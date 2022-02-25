import asyncio
import contextlib
import io
import logging
import pickle
import re
import time
from typing import Generator

import charmonium.time_block as ch_time_block


def check_lines(expected: str, actual: str) -> None:
    while expected.startswith("\n"):
        expected = expected[1:]

    for expected_line, line in zip(expected.split("\n"), actual.split("\n")):
        expected_line = expected_line.strip()
        line = line.strip()
        if not re.match(expected_line, line):
            print(repr(expected_line))
            print(repr(line))
        assert re.match(expected_line, line)


@contextlib.contextmanager
def capture_logs() -> Generator[io.StringIO, None, None]:
    capture = io.StringIO()
    capture_handler = logging.StreamHandler(capture)
    capture_handler.setFormatter(logging.Formatter("%(message)s"))
    ch_time_block.logger.addHandler(capture_handler)
    ch_time_block.clear()
    yield capture
    ch_time_block.logger.removeHandler(capture_handler)


def test_ctx() -> None:
    with capture_logs() as capture:
        with ch_time_block.ctx("main stuff 4"):
            time.sleep(0.1)
            with ch_time_block.ctx("inner stuff"):
                time.sleep(0.2)
    check_lines(
        r"""
 > main stuff 4: running
 > main stuff 4 > inner stuff: running
 > main stuff 4 > inner stuff: 0.2s
 > main stuff 4: 0.3s
""",
        capture.getvalue(),
    )


@ch_time_block.decor(print_args=True)
def foo(x: int) -> None:
    time.sleep(0.2)
    print(x)
    bar()


@ch_time_block.decor(do_gc=True)
def bar() -> None:
    time.sleep(0.1)


def test_decor() -> None:
    with capture_logs() as capture:
        foo(3)

    check_lines(
        r"""
 > foo\(3\): running
 > foo\(3\) > bar: running
 > foo\(3\) > bar: 0.1s \d+.\d+(Ki)?B \(gc: 0.\d+s\)
 > foo\(3\): 0.3s
""",
        capture.getvalue(),
    )


def test_print() -> None:
    foo(4)

    check_lines(
        r"""
foo\(3\)       =  100% of total =  100% of parent = \(.*?\) sec = *1\*\(.*?\) sec using \(.*?\) (Ki)?B
foo\(3\) > bar =  100% of total = +\d+% of parent = \(.*?\) sec = *1\*\(.*?\) sec using \(.*?\) (Ki)?B
""".rstrip(),
        ch_time_block.format_stats(),
    )


@ch_time_block.adecor()
async def afoo() -> int:
    await asyncio.sleep(0.3)
    return 0


async def abar() -> int:
    await asyncio.sleep(0.02)
    # this makes sure "abar" is ordered after "afoo"
    with ch_time_block.ctx("abar"):
        await asyncio.sleep(0.1)
        1 + (await abaz())
    return 1


@ch_time_block.adecor()
async def abaz() -> int:
    await asyncio.sleep(0.1)
    return 2


def test_async() -> None:
    with capture_logs() as capture:
        loop = asyncio.get_event_loop()
        loop.run_until_complete(asyncio.gather(afoo(), abar()))
        loop.close()

    check_lines(
        r"""
 > afoo: running
 > abar: running
 > abar > abaz: running
 > abar > abaz: 0.1s
 > abar: 0.2s
 > afoo: 0.3s
""",
        capture.getvalue(),
    )


def test_pickle() -> None:
    pickle.loads(pickle.dumps(ch_time_block.TimeBlock()))

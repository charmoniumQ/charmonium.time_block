import contextlib
import io
import logging
import re
import time
from typing import Generator

import charmonium.time_block as ch_time_block


def check_lines(expected: str, actual: str) -> None:
    while expected.startswith("\n"):
        expected = expected[1:]

    for expected_line, line in zip(
        expected.split("\n"), actual.split("\n")
    ):
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
    check_lines(r"""
 > main stuff 4: running
 > main stuff 4 > inner stuff: running
 > main stuff 4 > inner stuff: 0.2s \d+.\d+K?b \(gc: 0.0s\)
 > main stuff 4: 0.3s \d+.\d+K?b \(gc: 0.0s\)
""", capture.getvalue())


@ch_time_block.decor(print_args=True)
def foo(x: int) -> None:
    time.sleep(0.2)
    print(x)
    bar()


@ch_time_block.decor(run_gc=True)
def bar() -> None:
    time.sleep(0.1)


def test_decor() -> None:
    with capture_logs() as capture:
        foo(3)

    check_lines(r"""
 > foo: running \(3\)
 > foo > bar: running
 > foo > bar: 0.1s \d+.\d+K?b \(gc: 0.\d+s\)
 > foo: 0.3s \d+.\d+K?b \(gc: 0.\d+s\) \(3\)
""", capture.getvalue())

def test_print() -> None:
    foo(4)

    check_lines(r"""
foo       =  100% of total =  100% of parent = \(.*?\) sec = 2 \(.*?\) sec  \(.*?\) K?b
foo > bar =  100% of total = +\d+% of parent = \(.*?\) sec = 2 \(.*?\) sec  \(.*?\) K?b
""".rstrip(), ch_time_block.format_stats())

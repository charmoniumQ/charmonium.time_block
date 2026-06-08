import asyncio
import collections
import datetime
import math
import pickle
import time
import pytest

import charmonium.time_block.types as types
import charmonium.time_block.stats as stats
import charmonium.time_block as ch_time_block


def test_pickle() -> None:
    # Pickl-ability is important for charmonium.cache,
    # which may be used in conjunction with this
    pickle.loads(pickle.dumps(types.PicklableLock()))
    pickle.loads(pickle.dumps(ch_time_block.TimerManager()))
    pickle.loads(pickle.dumps(ch_time_block.Timer(ch_time_block.TimerManager())))


tolerance = 0.02
reliable_sleep_unit = 0.1


def test_sync() -> None:
    time_block = ch_time_block.Timer(ch_time_block.TimerManager())

    @time_block.decor()
    def func0() -> None:
        reliable_sleep(reliable_sleep_unit, tolerance)
        func1(42)

    @time_block.decor()
    def func1(n: int) -> None:
        reliable_sleep(reliable_sleep_unit, tolerance)
        with time_block.ctx("ctx"):
            reliable_sleep(reliable_sleep_unit, tolerance)
        for _ in time_block.time_iter("iter", range(2)):
            reliable_sleep(reliable_sleep_unit, tolerance)
        for _ in generator():
            reliable_sleep(reliable_sleep_unit, tolerance)

    @time_block.decor()
    def generator() -> collections.abc.Generator[int, None, None]:
        reliable_sleep(reliable_sleep_unit, tolerance)
        yield 1
        reliable_sleep(reliable_sleep_unit, tolerance)
        yield 2

    func0()
    timer_stats = time_block.get_stats()

    expected_lines = """
│┆├┴ 0.1s ctx
│┆├┴ 0.2s iter
│┆├┴ 0.4s generator
│├┴ 0.8s func1
├┴ 0.9s func0
    """.strip().splitlines()
    actual_lines = stats.log_frames_in_order(timer_stats)
    print("\n".join(actual_lines))
    assert expected_lines == actual_lines


@pytest.mark.xfail()
def test_async() -> None:
    # TODO: Fix this
    time_block = ch_time_block.Timer(ch_time_block.TimerManager())

    @time_block.decor()
    async def func0() -> None:
        # Use reliable_sleep to simulate actual computation,
        # which would block other threads.
        reliable_sleep(reliable_sleep_unit, tolerance)

        # asyncio.sleep will not influence wallclock timings if there is concurrency
        await asyncio.gather(func1(42), asyncio.sleep(reliable_sleep_unit * 2))

    @time_block.decor()
    async def func1(n: int) -> None:
        reliable_sleep(reliable_sleep_unit, tolerance)

    asyncio.run(func0())
    timer_stats = time_block.get_stats()
    for a, b in timer_stats:
        print(a)
        print(a.description, a.top().type)
        print(b)
    expected_lines = """a
    """.strip().splitlines()
    actual_lines = stats.log_frames_in_order(timer_stats)
    print("\n".join(actual_lines))
    print(actual_lines)
    assert expected_lines == actual_lines


def reliable_sleep(duration: float, tolerance: float) -> None:
    """Sleeps for duration * (1 +/- rtol) or throws an error."""
    start = datetime.datetime.now()
    time.sleep(duration)
    actual_duration = (datetime.datetime.now() - start).total_seconds()
    if not math.isclose(duration, actual_duration, abs_tol=tolerance):
        raise RuntimeError(f"Inaccurate sleep {duration=}, {actual_duration=}")

from __future__ import annotations

import asyncio
import collections
import contextlib
import copy
import datetime
import functools
import gc
import logging
import sys
import threading
from collections import defaultdict
from typing import (
    Any,
    Awaitable,
    Callable,
    DefaultDict,
    Dict,
    Generator,
    List,
    Mapping,
    Optional,
    Tuple,
    TypeVar,
    cast,
)

import psutil  # type: ignore

from .utils import mean, mem2str, python_sanitize, stddev


def safe_current_task() -> Optional[Any]:
    try:
        return asyncio.current_task()
    except RuntimeError:
        return None


class TimeBlockData(threading.local):
    def __init__(self, initial_stack: List[str], use_task_name: bool = False) -> None:
        super().__init__()
        self.stacks: DefaultDict[int, List[str]] = defaultdict(self.initial_stack)
        self.initial_stack_ = initial_stack
        self.use_task_name = use_task_name

    def __getstate__(self) -> Mapping[str, Any]:
        return self.__dict__

    def __setstate__(self, state: Mapping[str, Any]) -> None:
        self.__dict__.update(state)

    def initial_stack(self) -> List[str]:
        if self.use_task_name:
            task = safe_current_task()
            return [task.get_name()] if task else self.initial_stack_[:]
        else:
            return self.initial_stack_[:]

    @property
    def stack(self) -> List[str]:
        task = safe_current_task()
        task_id = id(task) if task is not None else 0
        return self.stacks[task_id]


FunctionType = TypeVar("FunctionType", bound=Callable[..., Any])
AsyncFunctionType = TypeVar("AsyncFunctionType", bound=Callable[..., Awaitable[Any]])

logger = logging.getLogger("charmonium.logger")
logger.setLevel(logging.DEBUG)


class TimeBlock:
    def __init__(self, root_label: str = "") -> None:
        if not root_label:
            if threading.current_thread() is threading.main_thread():
                root_label = ""
            else:
                root_label = "Thread " + threading.current_thread().name
        self.data = TimeBlockData([root_label])
        self.lock = threading.RLock()
        self.stats: Dict[
            Tuple[str, ...], List[Tuple[float, int]]
        ] = collections.defaultdict(list)
        self.logger = logger
        self.handler = logging.StreamHandler(sys.stdout)
        self.handler.setFormatter(logging.Formatter("%(message)s"))

    def __getstate__(self) -> Mapping[str, Any]:
        return {
            "stats": self.stats,
            "data": self.data,
        }

    def __setstate__(self, state: Mapping[str, Any]) -> None:
        self.stats = state["stats"]
        self.data = state["data"]

    def get_stats(self) -> Dict[Tuple[str, ...], List[Tuple[float, int]]]:
        """Gets the stats for a specific function."""
        # need lock to get consistent view of stats
        with self.lock:
            # need deepcopy so returned object doesn't change
            return copy.deepcopy(dict(self.stats))

    @contextlib.contextmanager
    def ctx(
        self,
        name: str,
        name_extra: str = "",
        print_start: bool = True,
        print_stop: bool = True,
        do_gc: bool = False,
    ) -> Generator[None, None, None]:
        """Measure the time and memory-usage of the wrapped context.

        If `do_gc`, then I will run garbage collection (with a
        separate timer). This makes memory usage stats more accurate.

        >>> import charmonium.time_block as ch_time_block
        >>> ch_time_block._enable_doctest_logging()
        >>> import time
        >>> with ch_time_block.ctx("main stuff 1", do_gc=True): # doctest:+ELLIPSIS
        ...     time.sleep(0.1)
        ...     with ch_time_block.ctx("inner stuff"):
        ...         time.sleep(0.2)
        ...
         > main stuff 1: running
         > main stuff 1 > inner stuff: running
         > main stuff 1 > inner stuff: 0.2s
         > main stuff 1: 0.3s ...B (gc: ...s)

        """

        self.data.stack.append(name + name_extra)
        qualified_name_str = " > ".join(self.data.stack)
        if print_start:
            self.logger.debug("%s: running", qualified_name_str)
        exc: Optional[Exception] = None
        process = psutil.Process()
        time_start = datetime.datetime.now()
        mem_start = process.memory_info().rss
        try:
            yield
        except Exception as exc2:  # pylint: disable=broad-except
            exc = exc2
        finally:
            time_stop = datetime.datetime.now()
            duration = (time_stop - time_start).total_seconds()
            if do_gc:
                gc_start = datetime.datetime.now()
                gc.collect()
                gc_end = datetime.datetime.now()
                gc_duration = (gc_end - gc_start).total_seconds()
            else:
                gc_duration = 0
            mem_end = process.memory_info().rss
            mem_leaked = mem_end - mem_start
            with self.lock:
                self.stats[tuple(self.data.stack[1:])].append((duration, mem_leaked))
            self.data.stack.pop()
            if print_stop:
                mem_val, mem_unit, _ = mem2str(mem_leaked)
                self.logger.debug(
                    "%s: %.1fs%s%s",
                    qualified_name_str,
                    duration,
                    f" {mem_val:.1f}{mem_unit} (gc: {gc_duration:.1f}s)"
                    if do_gc
                    else "",
                    " (err)" if exc is not None else "",
                )
        if exc:
            raise exc

    def decor(
        self,
        print_start: bool = True,
        print_stop: bool = True,
        print_args: bool = False,
        do_gc: bool = False,
    ) -> Callable[[FunctionType], FunctionType]:
        def make_timed_func(func: FunctionType) -> FunctionType:
            @functools.wraps(func)
            def timed_func(*args: Any, **kwargs: Any) -> Any:
                if print_args:
                    arg_str = "".join(
                        [
                            "(",
                            ", ".join(f"{arg!r}" for arg in args),
                            ", ".join(
                                f"{key}={val!r}" for key, val in sorted(kwargs.items())
                            ),
                            ")",
                        ]
                    )
                else:
                    arg_str = ""
                with self.ctx(
                    func.__qualname__,
                    name_extra=arg_str,
                    print_start=print_start,
                    print_stop=print_stop,
                    do_gc=do_gc,
                ):
                    return func(*args, **kwargs)

            return cast(FunctionType, timed_func)

        return make_timed_func

    def adecor(
        self,
        print_start: bool = True,
        print_stop: bool = True,
        print_args: bool = False,
        do_gc: bool = False,
    ) -> Callable[[AsyncFunctionType], AsyncFunctionType]:
        """Asynchronous version of decor"""

        def make_timed_async_func(func: FunctionType) -> AsyncFunctionType:
            @functools.wraps(func)
            async def timed_func(*args: Any, **kwargs: Any) -> Any:
                if print_args:
                    arg_str = "".join(
                        [
                            "(",
                            ", ".join(f"{arg!r}" for arg in args),
                            ", ".join(
                                f"{key}={val!r}" for key, val in sorted(kwargs.items())
                            ),
                            ")",
                        ]
                    )
                else:
                    arg_str = ""
                with self.ctx(
                    func.__qualname__,
                    name_extra=arg_str,
                    print_start=print_start,
                    print_stop=print_stop,
                    do_gc=do_gc,
                ):
                    return await func(*args, **kwargs)

            return cast(AsyncFunctionType, timed_func)

        return make_timed_async_func

    def format_stats(self) -> str:
        stats = {
            key: (
                len(vals),
                mean([time for time, mem in vals]),
                stddev([time for time, mem in vals]),
                mean([mem for time, mem in vals]),
                stddev([mem for time, mem in vals]),
            )
            for key, vals in self.get_stats().items()
        }

        keys = sorted(stats.keys())
        key_field_length = max(len(" > ".join(key)) for key in keys) if keys else 0

        lines: List[str] = []

        for key in keys:
            key_str = " > ".join(key)

            n_calls = stats[key][0]
            cumulative_time_m = stats[key][1]
            cumulative_time_s = stats[key][2]
            mem_m, mem_unit, mem_unit_size = mem2str(stats[key][3])
            mem_s = stats[key][4] / mem_unit_size
            percall_time_m = cumulative_time_m / n_calls
            percall_time_s = cumulative_time_s * n_calls

            parent = key[:-1]
            if parent in stats:
                parent_total_time_m = stats[parent][1]
                percent_parent = cumulative_time_m / parent_total_time_m * 100
            else:
                percent_parent = 100

            total = key[:2]
            total_time_m = stats[total][1]
            percent_total = cumulative_time_m / total_time_m * 100

            lines.append(
                " = ".join(
                    [
                        f"{key_str:{key_field_length}s}",
                        f"{percent_total: 4.0f}% of total",
                        f"{percent_parent: 4.0f}% of parent",
                        f"({cumulative_time_m:3.1f} +/- {cumulative_time_s:3.1f}) sec",
                        f"{n_calls: >3d}*({percall_time_m:3.1f} +/- {percall_time_s:3.1f}) sec",
                    ]
                )
                + f" using ({mem_m:.1f} +/- {mem_s:.1f}) {mem_unit}"
            )

        return "\n".join(lines)

    def print_stats(self) -> None:
        """

        >>> import charmonium.time_block as ch_time_block
        >>> ch_time_block.disable_stderr()
        >>> ch_time_block.clear()
        >>> import time
        >>> with ch_time_block.ctx("main stuff 2"):
        ...     time.sleep(0.1)
        ...     with ch_time_block.ctx("inner stuff"):
        ...         time.sleep(0.2)
        ...
        >>> import charmonium.time_block as ch_time_block
        >>> import time
        >>> @ch_time_block.decor()
        ... def foo():
        ...     time.sleep(0.3)
        ...     bar()
        ...
        >>> @ch_time_block.decor()
        ... def bar():
        ...     time.sleep(0.1)
        ...
        >>> foo()
        >>> ch_time_block.print_stats() # doctest:+SKIP
        foo                        =  100% of total =  100% of parent = (0.40 +/- 0.00) sec = 2 (0.20 +/- 0.00) sec  (0.0 +/- 0.0) b
        foo > bar                  =  100% of total =   25% of parent = (0.10 +/- 0.00) sec = 2 (0.05 +/- 0.00) sec  (0.0 +/- 0.0) b
        main stuff 2               =  100% of total =  100% of parent = (0.30 +/- 0.00) sec = 2 (0.15 +/- 0.00) sec  (0.0 +/- 0.0) b
        main stuff 2 > inner stuff =  100% of total =   66% of parent = (0.20 +/- 0.00) sec = 2 (0.10 +/- 0.00) sec  (0.0 +/- 0.0) b
        >>> ch_time_block.enable_stderr()
        >>> # This makes future doctests work, which are run with the same state
        """

        print(self.format_stats())

    def add_stats(
        self, other_stats: Dict[Tuple[str, ...], List[Tuple[float, int]]]
    ) -> None:
        """Aggregate statistics from multiple TimeBlock objects.

        See also print_stats.
        """
        with self.lock:
            for key, times in other_stats.items():
                self.stats[key].extend(times)

    def clear(self) -> None:
        """Clear statistsics.

        See also print_stats.

        """
        with self.lock:
            self.stats.clear()

    def enable_stderr(self) -> None:
        self.logger.addHandler(self.handler)

    def disable_stderr(self) -> None:
        self.logger.removeHandler(self.handler)

    def _enable_doctest_logging(self) -> None:
        # This is hack to make doctests work
        # It monkypatches sys.stdout, so I have to re-grab it here.
        self.handler.setStream(sys.stdout)


__all__ = ["TimeBlock"]

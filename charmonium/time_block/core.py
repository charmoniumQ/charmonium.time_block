from __future__ import annotations

import asyncio
import collections
import copy
import contextlib
import functools
import inspect
import types as types_lib
import typing
import warnings
import psutil
from . import types
from . import utils


_Params = typing.ParamSpec("_Params")
_ReturnType = typing.TypeVar("_ReturnType", covariant=True)
_Element = typing.TypeVar("_Element", covariant=True)
_GeneratorOutput = typing.TypeVar("_GeneratorOutput", covariant=True)
_GeneratorInput = typing.TypeVar("_GeneratorInput", contravariant=True)


class TimerManager:
    """Holds data from timers"""

    stacks_lock: types.PicklableLock
    stats_lock: types.PicklableLock
    process: psutil.Process
    stacks: dict[types.ThreadID, types.MutableStack]
    stats: list[tuple[types.FrozenStack, list[types.ResourceDiff]]]
    push_callbacks: list[
        typing.Union[
            typing.Callable[[types.ThreadID, types.FrozenStack, typing.Any], None],
            typing.Callable[
                [types.ThreadID, types.FrozenStack, typing.Any],
                collections.abc.Awaitable[None],
            ],
        ],
    ]
    pop_callbacks: list[
        typing.Union[
            typing.Callable[
                [types.ThreadID, types.FrozenStack, typing.Any, types.ResourceDiff],
                None,
            ],
            typing.Callable[
                [types.ThreadID, types.FrozenStack, typing.Any, types.ResourceDiff],
                collections.abc.Awaitable[None],
            ],
        ],
    ]

    def __getstate__(self) -> typing.Any:
        return (self.stacks, self.stats)

    def __setstate__(self, state: typing.Any) -> None:
        self.stacks = state[0]
        self.stats = state[1]

    def __init__(self) -> None:
        self.stacks_lock = types.PicklableLock()
        self.stats_lock = types.PicklableLock()
        self.process = psutil.Process()
        self.stacks = {}
        self.stats = []
        self.push_callbacks = []
        self.pop_callbacks = []

    @contextlib.contextmanager
    def add_frame(
        self,
        frame: types.Frame,
        extra: collections.abc.Mapping[str, typing.Any],
    ) -> collections.abc.Iterator[None]:
        thread_id = types.ThreadID.current()
        with self.stacks_lock:
            stack = self.stacks.setdefault(thread_id, types.MutableStack(thread_id))

        stack.push(frame)
        this_stack = stack.freeze()

        push_awaitables = []
        for push_callback in self.push_callbacks:
            ret = push_callback(thread_id, this_stack, extra)
            if ret is None:
                pass
            elif inspect.isawaitable(ret):
                push_awaitables.append(ret)
            else:
                raise TypeError()

        if push_awaitables:
            utils.sync_await(asyncio.gather(*push_awaitables))

        start = types.ResourceObservation.create(self.process)

        exc2: Exception | None = None
        try:
            yield
        except Exception as exc:
            exc2 = exc
        finally:
            end = types.ResourceObservation.create(self.process)
            diff = end - start

            assert stack.pop() == frame

            with self.stats_lock:
                if self.stats and self.stats[-1][0] == this_stack:
                    self.stats[-1][1].append(diff)
                else:
                    self.stats.append((this_stack, [diff]))

            pop_awaitables = []
            for pop_callback in self.pop_callbacks[::-1]:
                ret = pop_callback(thread_id, this_stack, extra, diff)
                if ret is None:
                    pass
                elif inspect.isawaitable(ret):
                    pop_awaitables.append(ret)
                else:
                    raise TypeError()
            if pop_awaitables:
                utils.sync_await(asyncio.gather(*pop_awaitables))

        if exc2:
            raise exc2

    def get_stats(self) -> list[tuple[types.FrozenStack, list[types.ResourceDiff]]]:
        with self.stats_lock:
            return copy.deepcopy(self.stats)

    def add_push_callback(
        self,
        push_callback: typing.Union[
            typing.Callable[[types.ThreadID, types.FrozenStack, typing.Any], None],
            typing.Callable[
                [types.ThreadID, types.FrozenStack, typing.Any],
                collections.abc.Awaitable[None],
            ],
        ],
    ) -> None:
        self.push_callbacks.append(push_callback)

    def add_pop_callback(
        self,
        pop_callback: typing.Union[
            typing.Callable[
                [types.ThreadID, types.FrozenStack, typing.Any, types.ResourceDiff],
                None,
            ],
            typing.Callable[
                [types.ThreadID, types.FrozenStack, typing.Any, types.ResourceDiff],
                collections.abc.Awaitable[None],
            ],
        ],
    ) -> None:
        self.pop_callbacks.append(pop_callback)


# TODO: Make robust for multiprocessing.
# - Detect main using utils.is_main_process
# - Non-mains send completed frames to main using a pipe
# - Main should drain pipe when main frame end
# - ThreadID should have a process ID

# TODO: Review Python's standard approach
# - https://github.com/python/cpython/blob/3.13/Lib/profile.py#L104


# https://github.com/python/typeshed/blob/1b1f3a9625ed26830549cddc3ddf0d8842e5e42b/stdlib/typing.pyi#L531
class TimedIterator(
    collections.abc.Iterator[_Element],
    typing.Generic[_Element],
):
    def __init__(
        self,
        timer_manager: TimerManager,
        iterable: collections.abc.Iterator[_Element],
        frame: types.Frame,
        time_container: bool,
        time_yield: bool,
        time_next: bool,
        extra: collections.abc.Mapping[str, typing.Any],
    ) -> None:
        self.timer_manager = timer_manager
        self.iterable = iterable
        self.frame = frame
        self.time_yield = time_yield
        self.time_next = time_next
        self.container_context: None | typing.ContextManager[None] = None
        self.yield_context: None | typing.ContextManager[None] = None
        self.extra = extra
        if time_container:
            self.container_context = self.timer_manager.add_frame(
                self.frame.replace_type(types.FrameType.LOOP_CONTAINER),
                self.extra,
            )
            self.container_context.__enter__()

    def _pre_next(self) -> None:
        if self.yield_context is not None:
            self.yield_context.__exit__(None, None, None)
            self.yield_context = None

    def _post_next(self) -> None:
        if self.time_yield:
            self.yield_context = self.timer_manager.add_frame(
                self.frame.replace_type(types.FrameType.LOOP_YIELD),
                self.extra,
            )
            self.yield_context.__enter__()

    def _close_exc(
        self,
        exception_type: type[BaseException] | None,
        exception: Exception,
        traceback: types_lib.TracebackType | None,
    ) -> None:
        if self.container_context:
            self.container_context.__exit__(exception_type, exception, traceback)
            self.container_context = None

    def _close(self) -> None:
        if self.container_context:
            self.container_context.__exit__(None, None, None)
            self.container_context = None

    def __next__(self) -> _Element:
        self._pre_next()
        try:
            if self.time_next:
                with self.timer_manager.add_frame(
                    self.frame.replace_type(types.FrameType.LOOP_NEXT),
                    self.extra,
                ):
                    val = self.iterable.__next__()
            else:
                val = self.iterable.__next__()
        except Exception as exc:
            self._close_exc(type(exc), exc, exc.__traceback__)
            raise exc
        else:
            self._post_next()
            return val

    def __del__(self) -> None:
        if self.yield_context is not None:
            self.yield_context.__exit__(None, None, None)
            warnings.warn(
                f"{type(self).__name__} was not iterated completely. Results will be wrong for {self.frame} YIELD_ELEMENT"
            )
        if self.container_context is not None:
            self.container_context.__exit__(None, None, None)
            warnings.warn(
                f"{type(self).__name__} was not iterated completely. Results will be wrong for {self.frame} CONTAINER_ELEMENT"
            )

    def __iter__(self) -> collections.abc.Iterator[_Element]:
        return self


# https://github.com/python/typeshed/blob/9354f93e6fbd3cce4862dfda403758bca08d3dae/stdlib/typing.pyi#L546
class TimedGenerator(
    collections.abc.Generator[_GeneratorOutput, _GeneratorInput, _ReturnType],
    TimedIterator[_GeneratorOutput],
    typing.Generic[_GeneratorOutput, _GeneratorInput, _ReturnType],
):
    def __init__(
        self,
        timer_manager: TimerManager,
        generator: collections.abc.Generator[
            _GeneratorOutput, _GeneratorInput, _ReturnType
        ],
        frame: types.Frame,
        extra: collections.abc.Mapping[str, typing.Any],
    ) -> None:
        self.timer_manager = timer_manager
        self.generator = generator
        self.frame = frame
        self.extra = extra
        TimedIterator.__init__(
            self, timer_manager, generator, frame, True, True, True, extra
        )
        # - Would opening and sending to multiple iterators disturb the stack?
        # TODO: put frame for init/close of iterator

    def send(self, input: _GeneratorInput) -> _GeneratorOutput:
        self._pre_next()
        try:
            with self.timer_manager.add_frame(
                self.frame.replace_type(types.FrameType.LOOP_NEXT),
                self.extra,
            ):
                output = self.generator.send(input)
        except Exception as exc:
            self._close_exc(type(exc), exc, exc.__traceback__)
            raise exc
        else:
            return output

    def throw(
        self,
        exception_type: BaseException | type[BaseException],
        exception: typing.Any = None,
        traceback: types_lib.TracebackType | None = None,
    ) -> _GeneratorOutput:
        if isinstance(exception_type, BaseException):
            exception = exception_type
            exception_type = type(exception)
            traceback = exception.__traceback__
        self._close_exc(exception_type, exception, traceback)
        return self.generator.throw(exception_type, exception, traceback)

    def close(self) -> _ReturnType | None:
        self._close()
        return self.generator.close()

    def __iter__(
        self,
    ) -> collections.abc.Generator[_GeneratorOutput, _GeneratorInput, _ReturnType]:
        return self


class TimedAwaitable(
    collections.abc.Awaitable[_ReturnType],
    typing.Generic[_ReturnType],
):
    def __init__(
        self,
        timer_manager: TimerManager,
        awaitable: collections.abc.Awaitable[_ReturnType],
        frame: types.Frame,
        extra: collections.abc.Mapping[str, typing.Any],
    ) -> None:
        self.timer_manager = timer_manager
        self.awaitable = awaitable
        self.frame = frame
        self.extra = extra

    def __await__(self) -> typing.Generator[typing.Any, typing.Any, _ReturnType]:
        with self.timer_manager.add_frame(
            self.frame.replace_type(types.FrameType.ASYNC_TOTAL),
            self.extra,
        ):
            with self.timer_manager.add_frame(
                self.frame.replace_type(types.FrameType.ASYNC_NEXT),
                self.extra,
            ):
                gi = self.awaitable.__await__()
            send_in = None
            while True:
                try:
                    with self.timer_manager.add_frame(
                        self.frame.replace_type(types.FrameType.ASYNC_NEXT),
                        self.extra,
                    ):
                        send_out = gi.send(send_in)
                    send_in = yield send_out
                except StopIteration as exc:
                    return typing.cast(_ReturnType, exc.value)


# https://github.com/python/typeshed/blob/9354f93e6fbd3cce4862dfda403758bca08d3dae/stdlib/typing.pyi#L586
class TimedCoroutine(
    typing.Coroutine[_GeneratorOutput, _GeneratorInput, _ReturnType],
    TimedAwaitable[_ReturnType],
    typing.Generic[_GeneratorOutput, _GeneratorInput, _ReturnType],
):
    def __init__(
        self,
        timer_manager: TimerManager,
        coroutine: typing.Coroutine[_GeneratorOutput, _GeneratorInput, _ReturnType],
        frame: types.Frame,
        extra: collections.abc.Mapping[str, typing.Any],
    ) -> None:
        self.timer_manager = timer_manager
        self.coroutine = coroutine
        self.frame = frame
        self.__name__ = coroutine.__name__
        self.__qualname__ = coroutine.__qualname__
        TimedAwaitable.__init__(self, timer_manager, coroutine, frame, extra)

    def send(self, input: _GeneratorInput) -> _GeneratorOutput:
        with self.timer_manager.add_frame(
            self.frame.replace_type(types.FrameType.ASYNC_NEXT), self.extra
        ):
            output = self.coroutine.send(input)
        return output

    def throw(
        self,
        exception_type: BaseException | type[BaseException],
        exception: typing.Any = None,
        traceback: types_lib.TracebackType | None = None,
    ) -> _GeneratorOutput:
        return self.coroutine.throw(exception_type, exception, traceback)

    def close(self) -> None:
        return self.coroutine.close()


# https://github.com/python/typeshed/blob/9354f93e6fbd3cce4862dfda403758bca08d3dae/stdlib/typing.pyi#L619
class TimedAsyncIterator(
    collections.abc.AsyncIterator[_Element],
    typing.Generic[_Element],
):
    def __init__(
        self,
        timer_manager: TimerManager,
        iterator: collections.abc.AsyncIterator[_Element],
        frame: types.Frame,
        extra: collections.abc.Mapping[str, typing.Any],
    ) -> None:
        self.timer_manager = timer_manager
        self.iterator = iterator
        self.frame = frame
        self.extra = extra
        # TODO: Should be a different frametype for the elements

    def __aiter__(self) -> collections.abc.AsyncIterator[_Element]:
        return self

    def __anext__(self) -> collections.abc.Awaitable[_Element]:
        return TimedAwaitable(
            self.timer_manager, self.iterator.__anext__(), self.frame, self.extra
        )


# https://github.com/python/typeshed/blob/9354f93e6fbd3cce4862dfda403758bca08d3dae/stdlib/typing.pyi#L626
class TimedAsyncGenerator(
    TimedAsyncIterator[_GeneratorOutput],
    typing.Generic[_GeneratorOutput, _GeneratorInput],
):
    def __init__(
        self,
        timer_manager: TimerManager,
        generator: typing.AsyncGenerator[_GeneratorOutput, _GeneratorInput],
        frame: types.Frame,
        extra: collections.abc.Mapping[str, typing.Any],
    ) -> None:
        self.timer_manager = timer_manager
        self.generator = generator
        self.frame = frame
        self.extra = extra
        TimedAsyncIterator.__init__(self, timer_manager, generator, frame, extra)
        # TODO: Should time entire loop
        # TODO: Should be a different frametype for the elements

    def asend(
        self, input: _GeneratorInput
    ) -> typing.Coroutine[typing.Any, typing.Any, _GeneratorOutput]:
        return TimedCoroutine(
            self.timer_manager,
            self.generator.asend(input),
            self.frame,
            self.extra,
        )

    def athrow(
        self,
        exception_type: BaseException | type[BaseException],
        exception: typing.Any = None,
        traceback: types_lib.TracebackType | None = None,
    ) -> typing.Coroutine[typing.Any, typing.Any, _GeneratorOutput]:
        return self.generator.athrow(exception_type, exception, traceback)

    def aclose(self) -> typing.Coroutine[typing.Any, typing.Any, typing.Any]:
        return self.generator.aclose()


class Timer:
    """Times stuff"""

    def __init__(self, timer_manager: TimerManager) -> None:
        self.timer_manager = timer_manager

    @contextlib.contextmanager
    def ctx(
        self,
        key: typing.Hashable = None,
        description: str | None = None,
        **extra: typing.Any,
    ) -> collections.abc.Generator[None, None, None]:
        """Measure the time and memory-usage of the wrapped context.

        - `key` uniquely identifies this frame, which determines whether the
          duration gets accounted in the same bucket. For example, you may want to
          distinguish the block when the argument `mode` is `gzip` or `xz`, so you
          should use the the mode as part of the key for this frame. This defaults
          to `(location.function, location.lineno)`

        - `description` (defaults to `str(key)`) is a human-representation of
          `frame_key`.

        - `quiet` allws you to toggle this off without removing the annotation.
          E.g., one could pass `disable=verbosity < 4`. Statistics are still
          collected.

        """
        location = types.Location.caller(1)

        if key is None:
            key = (location.function, location.lineno)

        if description is None:
            description = str(key)

        frame = types.Frame(
            types.FrameType.CONTEXT_BODY,
            key,
            description,
            types.Location.caller(1),
        )

        with self.timer_manager.add_frame(frame, extra):
            yield

    def decor(
        self,
        description: str | None = None,
        key_func: None = None,
        **extra: typing.Any,
    ) -> typing.Callable[
        [typing.Callable[_Params, _ReturnType]], typing.Callable[_Params, _ReturnType]
    ]:
        """Time the annotated function.

        - If `key_func` is given, it will also receive *arsg and **kwargs. The
          return value will 'uniquify' the stack frame. Perhaps you wish to have
          `my_open(mode="gzip")` accounted separately from `my_open(mode="xz")`, so
          `key_func=lambda mode: mode`.

        For the other options, see `time_ctx`.

        """

        def make_timed_func(
            func: typing.Callable[_Params, _ReturnType],
        ) -> typing.Callable[_Params, _ReturnType]:

            parameter_names = inspect.signature(func).parameters.values()

            @functools.wraps(func)
            def timed_func(
                *args: _Params.args, **kwargs: _Params.kwargs
            ) -> _ReturnType:
                location = types.Location.caller(1)
                all_kwargs = {
                    **{param.name: arg for param, arg in zip(parameter_names, args)},
                    **kwargs,
                }
                description_str = (
                    func.__name__
                    if description is None
                    else description.format(**all_kwargs)
                )
                key: typing.Hashable
                if key_func is None:
                    key = func.__qualname__
                else:
                    key = (func.__qualname__, key_func(*args, **kwargs))
                if inspect.isgeneratorfunction(func):
                    frame = types.Frame(
                        types.FrameType.LOOP_CONTAINER, key, description_str, location
                    )
                    generator = func(*args, **kwargs)
                    return typing.cast(
                        _ReturnType,  # we know _ReturnType is a generator because of insepct
                        TimedGenerator(self.timer_manager, generator, frame, extra),
                    )
                elif inspect.isasyncgenfunction(func):
                    frame = types.Frame(
                        types.FrameType.ASYNC_TOTAL, key, description_str, location
                    )
                    async_generator = func(*args, **kwargs)
                    return typing.cast(
                        _ReturnType,  # we know _ReturnType is an async gen because of insepct
                        TimedAsyncGenerator(
                            self.timer_manager, async_generator, frame, extra
                        ),
                    )  #
                elif inspect.iscoroutinefunction(func):
                    frame = types.Frame(
                        types.FrameType.ASYNC_TOTAL, key, description_str, location
                    )
                    coroutine = func(*args, **kwargs)
                    return typing.cast(
                        _ReturnType,  # we know _ReturnType is a coroutine because of insepct
                        TimedCoroutine(self.timer_manager, coroutine, frame, extra),
                    )
                else:
                    frame = types.Frame(
                        types.FrameType.FUNCTION_CALL, key, description_str, location
                    )
                    with self.timer_manager.add_frame(frame, extra):
                        return func(*args, **kwargs)

            return timed_func

        return make_timed_func

    def time_iter(
        self,
        key: typing.Hashable,
        iterator: collections.abc.Iterator[_Element],
        description: str | None = None,
        time_iterations: bool = True,
        **extra: typing.Any,
    ) -> collections.abc.Iterable[_Element]:
        """
        - `time_iterations`: whether to time each individual iteration or just the entire loop.

        See `time_ctx` for other options
        """
        location = types.Location.caller(1)
        description = str(key) if description is None else description
        frame = types.Frame(types.FrameType.LOOP_CONTAINER, key, description, location)
        return TimedIterator(
            self.timer_manager,
            iter(iterator),
            frame,
            True,
            time_iterations,
            time_iterations,
            extra,
        )

    def get_stats(self) -> list[tuple[types.FrozenStack, list[types.ResourceDiff]]]:
        return self.timer_manager.get_stats()


# TODO: nice wrapper fn for TimedAsyncIter

from __future__ import annotations

import collections
import contextvars
import dataclasses
import datetime
import enum
import inspect
import os
import threading
import types as types_lib
import typing
import psutil


class Stack:
    frames: collections.abc.Sequence[Frame]

    def __len__(self) -> int:
        return len(self.frames)

    def __iter__(self) -> collections.abc.Iterable[Frame]:
        return self.frames

    @property
    def description(self) -> str:
        return " > ".join(frame.description for frame in self.frames)

    def top(self) -> Frame:
        return self.frames[-1]

    def startswith(self, other: Stack) -> bool:
        return len(self) >= len(other) and all(
            self_frame.key == other_frame.key
            for self_frame, other_frame in zip(self.frames, other.frames)
        )


class MutableStack(Stack):
    thread_id: ThreadID
    frames: list[Frame]

    def __init__(self, thread_id: ThreadID) -> None:
        self.thread_id = thread_id
        self.frames = []

    def push(self, frame: Frame) -> None:
        self.frames.append(frame)

    def pop(self) -> Frame:
        return self.frames.pop()

    def freeze(self) -> FrozenStack:
        return FrozenStack(self.thread_id, tuple(self.frames))


@dataclasses.dataclass(frozen=True)
class FrozenStack(Stack):
    thread_id: ThreadID
    frames: tuple[Frame, ...]


class FrameType(enum.Enum):
    """
    - `FUNCTION_CALL`: body of a function call, when the other, more specific enum items don't apply.
    - `CONTEXT_BODY`: body of a `with` statement.
    - `LOOP_NEXT`: time spent computing the next element, i.e., body of `next()`.
    - `LOOP_YIELD`: time between yields, i.e., body of for-loop.
    - `LOOP_ITERATION`: `LOOP_NEXT` + `LOOP_YIELD`.
    - `LOOP_CONTAINER`: time spent in entire for-loop.
    - `ASYNC_TOTAL`: time spent evaluating awaitable, including the time we were switched out.
    - `ASYNC_NEXT`: time spent switched in and evaluating awaitable, i.e., the "pure Python" part of the Awaitable
    """

    FUNCTION_CALL = enum.auto()
    CONTEXT_BODY = enum.auto()
    LOOP_NEXT = enum.auto()
    LOOP_YIELD = enum.auto()
    LOOP_ITERATION = enum.auto()
    LOOP_CONTAINER = enum.auto()
    ASYNC_TOTAL = enum.auto()
    ASYNC_NEXT = enum.auto()

    @property
    def is_repeatable(self) -> bool:
        return (
            self == FrameType.ASYNC_NEXT
            or self == FrameType.LOOP_NEXT
            or self == FrameType.LOOP_YIELD
            or self == FrameType.LOOP_ITERATION
        )


@dataclasses.dataclass(frozen=True)
class Frame:
    type: FrameType
    key: typing.Hashable
    _description: str | None
    location: Location

    @property
    def description(self) -> str:
        return self._description if self._description is not None else str(self.key)

    def __hash__(self) -> int:
        return hash((self.key, self.type))

    def __eq__(self, other: object) -> bool:
        return (
            isinstance(other, Frame)
            and self.type == other.type
            and self.location == other.location
            and self.key == other.key
        )

    def replace_type(self, type: FrameType) -> Frame:
        return Frame(type, self.key, self.description, self.location)


@dataclasses.dataclass(frozen=True)
class Location:
    filename: str
    lineno: int
    function: str

    @staticmethod
    def caller(how_far_up: int) -> Location:
        frame = inspect.stack()[-how_far_up - 1]
        return Location(frame.filename, frame.lineno, frame.function)


@dataclasses.dataclass(frozen=True)
class ResourceObservation:
    wall_time: float
    user_time: float
    system_time: float
    rss: int

    @staticmethod
    def create(process: psutil.Process) -> ResourceObservation:
        wall_time = datetime.datetime.now().timestamp()
        process_time = process.cpu_times()
        mem_info = process.memory_info()
        return ResourceObservation(
            wall_time,
            process_time.user,
            process_time.system,
            mem_info.rss,
        )

    def __sub__(self, other: ResourceObservation) -> ResourceDiff:
        return ResourceDiff(
            self.wall_time - other.wall_time,
            self.user_time - other.user_time,
            self.system_time - other.system_time,
            self.rss - other.rss,
        )


@dataclasses.dataclass(frozen=True)
class ResourceDiff:
    wall_time: float
    user_time: float
    system_time: float
    rss: int


class PicklableLock:
    def __init__(self) -> None:
        self.lock = threading.Lock()

    def __enter__(self) -> bool | None:
        return self.lock.__enter__()

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: types_lib.TracebackType | None,
    ) -> None:
        self.lock.__exit__(exc_type, exc_val, exc_tb)

    def __getstate__(self) -> None:
        return None

    def __setstate__(self, state: None) -> None:
        raise ValueError("there")
        self.lock = threading.Lock()


_ASYNC_CONTEXT_LOCK = PicklableLock()
_ASYNC_CONTEXT_COUNTER = 0
_ASYNC_CONTEXT = contextvars.ContextVar("var", default=-1)


# TODO: Dask case?
# TODO: Rename to RootFrame or ExecutionContext or something
@dataclasses.dataclass(frozen=True)
class ThreadID:
    process_id: int
    thread_id: int
    async_id: int

    @staticmethod
    def current() -> ThreadID:
        pid = os.getpid()
        thread_id = threading.current_thread().native_id
        assert isinstance(thread_id, int)

        global _ASYNC_CONTEXT_COUNTER
        async_context = _ASYNC_CONTEXT.get()
        if async_context == -1:
            with _ASYNC_CONTEXT_LOCK:
                async_context = _ASYNC_CONTEXT_COUNTER
                _ASYNC_CONTEXT.set(async_context)
                _ASYNC_CONTEXT_COUNTER += 1

        return ThreadID(
            pid,
            thread_id,
            async_context,
        )

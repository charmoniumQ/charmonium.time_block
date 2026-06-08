import asyncio
import collections
import math
import typing
import wrapt  # type: ignore


Map: typing.TypeAlias = collections.abc.Mapping
Seq: typing.TypeAlias = collections.abc.Sequence


def format_mem(
    n_bytes: float, base2: bool = True, round_up: bool = False
) -> tuple[float, str, float]:
    rounder = round if round_up else math.floor
    unit_map: list[str] = (
        ["B", "KiB", "MiB", "GiB", "TiB"]
        if base2
        else [
            "B",
            "KB",
            "MB",
            "GB",
            "TB",
        ]
    )
    base = 1024 if base2 else 1000
    unit_int = (
        min([len(unit_map) - 1, int(rounder(math.log(math.fabs(n_bytes), base)))])
        if n_bytes != 0
        else 0
    )
    unit_div = base**unit_int
    return n_bytes / unit_div, unit_map[unit_int], unit_div


_T = typing.TypeVar("_T")
_U = typing.TypeVar("_U")


def groupby(
    data: Seq[tuple[_T, _U]],
) -> Map[_T, Seq[_U]]:
    ret: dict[_T, list[_U]] = {}
    for key, value in data:
        ret.setdefault(key, []).append(value)
    return ret


class _LabelledObject(
    typing.Generic[_T],
    wrapt.ObjectProxy,  # type: ignore
):
    def __init__(self, object: _T, label: str):
        super(_LabelledObject, self).__init__(object)
        self._self_label = label

    def __str__(self) -> str:
        return self._self_label

    def __repr__(self) -> str:
        return f"_LabelledObject({self.__wrapped__!r}, {self._self_label!r})"


def labelled_object(object: _T, label: str) -> _T:
    """Override `object` such that `str(object)` returns label.

    See features and caveats of [`wrapt.ObjectProxy`](https://wrapt.readthedocs.io/en/latest/wrappers.html#object-proxy)

    """
    return typing.cast(_T, _LabelledObject(object, label))


async def coroutine(awaitable: collections.abc.Awaitable[_T]) -> _T:
    """Converts an awaitable to a coroutine that awaits it."""
    return await awaitable


def sync_await(awaitable: collections.abc.Awaitable[_T]) -> _T:
    """Awaits on _T in a synchronous or asynchronous context.

    In an asynchronous context, this "misses out" on parallelism that may have resulted from `await awaitable`.

    But if `awaitable` is `asyncio.gather(*awaitables)`, then parallelism is still permitted between the awaitables.
    """
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(coroutine(awaitable))
    else:
        return loop.run_until_complete(awaitable)

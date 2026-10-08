# import types
# import inspect
# import typing
# import collections
# import asyncio


# _ParamSpec = typing.ParamSpec("_ParamSpec")
# _T_co = typing.TypeVar("_T_co", covariant=True)
# TimeBlock: typing.TypeAlias = int


# def adecor(
#         time_block: TimeBlock,
# ) -> typing.Callable[
#     # input = output = one async fn
#     [typing.Callable[_ParamSpec, collections.abc.Awaitable[_T_co]]],
#     typing.Callable[_ParamSpec, collections.abc.Awaitable[_T_co]],
# ]:
#     def async_fn_wrapper(
#             callable_awaitable: typing.Callable[_ParamSpec, collections.abc.Awaitable[_T_co]],
#     ) -> typing.Callable[_ParamSpec, collections.abc.Awaitable[_T_co]]:
#         def async_fn(
#                 *args: _ParamSpec.args,
#                 **kwargs: _ParamSpec.kwargs,
#         ) -> collections.abc.Awaitable[_T_co]:
#             awaitable = callable_awaitable(*args, **kwargs)
#             return TimeAwaitable(1, awaitable)
#         return async_fn
#     return async_fn_wrapper


# class TimeAsyncIterator(typing.Generic[_T_co], collections.abc.AsyncIterator[_T_co]):
#     def __init__(
#             self,
#             time_block: TimeBlock,
#             iterator: collections.abc.AsyncIterator[_T_co],
#     ) -> None:
#         self.time_block = time_block
#         self.iterator = iterator

#     def __anext__(self) -> collections.abc.Awaitable[_T_co]:
#         return TimeAwaitable(self.time_block, self.iterator.__anext__())


# def aiter(
#         time_block: TimeBlock,
# ) -> typing.Callable[
#     # input = output = one async fn
#     [typing.Callable[_ParamSpec, collections.abc.AsyncIterator[_T_co]]],
#     typing.Callable[_ParamSpec, collections.abc.AsyncIterator[_T_co]],
# ]:
#     def async_fn_wrapper(
#             callable_awaitable: typing.Callable[_ParamSpec, collections.abc.AsyncIterator[_T_co]],
#     ) -> typing.Callable[_ParamSpec, collections.abc.AsyncIterator[_T_co]]:
#         def async_fn(
#                 *args: _ParamSpec.args,
#                 **kwargs: _ParamSpec.kwargs,
#         ) -> collections.abc.AsyncIterator[_T_co]:
#             awaitable = callable_awaitable(*args, **kwargs)
#             return TimeAsyncIterator(1, awaitable)
#         return async_fn
#     return async_fn_wrapper


# async def hello() -> str:
#     print(1)
#     await asyncio.sleep(0.1)
#     print(2)
#     await asyncio.sleep(0.1)
#     print(3)
#     return "hellow orld"


# async def hello2() -> collections.abc.AsyncIterator[int]:
#     print(1)
#     yield 1
#     await asyncio.sleep(0.1)
#     yield 2
#     print(2)
#     yield 3
#     await asyncio.sleep(0.1)
#     print(3)


# async def main() -> None:
#     print(await (adecor(1)(hello)()))
#     print([x async for x in (aiter(1)(hello2)())])


# asyncio.run(main())

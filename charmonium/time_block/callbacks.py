import datetime
import typing
import humanize
from . import types
from . import utils


def print_running(
    thread_id: types.ThreadID,
    stack: types.FrozenStack,
    extra: typing.Any,
) -> None:
    if (
        extra.get("verbose", True)
        and extra.get("print_running", True)
        and (
            extra.get("print_repeatables", False) or not stack.top().type.is_repeatable
        )
    ):
        print(f"{stack.description}: running")


def print_finished(
    thread_id: types.ThreadID,
    stack: types.FrozenStack,
    extra: typing.Any,
    resource_diff: types.ResourceDiff,
) -> None:
    if (
        extra.get("verbose", True)
        and extra.get("print_finished", True)
        and (
            extra.get("print_repeatables", False) or not stack.top().type.is_repeatable
        )
    ):
        time_str = humanize.naturaltime(
            datetime.timedelta(seconds=resource_diff.wall_time)
        )
        min_leak = extra.get("min_leak", 4096)
        if resource_diff.rss > min_leak:
            (
                mem_val,
                mem_unit,
                _,
            ) = utils.format_mem(resource_diff.rss, base2=True, round_up=False)
            leak_info = f", leaked {mem_val}{mem_unit}"
        else:
            leak_info = ""
        print(f"{stack.description}: finished in {time_str}{leak_info}")

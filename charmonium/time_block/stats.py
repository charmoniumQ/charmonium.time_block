import itertools
import typing
from . import types
from . import utils


Stats: typing.TypeAlias = list[tuple[types.FrozenStack, list[types.ResourceDiff]]]


def log_frames_in_order(
    stats: Stats,
) -> list[str]:
    # TODO: Show the thread ID and async context?
    output = []
    grouped_by_thread = utils.groupby(
        [(stack.thread_id, (stack, duration)) for stack, duration in stats]
    )
    for thread_id, frames in grouped_by_thread.items():
        for i, (stack, durations) in enumerate(frames):
            if not stack.top().type.is_repeatable:
                level = sum(not frame.type.is_repeatable for frame in stack.frames)
                indentation = "".join(
                    [*itertools.islice(itertools.cycle("│┆┊"), level - 1), "├┴"]
                )
                wall_time = sum(duration.wall_time for duration in durations)
                output.append(
                    f"{indentation} {wall_time:.1f}s {stack.top().description}"
                )
    return output


def log_frames_by_duration(
    frames: Stats,
    top_k: int | None = None,
    minimum_duration: float | None = None,
    context: bool = True,
    cumulative: bool = True,
) -> list[str]:
    # TODO: Print stats shows n calls, per call, cumulative, with std devs
    # TODO: Option to include exclude children time?
    output = []

    grouped_frames = utils.groupby(
        [
            (
                stack if context else stack.top(),
                duration,
            )
            for stack, durations in frames
            for duration in durations
        ]
    )
    averaged_frames = {
        stack: sum(duration.wall_time for duration in durations)
        / (len(durations) if cumulative else 1)
        for stack, durations in grouped_frames.items()
    }
    sorted_frames = sorted(
        averaged_frames.items(),
        key=lambda pair: pair[1],
        reverse=True,
    )
    if top_k is not None:
        selected_frames = sorted_frames[:top_k]
    if minimum_duration is not None:
        selected_frames = [
            (frame, duration)
            for frame, duration in sorted_frames
            if duration > minimum_duration
        ]
    for frame, duration in selected_frames:
        output.append(f"{duration:.1f}sec {frame.description}")
    return output

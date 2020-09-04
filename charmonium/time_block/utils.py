import math
import re
from typing import Callable, List, Tuple, cast


def mem2str(
    n_bytes: float, base2: bool = True, round_up: bool = False
) -> Tuple[float, str, float]:
    rounder = cast(Callable[[float], float], round) if round_up else math.floor
    unit_map: List[str] = ["B", "KiB", "MiB", "GiB", "TiB"] if base2 else [
        "B",
        "KB",
        "MB",
        "GB",
        "TB",
    ]
    base = 1024 if base2 else 1000
    unit_int = (
        min([len(unit_map) - 1, int(rounder(math.log(math.fabs(n_bytes), base)))])
        if n_bytes != 0
        else 0
    )
    unit_div = base ** unit_int
    return n_bytes / unit_div, unit_map[unit_int], unit_div


def mean(lst: List[float]) -> float:
    return sum(lst) / len(lst)


def stddev(lst: List[float], ddof: int = 1) -> float:
    if len(lst) != 1:
        m = mean(lst)
        return math.sqrt(sum((x - m) ** 2 for x in lst) / (len(lst) - ddof))
    else:
        return 0


def python_sanitize(name: str) -> str:
    """Converts `name` to a valid Python identifier.

    >>> # TODO: better as a unittest
    >>> from charmonium.time_block.utils import python_sanitize
    >>> python_sanitize("1hello world")
    '_1hello_world'

    This tries to strike a balance between keeping semantic
    information of the invalid characters while being concise. Due to
    the desire to be concise, I have not made this an injective
    function.

    >>> from charmonium.time_block.utils import python_sanitize
    >>> python_sanitize("a.b")
    'a_b'
    >>> python_sanitize("a..b")
    'a_b'

    """
    name = re.sub(r"([^a-zA-Z0-9_]+)", "_", name)
    name = re.sub(r"^[0-9]", r"_\g<0>", name)
    return name


__all__ = ["mem2str", "mean", "stddev"]

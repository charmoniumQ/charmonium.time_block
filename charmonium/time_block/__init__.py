"""Time blocks of code

See README.rst."""


from .time_block import TimeBlock, logger

__author__ = "Samuel Grayson"
__email__ = "sam+dev@samgrayson.me"
__version__ = "0.3.2"
__license__ = "MPL-2.0"
__copyright__ = "2020, Samuel Grayson"

_time_block = TimeBlock()
ctx = _time_block.ctx
decor = _time_block.decor
adecor = _time_block.adecor
print_stats = _time_block.print_stats
clear = _time_block.clear
get_stats = _time_block.get_stats
format_stats = _time_block.format_stats
disable_stderr = _time_block.disable_stderr
enable_stderr = _time_block.enable_stderr
_enable_doctest_logging = _time_block._enable_doctest_logging

enable_stderr()

__all__ = ["TimeBlock", "logger"]

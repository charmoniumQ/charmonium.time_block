"""Time blocks of code

See README.rst."""

from .core import (
    TimerManager as TimerManager,
    Timer as Timer,
)
from .callbacks import print_running, print_finished

__author__ = "Samuel Grayson"
__email__ = "sam+dev@samgrayson.me"
__version__ = "0.4.0"
__license__ = "MPL-2.0"
__copyright__ = "2020, Samuel Grayson"


global_timer_manager = TimerManager()
global_timer = Timer(global_timer_manager)
ctx = global_timer.ctx
decor = global_timer.decor
time_iter = global_timer.time_iter
global_timer_manager.add_push_callback(print_running)
global_timer_manager.add_pop_callback(print_finished)

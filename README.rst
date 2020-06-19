=====================
charmonium.time_block
=====================

Time a block of code.


Quickstart
----------

::

    $ pip install charmonium.time_block

Here are some reasons you would use this instead of an external profiler
(e.g. line_prof) or another internal profiler (e.g. block-timer).

- This records process measures memory usage (relatively cross-platform method using `psutil`_).

.. _`psutil`: https://github.com/giampaolo/psutil

- This has sub-function granularity. With-statement context handler can time
  blocks (in a timed-function or not).

    >>> import charmonium.time_block as ch_time_block
    >>> import time
    >>>
    >>> def foo():
    ...     with ch_time_block.ctx("bar"):
    ...         time.sleep(0.1)
    ...
    >>> foo()
     > bar: running
     > bar: 0.1s 0.0b (gc: 0.0s)

- But it can also easily annotate functions with an equivalent decorator.

    >>> import charmonium.time_block as ch_time_block
    >>>
    >>> # Suppose we don't care how fast foo runs.
    >>> def foo():
    ...     bar()
    ...
    >>>
    >>> @ch_time_block.ctx("bar")
    >>> def bar():
    ...     time.sleep(0.1)
    ...
    >>> foo()
     > bar: running
     > bar: 0.1s 0.0b (gc: 0.0s)

- Like function profiling, but unlike other block-profilers, it is
  recurrent, and it maintains a stack.

    >>> import charmonium.time_block as ch_time_block
    >>> import time
    >>>
    >>> @ch_time_block.decor()
    ... def foo():
    ...     time.sleep(0.1)
    ...     bar()
    ...
    >>>
    >>> @ch_time_block.decor()
    ... def bar():
    ...     time.sleep(0.2)
    ...     with ch_time_block.ctx("baz"):
    ...         time.sleep(0.3)
    ...
    >>> foo()
     > foo: running
     > foo > bar: running
     > foo > bar > baz: running
     > foo > bar > baz: 0.3s 0.0b (gc: 0.0s)
     > foo > bar: 0.5s 0.0b (gc: 0.0s)
     > foo: 0.6s 0.0b (gc: 0.0s)


- This also works for threads (or more usefully `ThreadPoolExecutor`).

    >>> import charmonium.time_block as ch_time_block
    >>> import time
    >>> from concurrent.futures import ThreadPoolExecutor
    >>>
    >>> @ch_time_block.decor()
    ... def foo():
    ...     time.sleep(0.1)
    ...     baz()
    ...
    >>> @ch_time_block.decor()
    ... def bar():
    ...     time.sleep(0.2)
    ...     baz()
    ...
    >>> @ch_time_block.decor()
    ... def baz():
    ...     return time.sleep(0.3)
    ...
    >>> from threading import Thread
    >>> threads = [Thread(target=foo), Thread(target=bar)]
    >>> for thread in threads:
    ...     thread.start()
    ...
     > foo: running
     > bar: running
     > foo > baz: running
     > bar > baz: running
     > foo > baz: 0.3s 0.0b (gc: 0.0s)
     > foo: 0.4s 0.0b (gc: 0.0s)
     > bar > baz: 0.3s 4.0Kb (gc: 0.0s)
     > bar: 0.5s 4.0Kb (gc: 0.0s)
    >>> # TODO: get a better example, with named threads

- This is less verbose. You can place annotations only around functions you care
  about.

    >>> import charmonium.time_block as ch_time_block
    >>> import time
    >>>
    >>> # Suppose we don't care how fast foo runs.
    >>> def foo():
    ...     time.sleep(0.1)
    ...     bar()
    ...
    >>>
    >>> @ch_time_block.decor()
    ... def bar():
    ...     time.sleep(0.2)
    ...     baz()
    ...
    >>>
    >>> # suppose we don't care to distinguish the work of bar from the work of baz
    >>> # If we do, just add annotation to baz as well
    >>> def baz():
    ...     time.sleep(0.3)
    ...
    >>> foo()
     > bar: running
     > bar: 0.5s 0.0b (gc: 0.0s)
    >>> # Only reports runtime of bar, and accounts the cost of bar and baz.

- This reports in realtime to logger and (optionally to stderr). This is
  intended to let the user know what the code is doing right now. E.g.

     > download: running
     > download: 0.1s 1.2kb (gc: 0.1s)
     > decompress: running
     > decompress: 0.2s 3.4b (gc: 0.3s)
     > processing: running
     > processing: 0.4s 3.4b (gc: 0.3s)

- The results are programatically accessible at runtime. In the dict returned by
  get_stats(), the stack frame (key) is represented as a tuple of strings while
  the profile result (value) is a pair of time and memory used.

    >>> import charmonium.time_block as ch_time_block
    >>> ch_time_block.clear()
    >>> import time
    >>>
    >>> @ch_time_block.decor()
    ... def foo():
    ...     time.sleep(0.1)
    ...     bar()
    ...
    >>>
    >>> @ch_time_block.decor()
    ... def bar():
    ...     time.sleep(0.2)
    ...     # suppose we don't care to distinguish the work of bar from the work of baz
    ...     # If we do, just add annotation to baz as well
    ...
    >>> foo() # doctest:+ELLIPSIS
    ...
    >>> ch_time_block.get_stats() # doctest:+SKIP
    {('foo', 'bar'): [(0.200505, 0)], ('foo',): [(0.301857, 0)]}
    >>> ch_time_block.print_stats()
    foo                      =  100% of total =  100% of parent = (0.40 +/- 0.00) sec = 4 (0.10 +/- 0.00) sec  (0.0 +/- 0.0) b
    foo > bar                =  100% of total =   25% of parent = (0.10 +/- 0.00) sec = 4 (0.03 +/- 0.00) sec  (0.0 +/- 0.0) b

- This handles recursion. Handling recursion any other way would break
  evaluating self / parent, because parent could be self.

    >>> import charmonium.time_block as ch_time_block
    >>> import time
    >>>
    >>> @ch_time_block.decor()
    ... def foo(n):
    ...     if n == 0:
    ...         return 0
    ...     else:
    ...         time.sleep(0.1)
    ...         return foo(n - 1)
    ...
    >>> foo(2)
     > foo: running
     > foo > foo: running
     > foo > foo > foo: running
     > foo > foo > foo: 0.0s 0.0b (gc: 0.0s)
     > foo > foo: 0.1s 0.0b (gc: 0.0s)
     > foo: 0.2s 0.0b (gc: 0.0s)

- This does not need source-code access, so it will work from ``.eggs``.




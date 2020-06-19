=====================
charmonium.time_block
=====================

Time a block of code.


Quickstart
----------

::

    $ pip install charmonium.time_block

Here are some reasons you would use this instead of an external
profiler (e.g. line_prof) or another internal profiler
(e.g. block-timer) for measuring time larger than 0.1s.

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
     > bar: 0.1s

- But it can also easily annotate functions with an equivalent decorator.

    >>> import charmonium.time_block as ch_time_block
    >>> # Suppose we don't care how fast foo runs.
    >>> def foo():
    ...     bar()
    ...
    >>>
    >>> @ch_time_block.ctx("bar")
    ... def bar():
    ...     time.sleep(0.1)
    ...
    >>> foo()
     > bar: running
     > bar: 0.1s

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
     > foo > bar > baz: 0.3s
     > foo > bar: 0.5s
     > foo: 0.6s

- This records process measures memory usage (relatively
  cross-platform method using `psutil`_) when ``do_gc=True``.


- This also works for threads (or more usefully `ThreadPoolExecutor`_).

.. _`ThreadPoolExecutor`: https://docs.python.org/3/library/concurrent.futures.html#concurrent.futures.ThreadPoolExecutor

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
    >>> for thread in threads: # doctest:+SKIP
    ...     thread.start()
    ...
     > foo: running
     > bar: running
     > foo > baz: running
     > bar > baz: running
     > foo > baz: 0.3s
     > foo: 0.4s
     > bar > baz: 0.3s
     > bar: 0.5s
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
     > bar: 0.5s
    >>> # Only reports runtime of bar, and accounts the cost of bar and baz.

- This reports in realtime to `logger`_ (destination customizable). This
  is intended to let the user know what the code is doing right
  now. E.g.

     > download: running
     > download: 0.1s
     > decompress: running
     > decompress: 0.2s
     > processing: running
     > processing: 0.4s

.. _`logger`: https://docs.python.org/3.9/library/logging.html

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
    >>> foo()
     > foo: running
     > foo > bar: running
     > foo > bar: 0.2s
     > foo: 0.3s
    >>> ch_time_block.get_stats() # doctest:+SKIP
    {('foo', 'bar'): [(0.200505, 0)], ('foo',): [(0.301857, 0)]}
    >>> ch_time_block.print_stats() # doctest:+SKIP
    foo       =  100% of total =  100% of parent = (0.30 +/- 0.00) sec = 1 (0.30 +/- 0.00) sec  (0.0 +/- 0.0) b
    foo > bar =  100% of total =   67% of parent = (0.20 +/- 0.00) sec = 1 (0.20 +/- 0.00) sec  (0.0 +/- 0.0) b

- This handles recursion. Handling recursion any other way would break
  evaluating self / parent, because parent could be self.

    >>> import charmonium.time_block as ch_time_block
    >>> import time
    >>>
    >>> @ch_time_block.decor(print_args=True)
    ... def foo(n):
    ...     if n != 0:
    ...         time.sleep(0.1)
    ...         return foo(n - 1)
    ...
    >>> foo(2)
     > foo(2): running
     > foo(2) > foo(1): running
     > foo(2) > foo(1) > foo(0): running
     > foo(2) > foo(1) > foo(0): 0.0s
     > foo(2) > foo(1): 0.1s
     > foo(2): 0.2s

- This does not need source-code access, so it will work from ``.eggs``.




=====================
charmonium.time_block
=====================

A decorator and a context-manager (with-statment) to time a block of
code.


Quickstart
----------

::

    $ pip install charmonium.time_block

.. code:: python

    >>> import charmonium.time_block as ch_time_block
    >>> ch_time_block._enable_doctest_logging()
    >>> import time
    >>> 
    >>> def foo():
    ...     with ch_time_block.ctx("bar"):
    ...         time.sleep(0.1)
    ... 
    >>> foo()
     > bar: running
     > bar: 0.1s

Equivalent context-manager:

.. code:: python


    >>> import charmonium.time_block as ch_time_block
    >>> ch_time_block._enable_doctest_logging()
    >>> 
    >>> def foo():
    ...     bar()
    ... 
    >>> 
    >>> @ch_time_block.decor("bar")
    ... def bar():
    ...     time.sleep(0.1)
    ... 
    >>> foo()
     > bar: running
     > bar: 0.1s

`line_prof`_ is extremely detailed and complex, which makes it more
appropriate when you don't know what to measure, whereas this package
is more appropriate when you already know the bottleneck, and just
want to see how slow a few functions/blocks are.

.. _`line_prof`: https://github.com/rkern/line_profiler

Unlike external profiling, This does not need source-code access, so
it will work from ``.eggs``.

Unlike external profiling, this package reports in realtime to
`logger`_ (destination customizable). This is intended to let the user
know what the code is doing right now.

.. _`logger`: https://docs.python.org/3.9/library/logging.html

::

     > download: running
     > download: 0.1s
     > processing: running
     > processing > decompress: running
     > processing > decompress: 0.2s
     > processing: 0.4s

Since this plugs into Python's
`logger`_ infrastructure, this can feed a pipeline that checks the
application health (e.g. ensuring a microservice is responsive).

.. _`logger`: https://docs.python.org/3.9/library/logging.html

This records process's increase in memory usage (relatively
cross-platform method using `psutil`_) when ``do_gc=True``, which
gives a rough estimate of the memory leaked by the block.

.. _`psutil`: https://github.com/giampaolo/psutil

Like function profiling, but unlike other block-profilers, it is
recurrent, and it maintains a stack.

.. code:: python

    >>> import charmonium.time_block as ch_time_block
    >>> ch_time_block._enable_doctest_logging()
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

This handles recursion.

.. code:: python

    >>> import charmonium.time_block as ch_time_block
    >>> ch_time_block._enable_doctest_logging()
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

This even works for threads (or more usefully `ThreadPoolExecutor`_).

.. _`ThreadPoolExecutor`: https://docs.python.org/3/library/concurrent.futures.html#concurrent.futures.ThreadPoolExecutor

.. code:: python

    >>> import charmonium.time_block as ch_time_block
    >>> ch_time_block._enable_doctest_logging()
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

The results are programatically accessible at runtime. In the dict
returned by ``get_stats()``, the stack frame (key) is represented as a
tuple of strings while the profile result (value) is a pair of time
and memory used.

.. code:: python

    >>> import charmonium.time_block as ch_time_block
    >>> ch_time_block._enable_doctest_logging()
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
    ... 
    >>> [foo() for _ in range(2)]
     > foo: running
     > foo > bar: running
     > foo > bar: 0.2s
     > foo: 0.3s
     > foo: running
     > foo > bar: running
     > foo > bar: 0.2s
     > foo: 0.3s
    [None, None]
    >>> ch_time_block.get_stats() # doctest:+SKIP
    {('foo', 'bar'): [(0.2, 0), (0.2, 0)], ('foo',): [(0.3, 0), (0.3, 0)]}
    >>> ch_time_block.print_stats()
    foo       =  100% of total =  100% of parent = (0.3 +/- 0.0) sec =   2*(0.2 +/- 0.0) sec using (0.0 +/- 0.0) B
    foo > bar =  100% of total =   66% of parent = (0.2 +/- 0.0) sec =   2*(0.1 +/- 0.0) sec using (0.0 +/- 0.0) B

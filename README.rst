=====================
charmonium.time_block
=====================

A function-decorator and a context-manager (with-statement) to time a block of
code.

If your program is executing a lengthy operation, it's good UI to let the user
know what's going on, rather than just silently chomping along. The user will
have insight on what the process is stuck on and can decide if that was expected
or not. This library lets the programmer tag some functions with a decorator or
with-statement that logs when the function starts and finishes executing.

The user won't want to see every function, but judiciously labeling a few
top-level blocks with human-readable strings makes the program's running times
more understandable.

Logging the start and end can also be useful for high-level macro-optimization.
`line_prof`_ will measure every line, which comes with overhead and lots more
data. Most lines are not the bottleneck, so this is just adding hay to the
haystack and the performance overhead. `line_prof`_ is good for
micro-optimization when you already know where the bottleneck is; this package
is good for learning what high-level operation is the bottleneck.

----------
Quickstart
----------

::

    $ pip install charmonium.time_block

.. code:: python

    >>> import charmonium.time_block as ch_time_block
    >>> import time
    >>>
    >>> def main():
    ...     with ch_time_block.ctx("downloading data"):
    ...         time.sleep(0.2)
    ...
    >>> main()
    downloading data: running
    downloading data: finished in now

Equivalent a decorator:

.. code:: python

    >>> @ch_time_block.decor()
    ... def download_data():
    ...     time.sleep(0.2)
    ...
    >>> download_data()
    download_data: running
    download_data: finished in now

Like function profiling, but unlike other block-loggers, this package maintains
a call stack of declared blocks (not every function). This "perforated stack"
lets the programmer explicitly what gets logged to the user. In particular, the
``description`` field allows one to customize the representation of that stack
frame, and the ``comment`` field allows one to add a message just at the start,
such as the problem-size.

.. code:: python

    >>> @ch_time_block.decor(
    ...     # fn params are available for use in the format string
    ...     description="delete-{x}",
    ...     comment="({x} nodes)",
    ... )
    ... def delete_nodes(x):
    ...     with ch_time_block.ctx(
    ...         description=f"finder-{x}",
    ...         comment=f"({x} nodes)",
    ...     ):
    ...         time.sleep(0.1)
    ...
    >>> delete_nodes(32)
    delete-32: running
    delete-32 > finder-32: running
    delete-32 > finder-32: finished in now
    delete-32: finished in now

Unlike external profiling, this package reports in realtime to `logger`_
(destination customizable). This is intended to let the user know what the code
is doing right now.

Since this plugs into Python's `logger`_ infrastructure, this can feed a
pipeline that checks the application health.

.. _`logger`: https://docs.python.org/3.9/library/logging.html

This records process's increase in memory usage (relatively cross-platform
method using `psutil`_) when ``do_gc=True``, which gives a rough estimate of the
memory leaked by the block. If a function consistently uses memory that doesn't
get freed when the function returns, it may indicate a memory leak. In
high-level graph processing code, this is helpful to know _which_ transformation
is eating up all of RAM.

.. _`psutil`: https://github.com/giampaolo/psutil

.. code:: python

    >>> variable = []
    >>> @ch_time_block.decor()
    ... def main():
    ...     # Oops, leaking memory in global variable
    ...     variable.append("abc" * 16384)
    ...
    >>> main()
    main: running
    main: finished in now, leaked ...KiB

----
TODO
----

- Explain iter, iter no elements, and async variants
- Describe workflow
- Note on performance/coarseness
  - Have global disable
  - Have context disable?
- Documentation explains two ways of getting the stats: event-based and batch
  - Print, structlog, logging, rich backends
    - Should be very easy to get a print; then ensure doctests work.
- Integration with other profilers
- There should be an easy integration with Typer/Click and with global/atexit
- Persistence
  - Save at final frame
  - Use hash of frame func + module version + global version
- Frames have optional data
  - Could have size vector
    - Could implement global progress bar
- Show the active awaitables?
- Can we do async_ctx? Probably not. If not, explain why in README
  - Should we be an async event loop? Probably not.
- Use term scope timer in documentation
- Differentiators: print, time async, time iters, includes memory
  - Similar projects:
    - https://pypi.org/project/tree-timer/
    - https://pypi.org/project/scope-timer/
    - cProfile
    - line_profiler
    - memory-profiler
    - https://github.com/dropbox/stopwatch
- Plug in to existing profile visualizers. Make a flame graph.

"""Derived from CPython 3.12 Lib/timeit.py; PSF License, see stdlib/LICENSE-PSF.txt.

Tool for measuring execution time of small code snippets.

This AIL source keeps the callable form of `Timer`: the statement and the
setup are functions, and `timeit(number=...)`, `repeat(repeat=...,
number=...)` and the module-level `timeit()` / `repeat()` call them.  The
string form needs `exec`/`compile`, which this compiler does not build.  A
program that uses one calls `exec` and is refused by name at build time; a
`str` that still reaches `Timer` is refused with `TypeError` naming that
requirement instead of being run a different way.  The command-line `main()`, the
`autorange()` helper and `print_exc()` (which imports `linecache` and
`traceback`) are left out for the same reason; behaviour of the callable
path, including `default_timer`, is CPython's.
"""

import sys
import time

__all__ = ["Timer", "timeit", "repeat", "default_timer"]

default_number = 1000000
default_repeat = 5


def default_timer():
    """The default timer: time.perf_counter() as a float of seconds."""
    return time.perf_counter()


def _no_setup():
    pass


def _reindent(src, indent):
    return src.replace("\n", "\n" + " " * indent)


class Timer:
    """Class for timing execution speed of small code snippets.

    The constructor takes a callable statement to be timed, an optional
    callable setup, and a timer function.  The timer function defaults to
    `default_timer` (platform-dependent).
    """

    def __init__(self, stmt=None, setup=None, timer=None):
        if stmt is None:
            stmt = _no_setup
        if setup is None:
            setup = _no_setup
        if timer is None:
            timer = default_timer
        if isinstance(stmt, str):
            raise TypeError("timeit.Timer: a string stmt needs exec, which is not built; "
                            "pass a callable")
        if isinstance(setup, str):
            raise TypeError("timeit.Timer: a string setup needs exec, which is not built; "
                            "pass a callable")
        if not callable(stmt):
            raise ValueError("stmt is neither a string nor callable")
        if not callable(setup):
            raise ValueError("setup is neither a string nor callable")
        if not callable(timer):
            raise ValueError("timer is not callable")
        self.stmt = stmt
        self.setup = setup
        self.timer = timer

    def timeit(self, number=default_number):
        """Time 'number' executions of the main statement."""
        self.setup()
        t0 = self.timer()
        for _i in range(number):
            self.stmt()
        t1 = self.timer()
        return t1 - t0

    def repeat(self, repeat=default_repeat, number=default_number):
        """Call timeit() a few times and return the list of results."""
        r = []
        for _i in range(repeat):
            r.append(self.timeit(number))
        return r


def timeit(stmt=None, setup=None, timer=None, number=default_number):
    """Convenience function to create a Timer object and call timeit."""
    return Timer(stmt, setup, timer).timeit(number)


def repeat(stmt=None, setup=None, timer=None, repeat=default_repeat, number=default_number):
    """Convenience function to create a Timer object and call repeat."""
    return Timer(stmt, setup, timer).repeat(repeat, number)

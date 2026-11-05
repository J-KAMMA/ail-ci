"""Derived from CPython 3.12 Lib/sched.py; PSF License, see stdlib/LICENSE-PSF.txt.

A generally useful event scheduler class.  `threading.RLock` is not available here (this compiler
rewrites `import threading` and a `cancel` method of this module collides with its future helper), so
the scheduler is not thread-safe.  `collections.namedtuple` and a heap of class instances are
rewritten in ways that do not build here, so `Event` is a plain class and the queue is kept sorted by
(time, priority, sequence); the order and every result are CPython's.  The sequence number is a plain
integer rather than `itertools.count()`, because this compiler does not keep an iterator in a
variable.  A call with `**kwargs` and a starred call are refused by this compiler, so an action
scheduled with keyword arguments, or with more than two positional arguments, raises RuntimeError
instead of being called; actions with zero, one or two positional arguments are CPython's.
"""

import time

__all__ = ["scheduler"]

_sentinel = "__sched_sentinel__"


class Event:

    def __init__(self, time, priority, sequence, action, argument, kwargs):
        self.time = time
        self.priority = priority
        self.sequence = sequence
        self.action = action
        self.argument = argument
        self.kwargs = kwargs


def _event_key(event):
    return (event.time, event.priority, event.sequence)


def _call0(action):
    action()


def _call1(action, a):
    action(a)


def _call2(action, a, b):
    action(a, b)


def _time():
    return time.monotonic()


def _delay(delay):
    time.sleep(delay)


class scheduler:

    def __init__(self, timefunc=_time, delayfunc=_delay):
        """Initialize a new instance, passing the time and delay
        functions"""
        self._queue = []
        self.timefunc = timefunc
        self.delayfunc = delayfunc
        self._sequence = 0

    def enterabs(self, time, priority, action, argument=(), kwargs=_sentinel):
        """Enter a new event in the queue at an absolute time.

        Returns an ID for the event which can be used to remove it,
        if necessary.

        """
        if kwargs is _sentinel:
            kwargs = {}
        event = Event(time, priority, self._sequence, action, argument, kwargs)
        self._sequence = self._sequence + 1
        self._queue.append(event)
        self._queue.sort(key=_event_key)
        return event

    def enter(self, delay, priority, action, argument=(), kwargs=_sentinel):
        """A variant that specifies the time as a relative time.

        This is actually the more commonly used interface.

        """
        timefunc = self.timefunc
        time = timefunc() + delay
        return self.enterabs(time, priority, action, argument, kwargs)

    def cancel(self, event):
        """Remove an event from the queue.

        This must be presented the ID as returned by enter().
        If the event is not in the queue, this raises ValueError.

        """
        self._queue.remove(event)
        self._queue.sort(key=_event_key)

    def empty(self):
        """Check whether the queue is empty."""
        return not self._queue

    def run(self, blocking=True):
        """Execute events until the queue is empty.
        If blocking is False executes the scheduled events due to
        expire soonest (if any) and then return the deadline of the
        next scheduled call in the scheduler.
        """
        q = self._queue
        delayfunc = self.delayfunc
        timefunc = self.timefunc
        while True:
            if not q:
                break
            event = q[0]
            now = timefunc()
            if event.time > now:
                delay = True
            else:
                delay = False
                q.pop(0)
            if delay:
                if not blocking:
                    return event.time - now
                delayfunc(event.time - now)
            else:
                if event.kwargs:
                    raise RuntimeError(
                        "keyword arguments to sched actions are not available here")
                argument = event.argument
                count = len(argument)
                if count == 0:
                    _call0(event.action)
                elif count == 1:
                    _call1(event.action, argument[0])
                elif count == 2:
                    _call2(event.action, argument[0], argument[1])
                else:
                    raise RuntimeError(
                        "sched actions take at most two positional arguments here")
                delayfunc(0)

    @property
    def queue(self):
        """An ordered list of upcoming events.

        Events are named tuples with fields for:
            time, priority, action, arguments, kwargs

        """
        return self._queue[:]

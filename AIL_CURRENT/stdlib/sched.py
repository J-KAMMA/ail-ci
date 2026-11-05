"""A generally useful event scheduler class.

Derived from CPython 3.12 Lib/sched.py; PSF License, see stdlib/LICENSE-PSF.txt.

Each instance of this class manages its own queue.
No multi-threading is implied; you are supposed to hack that
yourself, or use a single instance per application.

Each instance is parametrized with two functions, one that is
supposed to return the current time, one that is supposed to
implement a delay.  You can implement real-time scheduling by
substituting time and sleep from built-in module time, or you can
implement simulated time by writing your own functions.  This can
also be used to integrate scheduling with STDWIN events; the delay
function is allowed to modify the queue.  Time can be expressed as
integers or floating point numbers, as long as it is consistent.

Events are specified by tuples (time, priority, action, argument, kwargs).
As in UNIX, lower priority numbers mean higher priority; in this
way the queue can be maintained as a priority queue.  Execution of the
event means calling the action function, passing it the argument
sequence in "argument" (remember that in Python, multiple function
arguments are be packed in a sequence) and keyword parameters in "kwargs".
The action function may be an instance method so it
has another way to reference private data (besides global variables).

This is CPython 3.12's Lib/sched.py as AIL source, used under the PSF
license (https://docs.python.org/3/license.html).  The AIL copy does not
take the threading.RLock that CPython takes, so unlike CPython it is not
safe to share one scheduler among threads.  itertools.count is replaced
by an integer attribute for the same monotonically increasing sequence
numbers.

Rewrites for the AIL compiler, with the behaviour kept:

* The queue is an ordinary list kept in (time, priority, sequence) order
  by insertion instead of a heapq of Events.  Events with equal time and
  priority come out in insertion (sequence) order, as CPython's named-tuple
  heap does, and the sorted insertion keeps that order after a cancel.
* The compiler refuses `action(*argument, **kwargs)`, so `_invoke`
  dispatches on the argument count up to 16.  Keyword arguments raise
  TypeError; that is a compiler follow-up recorded in the lab results.
* `Event` is `collections.namedtuple('Event', ...)`, so `event.time`,
  `event.priority`, `event.sequence`, `event.action`, `event.argument` and
  `event.kwargs` work and events order by the first three fields.
* `cancel` finds the event object itself rather than comparing actions:
  the compiler's general path makes two references to the same function
  compare unequal, so field-wise equality would reject a pending event.
  Each event is a distinct object, so identity removes exactly the event
  returned by `enter`/`enterabs`.
* The default time and delay functions call `time.monotonic` and
  `time.sleep`.  Those builtins are only callable, not first-class values,
  so the defaults are the module-level wrappers `_default_time` and
  `_default_delay`.
"""

import time
from collections import namedtuple

__all__ = ["scheduler"]


Event = namedtuple('Event', 'time, priority, sequence, action, argument, kwargs')

_sentinel = []


def _default_time():
    return time.monotonic()


def _default_delay(seconds):
    time.sleep(seconds)


def _invoke(action, argument, kwargs):
    if len(kwargs) != 0:
        raise TypeError("sched: keyword arguments to actions are not built by this compiler")
    count = len(argument)
    if count == 0:
        action()
    elif count == 1:
        action(argument[0])
    elif count == 2:
        action(argument[0], argument[1])
    elif count == 3:
        action(argument[0], argument[1], argument[2])
    elif count == 4:
        action(argument[0], argument[1], argument[2], argument[3])
    elif count == 5:
        action(argument[0], argument[1], argument[2], argument[3], argument[4])
    elif count == 6:
        action(argument[0], argument[1], argument[2], argument[3],
               argument[4], argument[5])
    elif count == 7:
        action(argument[0], argument[1], argument[2], argument[3],
               argument[4], argument[5], argument[6])
    elif count == 8:
        action(argument[0], argument[1], argument[2], argument[3],
               argument[4], argument[5], argument[6], argument[7])
    elif count == 9:
        action(argument[0], argument[1], argument[2], argument[3],
               argument[4], argument[5], argument[6], argument[7], argument[8])
    elif count == 10:
        action(argument[0], argument[1], argument[2], argument[3],
               argument[4], argument[5], argument[6], argument[7],
               argument[8], argument[9])
    elif count == 11:
        action(argument[0], argument[1], argument[2], argument[3],
               argument[4], argument[5], argument[6], argument[7],
               argument[8], argument[9], argument[10])
    elif count == 12:
        action(argument[0], argument[1], argument[2], argument[3],
               argument[4], argument[5], argument[6], argument[7],
               argument[8], argument[9], argument[10], argument[11])
    elif count == 13:
        action(argument[0], argument[1], argument[2], argument[3],
               argument[4], argument[5], argument[6], argument[7],
               argument[8], argument[9], argument[10], argument[11],
               argument[12])
    elif count == 14:
        action(argument[0], argument[1], argument[2], argument[3],
               argument[4], argument[5], argument[6], argument[7],
               argument[8], argument[9], argument[10], argument[11],
               argument[12], argument[13])
    elif count == 15:
        action(argument[0], argument[1], argument[2], argument[3],
               argument[4], argument[5], argument[6], argument[7],
               argument[8], argument[9], argument[10], argument[11],
               argument[12], argument[13], argument[14])
    elif count == 16:
        action(argument[0], argument[1], argument[2], argument[3],
               argument[4], argument[5], argument[6], argument[7],
               argument[8], argument[9], argument[10], argument[11],
               argument[12], argument[13], argument[14], argument[15])
    else:
        raise TypeError("sched: more than 16 action arguments are not built by this compiler")


class scheduler:
    def __init__(self, timefunc=_default_time, delayfunc=_default_delay):
        """Initialize a new instance, passing the time and delay
        functions"""
        self._queue = []
        self._sequence = 0
        self.timefunc = timefunc
        self.delayfunc = delayfunc

    def enterabs(self, time, priority, action, argument=(), kwargs=_sentinel):
        """Enter a new event in the queue at an absolute time.

        Returns an ID for the event which can be used to remove it,
        if necessary.

        """
        if kwargs is _sentinel:
            kwargs = {}

        sequence = self._sequence
        self._sequence += 1
        event = Event(time, priority, sequence, action, argument, kwargs)
        index = len(self._queue)
        while index > 0:
            other = self._queue[index - 1]
            if other.time > time:
                index -= 1
            elif other.time == time and other.priority > priority:
                index -= 1
            else:
                break
        self._queue.insert(index, event)
        return event  # The ID

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
        queue = self._queue
        index = 0
        while index < len(queue):
            if queue[index] is event:
                del queue[index]
                return
            index += 1
        raise ValueError("list.remove(x): x not in list")

    def empty(self):
        """Check whether the queue is empty."""
        return not self._queue

    def run(self, blocking=True):
        """Execute events until the queue is empty.
        If blocking is False executes the scheduled events due to
        expire soonest (if any) and then return the deadline of the
        next scheduled call in the scheduler.

        When there is a positive delay until the first event, the
        delay function is called and the event is left in the queue;
        otherwise, the event is removed from the queue and executed
        (its action function is called, passing it the argument).  If
        the delay function returns prematurely, it is simply
        restarted.

        It is legal for both the delay function and the action
        function to modify the queue or to raise an exception;
        exceptions are not caught but the scheduler's state remains
        well-defined so run() may be called again.

        A questionable hack is added to allow other threads to run:
        just after an event is executed, a delay of 0 is executed, to
        avoid monopolizing the CPU when other threads are also
        runnable.

        """
        # localize variable access to minimize overhead
        q = self._queue
        delayfunc = self.delayfunc
        timefunc = self.timefunc
        while True:
            if not q:
                break
            event = q[0]
            time = event.time
            now = timefunc()
            if time > now:
                delay = True
            else:
                delay = False
                del q[0]
            if delay:
                if not blocking:
                    return time - now
                delayfunc(time - now)
            else:
                action = event.action
                argument = event.argument
                kwargs = event.kwargs
                _invoke(action, argument, kwargs)
                delayfunc(0)  # Let other threads run

    @property
    def queue(self):
        """An ordered list of upcoming events.

        Events are named tuples with fields for:
            time, priority, action, arguments, kwargs

        """
        return self._queue[:]

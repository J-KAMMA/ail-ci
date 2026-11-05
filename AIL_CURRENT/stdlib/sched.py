"""A generally useful event scheduler class.

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
numbers, and the sentinel for the kwargs default is a shared empty tuple.

Rewrites for the AIL compiler, with the behaviour kept:

* `Event` builds a plain six-tuple `(time, priority, sequence, action,
  argument, kwargs)` instead of `collections.namedtuple`, which the compiler
  does not build here.  It orders by the first three fields, as the named
  tuple does; the fields are reached by index, so `event.time` is `event[0]`.
  A class stored in the queue, or exposed through a @property, defeats the
  compiler's inference for `timefunc`; a tuple keeps it working.
* The queue is an ordinary `queue` list kept in (time, priority, sequence)
  order by insertion instead of a heapq of Events.  Two events with equal
  time and priority come out in insertion (sequence) order, as CPython's
  named-tuple heap does.
* The compiler refuses `action(*argument, **kwargs)`, so `_invoke`
  dispatches on the argument count up to eight.  Keyword arguments raise
  TypeError; that is a compiler follow-up recorded in the lab results.
* The compiler refuses default arguments on `__init__`, so `scheduler`
  must be given both `timefunc` and `delayfunc` explicitly; CPython's
  `time.monotonic` / `time.sleep` defaults are not provided.
"""

__all__ = ["scheduler"]


def Event(time, priority, sequence, action, argument, kwargs):
    return (time, priority, sequence, action, argument, kwargs)


_sentinel = ()


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
        action(argument[0], argument[1], argument[2], argument[3], argument[4],
               argument[5])
    elif count == 7:
        action(argument[0], argument[1], argument[2], argument[3], argument[4],
               argument[5], argument[6])
    elif count == 8:
        action(argument[0], argument[1], argument[2], argument[3], argument[4],
               argument[5], argument[6], argument[7])
    else:
        raise TypeError("sched: more than eight action arguments are not built by this compiler")


class scheduler:
    def __init__(self, timefunc, delayfunc):
        """Initialize a new instance, passing the time and delay
        functions"""
        self.queue = []
        self._sequence = 0
        self.timefunc = timefunc
        self.delayfunc = delayfunc

    def enterabs(self, time, priority, action, argument=(), kwargs=_sentinel):
        """Enter a new event in the queue at an absolute time.

        Returns an ID for the event which can be used to remove it,
        if necessary.

        """
        if kwargs == _sentinel:
            kwargs = {}

        sequence = self._sequence
        self._sequence += 1
        event = Event(time, priority, sequence, action, argument, kwargs)
        index = len(self.queue)
        while index > 0:
            other = self.queue[index - 1]
            if other[0] > time:
                index -= 1
            elif other[0] == time and other[1] > priority:
                index -= 1
            else:
                break
        self.queue.insert(index, event)
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
        sequence = event[2]
        index = 0
        found = -1
        for queued in self.queue:
            if queued[2] == sequence:
                found = index
                break
            index += 1
        if found < 0:
            raise ValueError("list.remove(x): x not in list")
        del self.queue[found]

    def empty(self):
        """Check whether the queue is empty."""
        return not self.queue

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
        # and to improve thread safety
        q = self.queue
        delayfunc = self.delayfunc
        timefunc = self.timefunc
        while True:
            if not q:
                break
            event = q[0]
            time = event[0]
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
                action = event[3]
                argument = event[4]
                kwargs = event[5]
                _invoke(action, argument, kwargs)
                delayfunc(0)  # Let other threads run

"""A generator-only reference for the asyncio subset in docs/design/ASYNC.md.

This module is a *model*, not the AIL runtime: the 12 programs in lab/asyncio are
ordinary `async def` programs, and this file drives their native coroutines with
`send`/`throw` from a hand-written event loop.  No function in this file is written
with `async def` or `await`; the only suspension points are `yield` and the
generator methods behind `__await__`.

The order is CPython's:

* `call_soon` appends to one FIFO ready deque;
* `call_later` timers are a heap ordered by (deadline, insertion sequence);
* one turn moves every due timer to the end of the ready deque, then runs only the
  callbacks that were ready at the start of that turn.

The clock is virtual and starts from AIL_CLOCK when set (DIFFERENCES A28); a sleep
advances it to the next deadline.  Programs here print order, not timestamps.
"""

import heapq
import os
import re
from collections import deque
from builtins import TimeoutError

__all__ = [
    'CancelledError', 'TimeoutError', 'Future', 'Task', 'Lock', 'Event', 'Queue',
    'QueueEmpty', 'QueueFull', 'run', 'sleep', 'gather', 'wait_for', 'create_task',
    'current_task', 'all_tasks', 'get_running_loop', 'get_event_loop', 'ensure_future',
]


class CancelledError(Exception):
    pass


class QueueEmpty(Exception):
    pass


class QueueFull(Exception):
    pass


class InvalidStateError(Exception):
    pass


class _Awaitable:
    """Wrap a generator so `await obj` runs it (the model's only coroutine adapter)."""

    def __init__(self, generator):
        self._generator = generator

    def __await__(self):
        return self._generator


def _parse_clock():
    text = os.environ.get('AIL_CLOCK', '')
    if not text:
        return 0
    match = re.fullmatch(r'([+-]?)(\d+)(?:\.(\d*))?', text)
    if not match:
        raise ValueError('AIL_CLOCK must be a number of seconds since the epoch, like 1700000000.25')
    whole = int(match.group(2))
    fraction = int((match.group(3) or '').ljust(9, '0')[:9])
    value = whole * 10 ** 9 + fraction
    return -value if match.group(1) == '-' else value


class Handle:
    def __init__(self, callback, args, loop, when):
        self._callback = callback
        self._args = args
        self._loop = loop
        self._when = when
        self._cancelled = False

    def cancel(self):
        self._cancelled = True

    def cancelled(self):
        return self._cancelled

    def _run(self):
        if not self._cancelled:
            self._callback(*self._args)


class Future:
    _PENDING = 'PENDING'
    _CANCELLED = 'CANCELLED'
    _FINISHED = 'FINISHED'

    def __init__(self, loop=None):
        self._loop = loop if loop is not None else get_running_loop()
        self._state = Future._PENDING
        self._result = None
        self._exception = None
        self._callbacks = []
        self._asyncio_future_blocking = True

    def get_loop(self):
        return self._loop

    def done(self):
        return self._state != Future._PENDING

    def cancelled(self):
        return self._state == Future._CANCELLED

    def _schedule_callbacks(self):
        callbacks = self._callbacks
        self._callbacks = []
        for callback in callbacks:
            self._loop.call_soon(callback, self)

    def set_result(self, result):
        if self._state != Future._PENDING:
            raise InvalidStateError('invalid state')
        self._result = result
        self._state = Future._FINISHED
        self._schedule_callbacks()

    def set_exception(self, exception):
        if self._state != Future._PENDING:
            raise InvalidStateError('invalid state')
        self._exception = exception
        self._state = Future._FINISHED
        self._schedule_callbacks()

    def result(self):
        if self._state == Future._CANCELLED:
            raise CancelledError()
        if self._state != Future._FINISHED:
            raise InvalidStateError('Result is not ready.')
        if self._exception is not None:
            raise self._exception
        return self._result

    def exception(self):
        if self._state == Future._CANCELLED:
            raise CancelledError()
        if self._state != Future._FINISHED:
            raise InvalidStateError('Exception is not set.')
        return self._exception

    def cancel(self):
        if self._state != Future._PENDING:
            return False
        self._state = Future._CANCELLED
        self._schedule_callbacks()
        return True

    def add_done_callback(self, callback):
        if self.done():
            self._loop.call_soon(callback, self)
        else:
            self._callbacks.append(callback)

    def remove_done_callback(self, callback):
        self._callbacks = [item for item in self._callbacks if item != callback]

    def __await__(self):
        if not self.done():
            yield self
        return self.result()


class Task(Future):
    def __init__(self, coroutine, loop=None):
        Future.__init__(self, loop)
        self._coro = coroutine
        self._must_cancel = False
        self._fut_waiter = None
        self._loop._tasks.add(self)
        self._loop.call_soon(self._step)

    def get_coro(self):
        return self._coro

    def cancel(self):
        if self.done():
            return False
        if self._fut_waiter is not None:
            if self._fut_waiter.cancel():
                return True
        self._must_cancel = True
        return True

    def _wakeup(self, future):
        if self._fut_waiter is future:
            self._fut_waiter = None
            if future.cancelled():
                self._must_cancel = True
            self._loop.call_soon(self._step)

    def _step(self):
        if self.done():
            return
        previous = self._loop._current_task
        self._loop._current_task = self
        try:
            if self._must_cancel:
                self._must_cancel = False
                result = self._coro.throw(CancelledError())
            else:
                result = self._coro.send(None)
        except StopIteration as stop:
            Future.set_result(self, stop.value)
        except CancelledError:
            Future.cancel(self)
        except BaseException as error:
            Future.set_exception(self, error)
        else:
            if isinstance(result, Future) and not result.done():
                result._asyncio_future_blocking = False
                result.add_done_callback(self._wakeup)
                self._fut_waiter = result
                if self._must_cancel:
                    self._must_cancel = False
                    result.cancel()
            else:
                self._loop.call_soon(self._step)
        finally:
            self._loop._current_task = previous


class _EventLoop:
    def __init__(self):
        self._ready = deque()
        self._scheduled = []
        self._sequence = 0
        self._stopping = False
        self._closed = False
        self._tasks = set()
        self._current_task = None
        self._clock_ns = _parse_clock()

    def time(self):
        return self._clock_ns / 1e9

    def call_soon(self, callback, *args):
        handle = Handle(callback, args, self, self._clock_ns)
        self._ready.append(handle)
        return handle

    def call_at(self, when, callback, *args):
        handle = Handle(callback, args, self, int(when * 1e9))
        self._sequence += 1
        heapq.heappush(self._scheduled, (handle._when, self._sequence, handle))
        return handle

    def call_later(self, delay, callback, *args):
        return self.call_at(self.time() + delay, callback, *args)

    def create_future(self):
        return Future(self)

    def create_task(self, coroutine):
        return Task(coroutine, self)

    def _move_due_timers(self):
        while self._scheduled and self._scheduled[0][0] <= self._clock_ns:
            _, _, handle = heapq.heappop(self._scheduled)
            if not handle._cancelled:
                self._ready.append(handle)

    def _run_once(self):
        self._move_due_timers()
        if not self._ready:
            if not self._scheduled:
                return
            self._clock_ns = self._scheduled[0][0]
            self._move_due_timers()
        count = len(self._ready)
        for _ in range(count):
            handle = self._ready.popleft()
            if not handle._cancelled:
                handle._run()

    def run_forever(self):
        self._stopping = False
        while not self._stopping:
            self._run_once()
            if self._stopping:
                break

    def run_until_complete(self, future):
        future = ensure_future(future, loop=self)
        if future.done():
            return future.result()
        future.add_done_callback(self._stop)
        self.run_forever()
        return future.result()

    def _stop(self, future):
        self._stopping = True

    def _cancel_all_tasks(self):
        pending = [task for task in self._tasks if not task.done()]
        if not pending:
            return
        for task in pending:
            task.cancel()
        while True:
            pending = [task for task in self._tasks if not task.done()]
            if not pending:
                break
            before = (len(self._ready), len(self._scheduled))
            self._run_once()
            if before == (len(self._ready), len(self._scheduled)) and not self._ready:
                break
        for task in self._tasks:
            if task.done() and not task.cancelled():
                try:
                    task.exception()
                except CancelledError:
                    pass

    def close(self):
        self._closed = True


_running_loop = None


def get_running_loop():
    if _running_loop is None:
        raise RuntimeError('no running event loop')
    return _running_loop


def get_event_loop():
    return get_running_loop()


def current_task(loop=None):
    loop = loop if loop is not None else get_running_loop()
    return loop._current_task


def all_tasks(loop=None):
    loop = loop if loop is not None else get_running_loop()
    return {task for task in loop._tasks if not task.done()}


def ensure_future(awaitable, loop=None):
    if isinstance(awaitable, Future):
        return awaitable
    loop = loop if loop is not None else get_running_loop()
    if hasattr(awaitable, 'send') and hasattr(awaitable, 'throw'):
        return Task(awaitable, loop)
    if hasattr(awaitable, '__await__'):
        return Task(awaitable.__await__(), loop)
    raise TypeError('An asyncio.Future, a coroutine or an awaitable is required')


def create_task(coroutine, *, name=None):
    return get_running_loop().create_task(coroutine)


def _set_result_unless_cancelled(future, result):
    if not future.cancelled():
        future.set_result(result)


def sleep(delay, result=None):
    if delay <= 0:
        def _sleep_zero():
            yield None
            return result
        return _Awaitable(_sleep_zero())
    loop = get_running_loop()
    future = loop.create_future()
    loop.call_later(delay, _set_result_unless_cancelled, future, result)
    return future


def gather(*awaitables, return_exceptions=False):
    loop = get_running_loop()
    outer = loop.create_future()
    children = [ensure_future(item, loop=loop) for item in awaitables]
    if not children:
        outer.set_result([])
        return outer
    results = [None] * len(children)
    remaining = [len(children)]

    def _child_done(child, index):
        if outer.done():
            return
        if child.cancelled():
            if return_exceptions:
                results[index] = CancelledError()
                remaining[0] -= 1
                if remaining[0] == 0:
                    outer.set_result(results)
            else:
                outer.cancel()
            return
        error = child.exception()
        if error is not None:
            if return_exceptions:
                results[index] = error
                remaining[0] -= 1
                if remaining[0] == 0:
                    outer.set_result(results)
            else:
                outer.set_exception(error)
            return
        results[index] = child.result()
        remaining[0] -= 1
        if remaining[0] == 0:
            outer.set_result(results)

    for index, child in enumerate(children):
        child.add_done_callback(lambda done, index=index: _child_done(done, index))
    return outer


def wait_for(awaitable, timeout):
    loop = get_running_loop()
    return _Awaitable(_wait_for(awaitable, timeout, loop))


def _wait_for(awaitable, timeout, loop):
    task = ensure_future(awaitable, loop=loop)
    if timeout is None:
        while not task.done():
            yield task
        return task.result()
    if task.done():
        return task.result()
    waiter = loop.create_future()
    timed_out = [False]

    def _task_done(done):
        if not waiter.done():
            waiter.set_result(None)

    def _timeout():
        timed_out[0] = True
        if not waiter.done():
            waiter.set_result(None)

    timer = loop.call_later(timeout, _timeout)
    task.add_done_callback(_task_done)
    try:
        yield waiter
    finally:
        timer.cancel()
    if task.done():
        return task.result()
    task.cancel()
    while not task.done():
        try:
            yield task
        except CancelledError:
            pass
    raise TimeoutError()


class Event:
    def __init__(self):
        self._waiters = deque()
        self._value = False

    def is_set(self):
        return self._value

    def set(self):
        if self._value:
            return
        self._value = True
        for waiter in self._waiters:
            if not waiter.done():
                waiter.set_result(True)
        self._waiters.clear()

    def clear(self):
        self._value = False

    def _wait(self):
        if self._value:
            return True
        waiter = get_running_loop().create_future()
        self._waiters.append(waiter)
        try:
            yield waiter
        finally:
            try:
                self._waiters.remove(waiter)
            except ValueError:
                pass
        return True

    def wait(self):
        return _Awaitable(self._wait())


class Lock:
    def __init__(self):
        self._locked = False
        self._waiters = deque()

    def locked(self):
        return self._locked

    def _wake_up_first(self):
        for waiter in self._waiters:
            if not waiter.done():
                waiter.set_result(True)
                return

    def _acquire(self):
        if not self._locked and (not self._waiters or all(waiter.done() for waiter in self._waiters)):
            self._locked = True
            return True
        waiter = get_running_loop().create_future()
        self._waiters.append(waiter)
        try:
            yield waiter
        except CancelledError:
            if not self._locked:
                self._wake_up_first()
            raise
        finally:
            try:
                self._waiters.remove(waiter)
            except ValueError:
                pass
        self._locked = True
        return True

    def acquire(self):
        return _Awaitable(self._acquire())

    def release(self):
        if not self._locked:
            raise RuntimeError('Lock is not acquired.')
        self._locked = False
        self._wake_up_first()

    def __enter__(self):
        return self

    def __exit__(self, kind, value, traceback):
        self.release()


class Queue:
    def __init__(self, maxsize=0):
        self._maxsize = maxsize
        self._queue = deque()
        self._getters = deque()
        self._putters = deque()
        self._join_waiters = deque()
        self._unfinished_tasks = 0

    def qsize(self):
        return len(self._queue)

    def empty(self):
        return not self._queue

    def full(self):
        return self._maxsize > 0 and len(self._queue) >= self._maxsize

    def _wakeup_next(self, waiters):
        while waiters:
            waiter = waiters.popleft()
            if not waiter.done():
                waiter.set_result(None)
                break

    def put_nowait(self, item):
        if self.full():
            raise QueueFull()
        self._queue.append(item)
        self._unfinished_tasks += 1
        self._wakeup_next(self._getters)

    def get_nowait(self):
        if not self._queue:
            raise QueueEmpty()
        item = self._queue.popleft()
        self._wakeup_next(self._putters)
        return item

    def _put(self, item):
        while self.full():
            putter = get_running_loop().create_future()
            self._putters.append(putter)
            try:
                yield putter
            except CancelledError:
                putter.cancel()
                try:
                    self._putters.remove(putter)
                except ValueError:
                    pass
                raise
        self.put_nowait(item)

    def put(self, item):
        return _Awaitable(self._put(item))

    def _get(self):
        while self.empty():
            getter = get_running_loop().create_future()
            self._getters.append(getter)
            try:
                yield getter
            except CancelledError:
                getter.cancel()
                try:
                    self._getters.remove(getter)
                except ValueError:
                    pass
                raise
        return self.get_nowait()

    def get(self):
        return _Awaitable(self._get())

    def task_done(self):
        if self._unfinished_tasks <= 0:
            raise ValueError('task_done() called too many times')
        self._unfinished_tasks -= 1
        if self._unfinished_tasks == 0:
            self._wakeup_next(self._join_waiters)

    def _join(self):
        while self._unfinished_tasks > 0:
            waiter = get_running_loop().create_future()
            self._join_waiters.append(waiter)
            try:
                yield waiter
            except CancelledError:
                waiter.cancel()
                try:
                    self._join_waiters.remove(waiter)
                except ValueError:
                    pass
                raise

    def join(self):
        return _Awaitable(self._join())


def run(main):
    global _running_loop
    loop = _EventLoop()
    _running_loop = loop
    try:
        return loop.run_until_complete(main)
    finally:
        loop._cancel_all_tasks()
        loop.close()
        _running_loop = None

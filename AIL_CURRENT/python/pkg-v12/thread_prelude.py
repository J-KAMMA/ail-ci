# -*- coding: utf-8 -*-
"""thread_prelude.py -- the Python source threadlib.py injects for `threading`, `queue` and
`concurrent.futures` (stage G12 in docs/design/GENERAL_PURPOSE.md, threads).

It is compiled by the general path only, together with the program. Every class here runs under the
one interpreter lock of threadrt.py, so a field read and the field write after it cannot be split by
another thread unless the code between them waits or ends a loop iteration (the only places the lock
changes hands). Waiting uses one primitive pair:

    g = _ail_th_gen()        the notify generation now
    _ail_th_wait(g, secs)    let the lock go and sleep until the generation moves past g (secs < 0: no
                             time limit); returns whether it moved
    _ail_th_notify()         move the generation and wake every waiter

so every wait is `while not <condition>: g = gen(); if <condition>: break; wait(g, remaining)` and a
wake-up between the test and the wait cannot be lost. A Condition hands each waiter its own flag (as
CPython's Condition hands each waiter its own lock), so notify(n) wakes exactly n waiters.
"""

PRELUDE = r'''
_ail_th_count = 0
_ail_th_pool_count = 0
_ail_th_active = {}
_ail_th_mainobj = None
_ail_th_pools = []


class _AilQueueEmpty(Exception):
    pass


class _AilQueueFull(Exception):
    pass


class _AilCancelledError(Exception):
    pass


def _ail_th_deadline(timeout):
    if timeout is None:
        return -1.0
    if timeout < 0:
        return -1.0
    return _ail_th_now() + timeout


def _ail_th_left(deadline):
    if deadline < 0:
        return -1.0
    r = deadline - _ail_th_now()
    if r <= 0:
        return 0.0
    return r


class _AilThread:
    def __init__(self, group=None, target=None, name=None, args=None, kwargs=None, daemon=None):
        global _ail_th_count
        if name is None:
            _ail_th_count += 1
            name = "Thread-" + str(_ail_th_count)
            if target is not None:
                name = name + " (" + target._ail_name + ")"
        else:
            name = str(name)
        self.name = name
        self._target = target
        if daemon is None:
            daemon = _ail_current_thread().daemon
        self.daemon = bool(daemon)
        self._started = False
        self.ident = None
        self.native_id = None

    def start(self):
        if self._started:
            raise RuntimeError("threads can only be started once")
        self._started = True
        self.ident = _ail_th_start(self, self.daemon)
        self.native_id = self.ident
        _ail_th_active[self.ident] = self

    def run(self):
        if self._target is not None:
            self._target.call()

    def join(self, timeout=None):
        if not self._started:
            raise RuntimeError("cannot join thread before it is started")
        if self.ident == _ail_th_ident():
            raise RuntimeError("cannot join current thread")
        deadline = _ail_th_deadline(timeout)
        while not _ail_th_done(self.ident):
            g = _ail_th_gen()
            if _ail_th_done(self.ident):
                break
            r = _ail_th_left(deadline)
            if r == 0.0:
                break
            _ail_th_wait(g, r)

    def is_alive(self):
        if not self._started:
            return False
        return not _ail_th_done(self.ident)


def _ail_thread_body(t):
    try:
        t.run()
    except Exception as e:
        _ail_th_report(t.name, e)
    if t.ident in _ail_th_active:
        del _ail_th_active[t.ident]


def _ail_main_thread():
    global _ail_th_mainobj
    if _ail_th_mainobj is None:
        m = _AilThread(None, None, "MainThread", None, None, False)
        m._started = True
        m.ident = 1
        m.native_id = 1
        _ail_th_mainobj = m
    return _ail_th_mainobj


def _ail_current_thread():
    me = _ail_th_ident()
    if me in _ail_th_active:
        return _ail_th_active[me]
    return _ail_main_thread()


def _ail_active_count():
    return len(_ail_th_active) + 1


def _ail_enumerate():
    out = [_ail_main_thread()]
    for k in _ail_th_active:
        out.append(_ail_th_active[k])
    return out


class _AilLock:
    def __init__(self):
        self._locked = False

    def acquire(self, blocking=True, timeout=-1):
        if not blocking:
            if timeout != -1:
                raise ValueError("can't specify a timeout for a non-blocking call")
            if self._locked:
                return False
            self._locked = True
            return True
        if timeout < 0 and timeout != -1:
            raise ValueError("timeout value must be a non-negative number")
        if not self._locked:
            self._locked = True
            return True
        deadline = _ail_th_deadline(timeout)
        while True:
            g = _ail_th_gen()
            if not self._locked:
                self._locked = True
                return True
            r = _ail_th_left(deadline)
            if r == 0.0:
                return False
            _ail_th_wait(g, r)

    def release(self):
        if not self._locked:
            raise RuntimeError("release unlocked lock")
        self._locked = False
        _ail_th_notify()

    def locked(self):
        return self._locked

    def _is_owned(self):
        return self._locked

    def _release_save(self):
        self.release()
        return 0

    def _acquire_restore(self, saved):
        self.acquire()

    def _ail_enter(self):
        return self.acquire()

    def _ail_exit(self):
        self.release()


class _AilRLock:
    def __init__(self):
        self._owner = 0
        self._count = 0

    def acquire(self, blocking=True, timeout=-1):
        me = _ail_th_ident()
        if self._owner == me:
            self._count += 1
            return True
        if not blocking:
            if timeout != -1:
                raise ValueError("can't specify a timeout for a non-blocking call")
            if self._owner != 0:
                return False
            self._owner = me
            self._count = 1
            return True
        if timeout < 0 and timeout != -1:
            raise ValueError("timeout value must be a non-negative number")
        deadline = _ail_th_deadline(timeout)
        while True:
            g = _ail_th_gen()
            if self._owner == 0:
                self._owner = me
                self._count = 1
                return True
            r = _ail_th_left(deadline)
            if r == 0.0:
                return False
            _ail_th_wait(g, r)

    def release(self):
        if self._owner != _ail_th_ident():
            raise RuntimeError("cannot release un-acquired lock")
        self._count -= 1
        if self._count == 0:
            self._owner = 0
            _ail_th_notify()

    def _is_owned(self):
        return self._owner == _ail_th_ident()

    def _release_save(self):
        if self._owner != _ail_th_ident():
            raise RuntimeError("cannot release un-acquired lock")
        saved = self._count
        self._count = 0
        self._owner = 0
        _ail_th_notify()
        return saved

    def _acquire_restore(self, saved):
        self.acquire()
        self._count = saved

    def _ail_enter(self):
        return self.acquire()

    def _ail_exit(self):
        self.release()


class _AilWaiter:
    def __init__(self):
        self.flag = False


class _AilCondition:
    def __init__(self, lock=None):
        if lock is None:
            lock = _AilRLock()
        self._lock = lock
        self._waiters = []

    def acquire(self, blocking=True, timeout=-1):
        return self._lock.acquire(blocking, timeout)

    def release(self):
        self._lock.release()

    def _ail_enter(self):
        return self._lock.acquire()

    def _ail_exit(self):
        self._lock.release()

    def wait(self, timeout=None):
        if not self._lock._is_owned():
            raise RuntimeError("cannot wait on un-acquired lock")
        w = _AilWaiter()
        self._waiters.append(w)
        saved = self._lock._release_save()
        deadline = _ail_th_deadline(timeout)
        while not w.flag:
            g = _ail_th_gen()
            if w.flag:
                break
            r = _ail_th_left(deadline)
            if r == 0.0:
                break
            _ail_th_wait(g, r)
        self._lock._acquire_restore(saved)
        if not w.flag:
            i = 0
            while i < len(self._waiters):
                if self._waiters[i] is w:
                    self._waiters.pop(i)
                    break
                i += 1
            return False
        return True

    def notify(self, n=1):
        if not self._lock._is_owned():
            raise RuntimeError("cannot notify on un-acquired lock")
        k = 0
        while k < n and len(self._waiters) > 0:
            w = self._waiters.pop(0)
            w.flag = True
            k += 1
        if k > 0:
            _ail_th_notify()

    def notify_all(self):
        self.notify(len(self._waiters))


class _AilSemaphore:
    def __init__(self, value=1):
        if value < 0:
            raise ValueError("semaphore initial value must be >= 0")
        self._value = value
        self._bound = -1

    def acquire(self, blocking=True, timeout=None):
        if not blocking and timeout is not None:
            raise ValueError("can't specify timeout for non-blocking acquire")
        if self._value > 0:
            self._value -= 1
            return True
        if not blocking:
            return False
        deadline = _ail_th_deadline(timeout)
        while True:
            g = _ail_th_gen()
            if self._value > 0:
                self._value -= 1
                return True
            r = _ail_th_left(deadline)
            if r == 0.0:
                return False
            _ail_th_wait(g, r)

    def release(self, n=1):
        if n < 1:
            raise ValueError("n must be one or more")
        if self._bound >= 0 and self._value + n > self._bound:
            raise ValueError("Semaphore released too many times")
        self._value += n
        _ail_th_notify()

    def _ail_enter(self):
        return self.acquire()

    def _ail_exit(self):
        self.release()


class _AilBoundedSemaphore(_AilSemaphore):
    def __init__(self, value=1):
        super().__init__(value)
        self._bound = value


class _AilEvent:
    def __init__(self):
        self._flag = False

    def is_set(self):
        return self._flag

    def set(self):
        self._flag = True
        _ail_th_notify()

    def clear(self):
        self._flag = False

    def wait(self, timeout=None):
        deadline = _ail_th_deadline(timeout)
        while not self._flag:
            g = _ail_th_gen()
            if self._flag:
                break
            r = _ail_th_left(deadline)
            if r == 0.0:
                break
            _ail_th_wait(g, r)
        return self._flag


class _AilQueue:
    def __init__(self, maxsize=0):
        self.maxsize = maxsize
        self._items = []
        self._head = 0
        self.unfinished_tasks = 0
        self._lifo = False

    def qsize(self):
        return len(self._items) - self._head

    def empty(self):
        return len(self._items) - self._head == 0

    def full(self):
        if self.maxsize <= 0:
            return False
        return len(self._items) - self._head >= self.maxsize

    def put(self, item, block=True, timeout=None):
        if self.maxsize > 0:
            if not block:
                if self.full():
                    raise _AilQueueFull()
            else:
                if timeout is not None and timeout < 0:
                    raise ValueError("'timeout' must be a non-negative number")
                deadline = _ail_th_deadline(timeout)
                while self.full():
                    g = _ail_th_gen()
                    if not self.full():
                        break
                    r = _ail_th_left(deadline)
                    if r == 0.0:
                        raise _AilQueueFull()
                    _ail_th_wait(g, r)
        self._put(item)
        self.unfinished_tasks += 1
        _ail_th_notify()

    def _put(self, item):
        self._items.append(item)

    def _get(self):
        if self._lifo:
            return self._items.pop()
        item = self._items[self._head]
        self._items[self._head] = None
        self._head += 1
        if self._head >= 64 and self._head * 2 >= len(self._items):
            self._items = self._items[self._head:]
            self._head = 0
        return item

    def get(self, block=True, timeout=None):
        if not block:
            if self.empty():
                raise _AilQueueEmpty()
        else:
            if timeout is not None and timeout < 0:
                raise ValueError("'timeout' must be a non-negative number")
            deadline = _ail_th_deadline(timeout)
            while self.empty():
                g = _ail_th_gen()
                if not self.empty():
                    break
                r = _ail_th_left(deadline)
                if r == 0.0:
                    raise _AilQueueEmpty()
                _ail_th_wait(g, r)
        item = self._get()
        if self.maxsize > 0:
            _ail_th_notify()
        return item

    def put_nowait(self, item):
        self.put(item, False)

    def get_nowait(self):
        return self.get(False)

    def task_done(self):
        if self.unfinished_tasks <= 0:
            raise ValueError("task_done() called too many times")
        self.unfinished_tasks -= 1
        if self.unfinished_tasks == 0:
            _ail_th_notify()

    def join(self):
        while self.unfinished_tasks > 0:
            g = _ail_th_gen()
            if self.unfinished_tasks == 0:
                break
            _ail_th_wait(g, -1.0)


class _AilLifoQueue(_AilQueue):
    # (a flag, not an override of _get: a method's `self._get()` is bound to its own class here)
    def __init__(self, maxsize=0):
        super().__init__(maxsize)
        self._lifo = True


class _AilFuture:
    def __init__(self):
        self._state = 0
        self._result = None
        self._exc = None

    def done(self):
        return self._state >= 2

    def running(self):
        return self._state == 1

    def cancelled(self):
        return self._state == 3

    def cancel(self):
        if self._state == 1 or self._state == 2:
            return False
        self._state = 3
        _ail_th_notify()
        return True

    def _wait(self, timeout):
        deadline = _ail_th_deadline(timeout)
        while self._state < 2:
            g = _ail_th_gen()
            if self._state >= 2:
                break
            r = _ail_th_left(deadline)
            if r == 0.0:
                raise TimeoutError()
            _ail_th_wait(g, r)

    def result(self, timeout=None):
        self._wait(timeout)
        if self._state == 3:
            raise _AilCancelledError()
        if self._exc is not None:
            _ail_th_raise(self._exc)
        return self._result

    def exception(self, timeout=None):
        self._wait(timeout)
        if self._state == 3:
            raise _AilCancelledError()
        return self._exc


class _AilWork:
    def __init__(self, call, fut, mode, a, b):
        self.call = call
        self.fut = fut
        self.mode = mode
        self.a = a
        self.b = b


class _AilPoolRun:
    def __init__(self, pool):
        self._ail_name = "_worker"
        self.pool = pool

    def call(self):
        _ail_pool_worker(self.pool)

    def call1(self, x):
        return None

    def call2(self, x, y):
        return None


def _ail_pool_worker(pool):
    while True:
        w = pool._q.get()
        if w is None:
            return
        f = w.fut
        if f._state == 0:
            f._state = 1
            try:
                if w.mode == 0:
                    f._result = w.call.call()
                elif w.mode == 1:
                    f._result = w.call.call1(w.a)
                else:
                    f._result = w.call.call2(w.a, w.b)
            except Exception as e:
                f._exc = e
            f._state = 2
            _ail_th_notify()
        w = None
        f = None
        pool._idle += 1


class _AilPool:
    def __init__(self, max_workers=None, thread_name_prefix=""):
        global _ail_th_pool_count
        if max_workers is None:
            max_workers = min(32, _ail_th_cpus() + 4)
        if max_workers <= 0:
            raise ValueError("max_workers must be greater than 0")
        self._max_workers = max_workers
        self._q = _AilQueue()
        self._threads = []
        self._idle = 0
        self._shutdown = False
        if not thread_name_prefix:
            thread_name_prefix = "ThreadPoolExecutor-" + str(_ail_th_pool_count)
            _ail_th_pool_count += 1
        self._prefix = thread_name_prefix
        _ail_th_pools.append(self)

    def _submit1(self, call, mode, a, b):
        if self._shutdown:
            raise RuntimeError("cannot schedule new futures after shutdown")
        f = _AilFuture()
        self._q.put(_AilWork(call, f, mode, a, b))
        if self._idle > 0:
            self._idle -= 1
        elif len(self._threads) < self._max_workers:
            t = _AilThread(None, _AilPoolRun(self), self._prefix + "_" + str(len(self._threads)), None, None, False)
            t.start()
            self._threads.append(t)
        return f

    def _submit(self, call):
        return self._submit1(call, 0, None, None)

    def _map(self, call, a, b=None, timeout=None):
        futs = []
        if b is None:
            for x in a:
                futs.append(self._submit1(call, 1, x, None))
        else:
            bl = list(b)
            i = 0
            for x in a:
                if i >= len(bl):
                    break
                futs.append(self._submit1(call, 2, x, bl[i]))
                i += 1
        deadline = _ail_th_deadline(timeout)
        out = []
        for f in futs:
            if deadline < 0:
                out.append(f.result())
            else:
                out.append(f.result(_ail_th_left(deadline)))
        return out

    def shutdown(self, wait=True, cancel_futures=False):
        if not self._shutdown:
            self._shutdown = True
            if cancel_futures:
                for w in self._q._items:
                    if w is not None:
                        w.fut.cancel()
            for t in self._threads:
                self._q.put(None)
        if wait:
            for t in self._threads:
                t.join()

    def _ail_enter(self):
        return self

    def _ail_exit(self):
        self.shutdown(True)


def _ail_as_completed(fs, timeout=None):
    pending = list(fs)
    total = len(pending)
    out = []
    deadline = _ail_th_deadline(timeout)
    while len(pending) > 0:
        g = _ail_th_gen()
        keep = []
        for f in pending:
            if f._state >= 2:
                out.append(f)
            else:
                keep.append(f)
        pending = keep
        if len(pending) > 0:
            r = _ail_th_left(deadline)
            if r == 0.0:
                raise TimeoutError(str(len(pending)) + " (of " + str(total) + ") futures unfinished")
            _ail_th_wait(g, r)
    return out


def _ail_th_atexit():
    for p in _ail_th_pools:
        p.shutdown(False)
'''

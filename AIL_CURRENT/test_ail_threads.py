"""G12: threads (threading, queue, concurrent.futures.ThreadPoolExecutor), compared with CPython 3.12.

The owner's decision (GENERAL_PURPOSE.md Q9): one interpreter lock with CPython's GIL semantics. Only one
thread runs AIL code at a time; the lock changes hands at loop back-edges (after another thread has waited
5 ms), at waits (join, Lock.acquire, Queue.get, Event.wait, Condition.wait, Future.result) and around
time.sleep. Design note: docs/design/G12_THREADS.md.

Output order between threads is not deterministic in CPython either, so every program here prints only
what is: results joined before printing, collected in a list and sorted, counted under a Lock, or read by
one consumer from a queue. Each program is run by CPython and by the compiled program; stdout and the exit
status must be the same.

* Differential programs: Lock / RLock / Condition / Semaphore / BoundedSemaphore / Event, Queue (FIFO,
  LIFO, bounded, task_done / join, timeouts, Empty / Full), Thread (target with args and kwargs, bound
  methods, subclasses with run(), names, daemon, is_alive, join timeouts, start twice), executors (submit,
  map over one and two iterables, as_completed, exceptions through result(), with-shutdown, bound methods,
  keyword arguments), preemption (a busy wait on a flag another thread sets), sleep concurrency, an
  exception in a thread (stderr, exit 0), sys.exit in a thread, the main thread raising while threads run.
* Stress: many threads on one counter under a Lock (exact), producers and consumers on one Queue (exact
  sum), an executor with many small tasks; each run several times.
* Sanitizers: one stress program built with -fsanitize=thread and one with -fsanitize=address,undefined.
* Refusals by name: lambda and nested-function targets, threading.local / Timer / Barrier,
  queue.PriorityQueue, ProcessPoolExecutor, Condition.wait_for, add_done_callback, imports inside a
  function, `from threading import *`; the typed path alone (AIL_NO_GENERAL=1) names the general path.
* No cost elsewhere: a program that does not import the three modules is returned by the source pass as
  written and its C has nothing of the thread runtime; a threaded program's C has the back-edge check.
"""
import os
import platform
import random
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent
CLI = str(ROOT / "ail_chatgpt.py")
CORE = ROOT / "python" / "pkg-v12"


def oracle_env():
    env = dict(os.environ, PYTHONUTF8="1")
    env.pop("PYTHONPATH", None)
    return env


def build(src, exe, typed_only=False, cwd=None):
    env = dict(os.environ)
    for key in ("AIL_NO_GENERAL", "AIL_TARGET", "AIL_IR"):
        env.pop(key, None)
    if typed_only:
        env["AIL_NO_GENERAL"] = "1"
    return subprocess.run([sys.executable, "-B", CLI, "compile", str(src), "-o", str(exe)], cwd=cwd,
                          capture_output=True, text=True, timeout=900, env=env)


class Base(unittest.TestCase):
    def compare(self, name, text, rc=0, runs=1, stderr_has=()):
        """CPython's stdout and exit status equal the compiled program's (built once, run `runs` times)."""
        with tempfile.TemporaryDirectory(prefix="ail-threads-") as tmp:
            src = Path(tmp) / (name + ".py")
            src.write_text(text, encoding="utf-8")
            want = subprocess.run([sys.executable, str(src)], cwd=tmp, capture_output=True, timeout=300,
                                  env=oracle_env())
            self.assertEqual(want.returncode, rc, want.stderr.decode())
            self.assertTrue(want.stdout, "the program prints nothing")
            exe = Path(tmp) / ("exe" + (".exe" if os.name == "nt" else ""))
            built = build(src, exe, cwd=tmp)
            self.assertEqual(built.returncode, 0, built.stderr[-3000:])
            self.assertIn("general path", built.stderr)
            for run in range(runs):
                got = subprocess.run([str(exe)], cwd=tmp, capture_output=True, timeout=300, env=oracle_env())
                self.assertEqual(got.returncode, rc, "run %d: %s" % (run, got.stderr.decode()[-2000:]))
                if got.stdout != want.stdout:
                    a = want.stdout.decode("utf-8", "replace").split("\n")
                    b = got.stdout.decode("utf-8", "replace").split("\n")
                    for i in range(max(len(a), len(b))):
                        x = a[i] if i < len(a) else "<none>"
                        y = b[i] if i < len(b) else "<none>"
                        if x != y:
                            self.fail("run %d line %d: CPython %r, AIL %r" % (run, i + 1, x[:300], y[:300]))
                self.assertEqual(got.stdout, want.stdout)
                for needle in stderr_has:
                    self.assertIn(needle, got.stderr.decode("utf-8", "replace"))

    def refused(self, text, *needles, typed_only=False):
        with tempfile.TemporaryDirectory(prefix="ail-threads-") as tmp:
            src = Path(tmp) / "prog.py"
            src.write_text(text, encoding="utf-8")
            built = build(src, Path(tmp) / "exe", typed_only=typed_only, cwd=tmp)
            self.assertNotEqual(built.returncode, 0, "accepted:\n" + text)
            self.assertFalse((Path(tmp) / "exe").exists())
            for needle in needles:
                self.assertIn(needle, built.stderr)


# ------------------------------------------------------------------------------------- programs

LOCK_COUNTER = r'''
import threading

counter = 0
lock = threading.Lock()
done = []


def worker(n, tag):
    global counter
    for _ in range(n):
        with lock:
            counter += 1
    with lock:
        done.append(tag)


def main():
    ts = [threading.Thread(target=worker, args=(N, "w%d" % k)) for k in range(T)]
    for t in ts:
        t.start()
    for t in ts:
        t.join()
    print(counter, counter == N * T)
    print(sorted(done))
    print([t.is_alive() for t in ts])


main()
'''

PRIMITIVES = r'''
import threading
import time


class Counter:
    def __init__(self):
        self.n = 0
        self.lock = threading.RLock()

    def bump(self, k):
        for _ in range(k):
            with self.lock:
                with self.lock:
                    self.n += 1


active = [0]
peak = [0]
guard = threading.Lock()
sem = threading.BoundedSemaphore(3)


def limited(i, out):
    with sem:
        with guard:
            active[0] += 1
            if active[0] > peak[0]:
                peak[0] = active[0]
        time.sleep(0.002)
        with guard:
            active[0] -= 1
            out.append(i)


def waiter(ev, cond, box):
    ev.wait()
    with cond:
        while not box:
            cond.wait()
        box.append("seen")


def main():
    c = Counter()
    ts = [threading.Thread(target=c.bump, args=(400,)) for _ in range(5)]
    for t in ts:
        t.start()
    for t in ts:
        t.join()
    print("rlock", c.n)
    out = []
    ls = [threading.Thread(target=limited, args=(i, out)) for i in range(12)]
    for t in ls:
        t.start()
    for t in ls:
        t.join()
    print("semaphore", sorted(out), peak[0] <= 3, active[0])
    try:
        sem.release()
    except ValueError as e:
        print("ValueError", e)
    ev = threading.Event()
    cond = threading.Condition()
    box = []
    w = threading.Thread(target=waiter, args=(ev, cond, box))
    w.start()
    print("event", ev.is_set(), ev.wait(0.001))
    ev.set()
    with cond:
        box.append("go")
        cond.notify_all()
    w.join()
    print("cond", box, ev.wait())
    s = threading.Semaphore(2)
    print(s.acquire(), s.acquire(), s.acquire(blocking=False), s.acquire(timeout=0.01))
    s.release(2)
    lk = threading.Lock()
    print(lk.acquire(), lk.locked(), lk.acquire(timeout=0.01), lk.acquire(False))
    lk.release()
    with lk as got:
        print("with as", got, lk.locked())
    print(lk.locked())
    try:
        lk.release()
    except RuntimeError as e:
        print("RuntimeError", e)
    r = threading.RLock()
    try:
        r.release()
    except RuntimeError as e:
        print("RuntimeError", e)
    cv = threading.Condition(threading.Lock())
    with cv:
        print("timed wait", cv.wait(0.01))
    try:
        cv.notify()
    except RuntimeError as e:
        print("RuntimeError", e)


main()
'''

QUEUES = r'''
import queue
import threading


class Worker(threading.Thread):
    def __init__(self, q, out, idx):
        super().__init__()
        self.q = q
        self.out = out
        self.idx = idx

    def run(self):
        while True:
            item = self.q.get()
            if item is None:
                self.q.task_done()
                break
            self.out.append(item * 10)
            self.q.task_done()


def producer(q, lo, hi):
    for i in range(lo, hi):
        q.put(i)


def consumer(q, out, lock):
    while True:
        x = q.get()
        if x is None:
            break
        with lock:
            out.append(x)


def main():
    q = queue.Queue()
    out = []
    ws = [Worker(q, out, i) for i in range(3)]
    for w in ws:
        w.start()
    for i in range(40):
        q.put(i)
    for w in ws:
        q.put(None)
    q.join()
    for w in ws:
        w.join()
    print("workers", sorted(out) == [i * 10 for i in range(40)], len(out), q.empty(), q.qsize())

    bq = queue.Queue(maxsize=3)
    got = []
    lock = threading.Lock()
    ps = [threading.Thread(target=producer, args=(bq, k * 100, k * 100 + 50)) for k in range(4)]
    cs = [threading.Thread(target=consumer, args=(bq, got, lock)) for k in range(2)]
    for t in ps + cs:
        t.start()
    for t in ps:
        t.join()
    for t in cs:
        bq.put(None)
    for t in cs:
        t.join()
    print("bounded", len(got), sum(got), sorted(got)[:3], bq.full(), bq.maxsize)

    single = queue.Queue()
    order = []
    p = threading.Thread(target=producer, args=(single, 0, 30))
    p.start()
    for _ in range(30):
        order.append(single.get())
    p.join()
    print("fifo", order == list(range(30)))

    lq = queue.LifoQueue()
    for i in range(5):
        lq.put(i)
    print("lifo", [lq.get() for _ in range(5)])
    sq = queue.SimpleQueue()
    sq.put("a")
    print("simple", sq.get(), sq.empty())
    e = queue.Queue()
    try:
        e.get(timeout=0.01)
    except queue.Empty:
        print("Empty after timeout")
    try:
        e.get_nowait()
    except queue.Empty:
        print("Empty now")
    f = queue.Queue(1)
    f.put_nowait(1)
    try:
        f.put(2, timeout=0.01)
    except queue.Full:
        print("Full after timeout")
    try:
        f.put_nowait(3)
    except queue.Full:
        print("Full now")
    try:
        f.task_done()
        f.task_done()
    except ValueError as err:
        print("ValueError", err)


main()
'''

EXECUTORS = r'''
from concurrent.futures import ThreadPoolExecutor, as_completed
import concurrent.futures
import threading


def square(x):
    return x * x


def add(a, b):
    return a + b


def scaled(x, factor=1, offset=0):
    return x * factor + offset


def boom(x):
    if x % 4 == 3:
        raise ValueError("bad %d" % x)
    return x


class Acc:
    def __init__(self):
        self.total = 0
        self.lock = threading.Lock()

    def take(self, x):
        with self.lock:
            self.total += x
        return x + 1


def main():
    with ThreadPoolExecutor(max_workers=4) as ex:
        futs = [ex.submit(square, i) for i in range(25)]
        print([f.result() for f in futs])
        print(list(ex.map(square, range(12))))
        print(list(ex.map(add, [1, 2, 3], [10, 20, 30, 40])))
        print(sorted(f.result() for f in as_completed([ex.submit(square, k) for k in range(6)])))
        print(ex.submit(scaled, 3, factor=5, offset=2).result(), ex.submit(scaled, 4).result())
        caught = []
        for f in [ex.submit(boom, i) for i in range(8)]:
            try:
                caught.append(f.result())
            except ValueError as e:
                caught.append(str(e))
        print(caught)
        bad = ex.submit(boom, 3)
        print(bad.exception() is not None, bad.done(), bad.cancelled())
        acc = Acc()
        print(sorted(ex.map(acc.take, range(10))), acc.total)
        try:
            list(ex.map(boom, range(6)))
        except ValueError as e:
            print("map raised", e)
    ex2 = concurrent.futures.ThreadPoolExecutor(2)
    fs = [ex2.submit(add, i, i) for i in range(10)]
    ex2.shutdown(wait=True)
    print([f.result() for f in fs], all(f.done() for f in fs))
    try:
        ex2.submit(square, 1)
    except RuntimeError as e:
        print("RuntimeError", e)
    names = []
    lock = threading.Lock()
    with ThreadPoolExecutor(max_workers=2, thread_name_prefix="pool") as ex3:
        for _ in range(4):
            ex3.submit(record_name, names, lock).result()
    print(sorted(set(names))[0] == "pool_0")
    leftover = ThreadPoolExecutor(3)
    late = [leftover.submit(square, i) for i in range(5)]
    print("not joined", [f.result() for f in late])


def record_name(names, lock):
    with lock:
        names.append(threading.current_thread().name)


main()
'''

THREADS = r'''
import sys
import threading
import time

flag = [False]
seen = []


def busy():
    n = 0
    while not flag[0]:
        n += 1
    seen.append("busy done")


def sleeper(i, out):
    time.sleep(0.2)
    out.append(i)


def named(out, lock):
    with lock:
        out.append(threading.current_thread().name)


def kw(out, a, b=0, c=0):
    out.append(a + 10 * b + 100 * c)


def quits():
    sys.exit(3)


def fails(x):
    raise KeyError(x)


def forever():
    while True:
        time.sleep(0.05)


class Job(threading.Thread):
    def __init__(self, k, out):
        threading.Thread.__init__(self, name="job%d" % k)
        self.k = k
        self.out = out

    def run(self):
        self.out.append(self.k * self.k)


def main():
    t = threading.Thread(target=busy)
    t.start()
    k = 0
    for i in range(200000):
        k += i
    flag[0] = True
    t.join()
    print(seen, k)
    out = []
    start = time.time()
    ss = [threading.Thread(target=sleeper, args=(i, out)) for i in range(8)]
    for s in ss:
        s.start()
    for s in ss:
        s.join()
    print(sorted(out), time.time() - start < 1.5)
    names = []
    lock = threading.Lock()
    ns = [threading.Thread(target=named, args=(names, lock)) for _ in range(3)]
    ns.append(threading.Thread(target=named, args=(names, lock), name="custom"))
    ns.append(threading.Thread(None, named, "positional", (names, lock)))
    print([x.name.split("-")[0] for x in ns], ns[0].name.endswith("(named)"))
    for x in ns:
        x.start()
    for x in ns:
        x.join()
    print(len(names), "custom" in names, "positional" in names, threading.current_thread().name)
    vals = []
    ks = [threading.Thread(target=kw, args=(vals, 1), kwargs={"b": 2, "c": 3}),
          threading.Thread(target=kw, args=(vals, 4, 5)), threading.Thread(target=kw, kwargs={"out": vals, "a": 7})]
    for x in ks:
        x.start()
        x.join()
    print(vals)
    jobs = [Job(i, []) for i in range(4)]
    for j in jobs:
        j.start()
    for j in jobs:
        j.join()
    print([j.out for j in jobs], [j.name for j in jobs], jobs[0].daemon)
    q = threading.Thread(target=quits)
    q.start()
    q.join()
    print("after sys.exit in a thread", q.is_alive())
    f = threading.Thread(target=fails, args=("k",), name="failer")
    f.start()
    f.join()
    print("after failure", f.is_alive())
    d = threading.Thread(target=forever, daemon=True)
    d.start()
    print("daemon", d.daemon, d.is_alive())
    slow = threading.Thread(target=sleeper, args=(99, out))
    slow.start()
    slow.join(timeout=0.01)
    print("timed join", slow.is_alive())
    slow.join()
    print("joined", slow.is_alive(), out[-1])
    try:
        slow.start()
    except RuntimeError as e:
        print("RuntimeError", e)
    try:
        threading.Thread(target=busy).join()
    except RuntimeError as e:
        print("RuntimeError", e)
    try:
        threading.current_thread().join()
    except RuntimeError as e:
        print("RuntimeError", e)
    print(threading.active_count() >= 2, threading.main_thread().name, threading.get_ident() > 0)


main()
'''

LATE = r'''
import threading
import time


def late():
    time.sleep(0.1)
    print("late thread finished")


def main():
    print("main starts")
    threading.Thread(target=late).start()
    raise ValueError("main failed")


main()
'''

STRESS_QUEUE = r'''
import queue
import threading

P = 6
C = 5
N = 3000


def produce(q, k):
    for i in range(N):
        q.put(k * N + i)


def consume(q, totals, counts, idx):
    while True:
        x = q.get()
        if x < 0:
            q.task_done()
            return
        totals[idx] += x
        counts[idx] += 1
        q.task_done()


def main():
    q = queue.Queue(maxsize=50)
    totals = [0] * C
    counts = [0] * C
    ps = [threading.Thread(target=produce, args=(q, k)) for k in range(P)]
    cs = [threading.Thread(target=consume, args=(q, totals, counts, i)) for i in range(C)]
    for t in cs + ps:
        t.start()
    for t in ps:
        t.join()
    for _ in cs:
        q.put(-1)
    q.join()
    for t in cs:
        t.join()
    n = P * N
    print(sum(counts), sum(totals), sum(totals) == n * (n - 1) // 2)


main()
'''

STRESS_POOL = r'''
from concurrent.futures import ThreadPoolExecutor
import threading

hits = {}
lock = threading.Lock()


def task(i):
    s = 0
    for j in range(i % 50):
        s += j
    with lock:
        hits[i % 7] = hits.get(i % 7, 0) + 1
    return s


def main():
    with ThreadPoolExecutor(max_workers=8) as ex:
        res = list(ex.map(task, range(4000)))
        more = [ex.submit(task, i) for i in range(1000)]
        res2 = [f.result() for f in more]
    print(sum(res), sum(res2), sorted(hits.items()))


main()
'''


FILES_AND_PROCESSES = r'''
import os
import subprocess
import threading


def job(k, out, lock):
    name = "file_%d.txt" % k
    with open(name, "w") as f:
        for i in range(50):
            f.write("line %d %d\n" % (k, i))
    with open(name) as f:
        n = len(f.read().splitlines())
    r = subprocess.run([@PY@, "-c", "print('child', %d)" % k], capture_output=True, text=True)
    os.remove(name)
    with lock:
        out.append((k, n, r.stdout.strip(), r.returncode))


def main():
    out = []
    lock = threading.Lock()
    ts = [threading.Thread(target=job, args=(k, out, lock)) for k in range(6)]
    for t in ts:
        t.start()
    for t in ts:
        t.join()
    for row in sorted(out):
        print(row)
    print(sorted(os.listdir(".")) == sorted(x for x in os.listdir(".") if not x.startswith("file_")))


main()
'''


WITH_JUMPS = r'''
import threading

lock = threading.Lock()
other = threading.RLock()
tasks = list(range(100))
done = []


def worker(tag):
    while True:
        with lock:
            if not tasks:
                break
            t = tasks.pop()
            if t % 10 == 0:
                continue
        with other, lock:
            done.append(t)
            if t == 55:
                try:
                    raise ValueError("inside")
                except ValueError:
                    done.append(-1)


def finder(xs):
    for x in xs:
        with lock:
            if x > 3:
                return x
    return -1


def main():
    ts = [threading.Thread(target=worker, args=(i,)) for i in range(4)]
    for t in ts:
        t.start()
    for t in ts:
        t.join()
    print(len(done), sorted(done)[:5], lock.locked())
    print(finder([1, 2, 5, 7]), lock.locked())
    try:
        with lock:
            raise KeyError("x")
    except KeyError:
        print("released after error", lock.locked())
    for i in range(3):
        with lock:
            if i == 1:
                try:
                    with other:
                        raise ValueError("nested")
                except ValueError as e:
                    print("nested", e)
                break
    print("after break", lock.locked(), other.acquire(blocking=False))


main()
'''


class Programs(Base):
    def test_with_lock_and_jumps(self):
        self.compare("with_jumps", WITH_JUMPS, runs=3)

    def test_files_and_processes_in_threads(self):
        self.compare("files_procs", FILES_AND_PROCESSES.replace("@PY@", repr(sys.executable)), runs=2)

    def test_lock_counter(self):
        self.compare("lock_counter", LOCK_COUNTER.replace("N, ", "20000, ").replace("N * T", "20000 * 8")
                     .replace("range(T)", "range(8)"), runs=3)

    def test_primitives(self):
        self.compare("primitives", PRIMITIVES, runs=3)

    def test_queues(self):
        self.compare("queues", QUEUES, runs=3)

    def test_executors(self):
        self.compare("executors", EXECUTORS, runs=3)

    def test_threads(self):
        self.compare("threads", THREADS, runs=2, stderr_has=("Exception in thread failer", "KeyError: 'k'"))

    def test_main_raises_threads_still_joined(self):
        self.compare("late", LATE, rc=1, stderr_has=("ValueError: main failed",))


class Stress(Base):
    def test_many_threads_one_lock(self):
        for threads, n in ((16, 5000), (3, 40000), (32, 500)):
            with self.subTest(threads=threads, n=n):
                self.compare("stress_lock", LOCK_COUNTER.replace("N, ", "%d, " % n).replace("N * T", "%d * %d" % (n, threads))
                             .replace("range(T)", "range(%d)" % threads), runs=3)

    def test_producers_consumers(self):
        self.compare("stress_queue", STRESS_QUEUE, runs=5)

    def test_pool_many_tasks(self):
        self.compare("stress_pool", STRESS_POOL, runs=3)

    def test_random_worker_counts(self):
        rng = random.Random(1218)
        for _ in range(3):
            threads, n, size = rng.randint(2, 12), rng.randint(100, 3000), rng.randint(1, 20)
            text = STRESS_QUEUE.replace("P = 6", "P = %d" % threads).replace("C = 5", "C = %d" % rng.randint(1, 6)) \
                .replace("N = 3000", "N = %d" % n).replace("maxsize=50", "maxsize=%d" % size)
            with self.subTest(threads=threads, n=n, size=size):
                self.compare("stress_random", text, runs=2)


@unittest.skipUnless(sys.platform.startswith("linux") and shutil.which("gcc"), "sanitizers: Linux gcc")
class Sanitizers(unittest.TestCase):
    """The generated C of a stress program under ThreadSanitizer (no data race: every AIL value is touched
    by the lock holder only, and TSan sees the hand-over through the mutex) and ASan/UBSan."""

    def run_sanitized(self, text, flags, name):
        sys.path[:0] = [str(CORE), str(ROOT)]
        try:
            import ail_syntax
            import pyboxed2
        finally:
            del sys.path[:2]
        c = pyboxed2.build(ail_syntax.fold_constants(ail_syntax.python_surface(text)), {}, allow_mix=False)
        with tempfile.TemporaryDirectory(prefix="ail-threads-san-") as tmp:
            cfile = Path(tmp) / (name + ".c")
            cfile.write_text(c, encoding="utf-8")
            exe = Path(tmp) / name
            cc = subprocess.run(["gcc", "-O1", "-g", *flags, "-o", str(exe), str(cfile), "-lm", "-pthread"],
                                capture_output=True, text=True, timeout=600)
            if cc.returncode:
                self.skipTest("gcc cannot build with %s: %s" % (" ".join(flags), cc.stderr[-300:]))
            want = subprocess.run([sys.executable, "-c", text], capture_output=True, timeout=300, env=oracle_env())
            # high-entropy ASLR can defeat TSan's shadow layout (it stops, or faults): run without ASLR
            norand = ["setarch", platform.machine(), "-R"] if shutil.which("setarch") else []
            for _ in range(20):
                got = subprocess.run(norand + [str(exe)], capture_output=True, timeout=600,
                                     env=dict(os.environ, TSAN_OPTIONS="halt_on_error=1", ASAN_OPTIONS="detect_leaks=0"))
                if b"unexpected memory mapping" not in got.stderr:
                    break
            else:
                self.skipTest("ThreadSanitizer cannot map its shadow memory on this kernel")
            err = got.stderr.decode("utf-8", "replace")
            self.assertNotIn("ThreadSanitizer", err)
            self.assertNotIn("AddressSanitizer", err)
            self.assertNotIn("runtime error", err)
            self.assertEqual(got.returncode, 0, err[-2000:])
            self.assertEqual(got.stdout, want.stdout)

    def test_tsan(self):
        text = LOCK_COUNTER.replace("N, ", "3000, ").replace("N * T", "3000 * 6").replace("range(T)", "range(6)")
        self.run_sanitized(text, ["-fsanitize=thread"], "tsan_lock")
        self.run_sanitized(STRESS_QUEUE.replace("N = 3000", "N = 400"), ["-fsanitize=thread"], "tsan_queue")
        self.run_sanitized(QUEUES, ["-fsanitize=thread"], "tsan_queues")

    def test_asan_ubsan(self):
        self.run_sanitized(STRESS_POOL.replace("4000", "800"), ["-fsanitize=address,undefined", "-fno-omit-frame-pointer"],
                           "asan_pool")
        self.run_sanitized(PRIMITIVES, ["-fsanitize=address,undefined", "-fno-omit-frame-pointer"], "asan_primitives")


class Refusals(Base):
    HEAD = "import threading\nimport queue\nfrom concurrent.futures import ThreadPoolExecutor\n"

    def test_by_name(self):
        cases = [
            ("def main():\n    out = []\n    t = threading.Thread(target=lambda: out.append(1))\n    t.start()\n    t.join()\n"
             "    print(out)\nmain()\n", "a lambda as the function of a thread"),
            ("def main():\n    out = []\n    def w():\n        out.append(1)\n    t = threading.Thread(target=w)\n"
             "    t.start()\n    t.join()\n    print(out)\nmain()\n", "defined inside a function"),
            ("def main():\n    d = threading.local()\n    print(d)\nmain()\n", "threading.local is not built"),
            ("def f():\n    print(1)\ndef main():\n    threading.Timer(1.0, f).start()\nmain()\n", "threading.Timer is not built"),
            ("def main():\n    b = threading.Barrier(2)\n    print(b)\nmain()\n", "threading.Barrier is not built"),
            ("def main():\n    q = queue.PriorityQueue()\n    print(q)\nmain()\n", "queue.PriorityQueue is not built"),
            ("import concurrent.futures\ndef main():\n    concurrent.futures.ProcessPoolExecutor()\nmain()\n",
             "ProcessPoolExecutor is not built"),
            ("def main():\n    c = threading.Condition()\n    with c:\n        c.wait_for(lambda: True)\nmain()\n",
             "wait_for() takes a function"),
            ("def sq(x):\n    return x\ndef main():\n    with ThreadPoolExecutor() as ex:\n        f = ex.submit(sq, 1)\n"
             "        f.add_done_callback(print)\nmain()\n", "add_done_callback() takes a function"),
            ("def main():\n    import threading as t2\n    print(t2.get_ident())\nmain()\n", "put the import at the top"),
            ("def main():\n    x = threading\n    print(x)\nmain()\n", "used as a value is not built"),
            ("def main():\n    print(threading.settrace)\nmain()\n", "threading.settrace is not built"),
            ("def main():\n    print(threading.stack_size())\nmain()\n", "threading.stack_size is not built"),
            ("class W(threading.Thread):\n    pass\nclass V(W):\n    def __init__(self):\n"
             "        threading.Thread.__init__(self)\ndef main():\n    print(V().name)\nmain()\n",
             "outside a direct subclass of Thread"),
        ]
        bare = ("settrace", "stack_size")
        for body, needle in cases:
            with self.subTest(needle=needle):
                self.refused(self.HEAD + body, needle, *(() if any(b in needle for b in bare) else ("write instead",)))
        self.refused("from threading import *\ndef main():\n    print(Lock())\nmain()\n", "from threading import *")

    def test_typed_path_names_the_general_path(self):
        self.refused(LOCK_COUNTER, "built on the general path only", typed_only=True)


class NoCost(unittest.TestCase):
    def test_source_pass_leaves_other_programs_alone(self):
        sys.path[:0] = [str(CORE), str(ROOT)]
        try:
            import threadlib
        finally:
            del sys.path[:2]
        for text in ("queue = []\nconcurrent = 1\nprint('threading', queue, concurrent)\n",
                     "def main():\n    print('no threads')\nmain()\n",
                     "import queue_helpers\n", "x = 'from threading import Thread'\n"):
            self.assertIs(threadlib.rewrite_text(text), text)

    def test_c_has_no_thread_runtime(self):
        sys.path[:0] = [str(CORE), str(ROOT)]
        try:
            import ail_syntax
            import pyboxed2
        finally:
            del sys.path[:2]
        plain = "counter = 0\ndef bump():\n    global counter\n    for i in range(3):\n        counter += i\n" \
                "def main():\n    bump()\n    print(counter)\nmain()\n"
        c = pyboxed2.build(ail_syntax.python_surface(plain), {})
        for needle in ("ail_gil", "AIL_GIL_CHECK", "pthread", "ail_thr_mark_roots", "ail_th_"):
            self.assertNotIn(needle, c)
        self.assertEqual(c.count("{ int rc = ail_main_finish(cx, st); ail_ctx_destroy(cx); return rc; }"), 2)
        threaded = pyboxed2.build(ail_syntax.python_surface(LOCK_COUNTER.replace("N, ", "3, ")
                                                            .replace("N * T", "6").replace("range(T)", "range(2)")), {})
        self.assertIn("AIL_GIL_CHECK(cx);", threaded)
        self.assertIn("ail_thr_mark_roots(cx);", threaded)
        self.assertIn("rc = ail_th_finish(cx, rc);", threaded)


if __name__ == "__main__":
    unittest.main()

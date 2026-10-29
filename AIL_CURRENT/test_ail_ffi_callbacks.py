"""F7: callbacks from C into AIL. `callback(ret, arg, ...)` (ail_ffi.py, ail_ffi_lower.py).

A stub parameter `callback(c_int, cptr(c_int), cptr(c_int), on_error=0)` takes the name of a module-level, fully
C-typed def. The compiled program runs the C call on a stack of its own and serves each callback in between (a C
trampoline per callback parameter); the ctypes shim uses `ctypes.CFUNCTYPE`. An exception raised in a callback is
stored, C gets `on_error` (from this and every later callback of the same C call), and the exception is raised
when the C call returns, in both. Each program below runs under CPython (ail_ffi.py) and as the compiled executable,
typed path and general path; stdout and the exit code must be equal.

* qsort and bsearch from the C library with AIL comparators (ints, doubles; a header-checked `const void *` form);
* a small C library (built here): an exception in the 3rd callback call, a result that does not fit, an uncaught
  exception, nested callback calls, float / bool / str / void / c_void_p / array callbacks, a callback on a stub
  that also takes a bytearray;
* the SQLite `sqlite3_exec` row callback; skipped with a reason when libsqlite3-dev is missing;
* C that breaks the contract (calls the callback from its own thread, or after the call returned) aborts with a
  message instead of running the callback;
* named refusals with file:line and `write instead:` (lambda, closure, method, local variable, retain=, threads=,
  a parallel worker that makes the call, a mismatched def);
* programs without callbacks keep the same lowered text and the same adapter C (sha256 against the values F4 gives).
"""
import ctypes
import hashlib
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent
CLI = str(ROOT / "ail_chatgpt.py")
CC = os.environ.get("PIPE_CC") or shutil.which("cc") or shutil.which("gcc")

MODES = (("typed", {"AIL_NO_GENERAL": "1", "AIL_IR": "0"}), ("general", {"AIL_UNIFIED_FORCE": "1"}))

SORT = r"""
from ail_ffi import *

Cmp = callback(c_int, cptr(c_int), cptr(c_int), on_error=0)

@extern(header="stdlib.h", trust=True)
def qsort(base: ptr(c_int), n: length("base", c_size_t), size: c_size_t, cmp: Cmp) -> None: ...
@extern(header="stdlib.h", trust=True)
def bsearch(key: cptr(c_int), base: cptr(c_int), n: length("base", c_size_t), size: c_size_t, cmp: Cmp) -> c_void_p: ...
@extern(header="stdlib.h", trust=True, symbol="qsort")
def qsort_f(base: ptr(c_double), n: length("base", c_size_t), size: c_size_t,
            cmp: callback(c_int, cptr(c_double), cptr(c_double), on_error=0)) -> None: ...
@extern(header="stdlib.h", symbol="qsort")
def qsort_raw(base: c_mut_void_p, n: c_size_t, size: c_size_t,
              cmp: callback(c_int, c_const_void_p, c_const_void_p, on_error=0)) -> None: ...

def by_value(a: int, b: int) -> int:
    return a - b

def descending(a: int, b: int) -> int:
    return b - a

def by_float(a: float, b: float) -> int:
    if a < b:
        return -1
    if a > b:
        return 1
    return 0

def never(a: int, b: int) -> int:
    print("not called")
    return 0

def pack(xs: list[int]) -> bytearray:
    out = bytearray()
    for x in xs:
        out.extend(x.to_bytes(4, "little", signed=True))
    return out

def unpack(b: bytearray) -> list[int]:
    data = bytes(b)
    return [int.from_bytes(data[i:i + 4], "little", signed=True) for i in range(0, len(data), 4)]

def main():
    buf = pack([5, -2, 9, 1, 7, 1, -40])
    qsort(buf, 4, by_value)
    print(unpack(buf))
    qsort(buf, 4, descending)
    print(unpack(buf))
    qsort(buf, 4, cmp=by_value)
    table = bytes(buf)
    for k in [-40, 7, 8, 9, 100]:
        print(k, bsearch(bytes(pack([k])), table, 4, by_value) != 0)
    one = pack([3])
    qsort_raw(one, 1, 4, never)
    print(unpack(one))
    empty = bytearray()
    qsort_f(empty, 8, by_float)
    print(len(empty))

main()
"""
SORT_OUT = ("[-40, -2, 1, 1, 5, 7, 9]\n[9, 7, 5, 1, 1, -2, -40]\n-40 True\n7 True\n8 False\n9 True\n100 False\n"
            "[3]\n0\n")

CB_H = r"""
int each(int n, int (*f)(int));
int got(int i);
double fold(int n, double (*f)(double, int), double acc);
int count_if(int n, _Bool (*p)(int));
void names(void (*f)(const char *, int));
int lists(int (*f)(int, int *, char **, double *));
void *poke(void *(*f)(void *, unsigned char), void *p);
void tick(int n, void (*f)(int));
int scale(unsigned char *buf, int n, int (*f)(int));
int in_thread(int (*f)(int));
void keep(int (*f)(int));
int fire(void);
"""

CB_C = r"""
#include "cb.h"
#include <pthread.h>
#include <stddef.h>
static int log_[16];
int each(int n, int (*f)(int)) { int s = 0; for (int i = 1; i <= n; i++) { int r = f(i); if (i < 16) log_[i] = r; s += r; } return s; }
int got(int i) { return log_[i]; }
double fold(int n, double (*f)(double, int), double acc) { for (int i = 1; i <= n; i++) acc = f(acc, i); return acc; }
int count_if(int n, _Bool (*p)(int)) { int c = 0; for (int i = 0; i < n; i++) c += p(i); return c; }
void names(void (*f)(const char *, int)) { f("alpha", 1); f("\xce\xb2" "eta", 2); f(NULL, 3); }
int lists(int (*f)(int, int *, char **, double *)) {
    static int xs[3] = {4, -5, 6}; static char *w[3] = {"x", NULL, "zz"}; static double d[3] = {0.5, 1.5, -2.0};
    return f(3, xs, w, d) + f(0, NULL, NULL, NULL);
}
void *poke(void *(*f)(void *, unsigned char), void *p) { return f(p, 200); }
void tick(int n, void (*f)(int)) { for (int i = 0; i < n; i++) f(i); }
int scale(unsigned char *buf, int n, int (*f)(int)) { int s = 0; for (int i = 0; i < n; i++) { buf[i] = (unsigned char)f(buf[i]); s += buf[i]; } return s; }
static int (*kept)(int);
static void *thread_main(void *f) { kept = (int (*)(int))f; static int r; r = kept(5); return &r; }
int in_thread(int (*f)(int)) { pthread_t t; void *r; pthread_create(&t, NULL, thread_main, (void *)f); pthread_join(t, &r); return *(int *)r; }
void keep(int (*f)(int)) { kept = f; }
int fire(void) { return kept(6); }
"""

CB_STUBS = r"""
from ail_ffi import *

link("./libcb.so")
Each = callback(c_int, c_int, on_error=-1)

@extern(header="cb.h")
def each(n: c_int, f: Each) -> c_int: ...
@extern(header="cb.h")
def got(i: c_int) -> c_int: ...
@extern(header="cb.h")
def fold(n: c_int, f: callback(c_double, c_double, c_int, on_error=-1.5), acc: c_double) -> c_double: ...
@extern(header="cb.h")
def count_if(n: c_int, p: callback(c_bool, c_int, on_error=True)) -> c_int: ...
@extern(header="cb.h")
def names(f: callback(None, c_char_p, c_int)) -> None: ...
@extern(header="cb.h")
def lists(f: callback(c_int, c_int, array(c_int, 0), array(c_mut_char_p, 0), array(c_double, 0), on_error=0)) -> c_int: ...
@extern(header="cb.h")
def poke(f: callback(c_void_p, c_void_p, c_uint8, on_error=0), p: c_void_p) -> c_void_p: ...
@extern(header="cb.h")
def tick(n: c_int, f: callback(None, c_int)) -> None: ...
@extern(header="cb.h")
def scale(buf: bytearray, n: length("buf", c_int), f: Each) -> c_int: ...
@extern(header="cb.h")
def in_thread(f: Each) -> c_int: ...
@extern(header="cb.h")
def keep(f: Each) -> None: ...
@extern(header="cb.h")
def fire() -> c_int: ...
"""

THIRD = CB_STUBS + r"""
def third(i: int) -> int:
    print("call", i)
    if i == 3:
        raise ValueError("raised in call 3")
    return i * 10

def big(i: int) -> int:
    return i << 40

def inner(i: int) -> int:
    return i

def outer(i: int) -> int:
    return each(i, inner)

def inner_bad(i: int) -> int:
    if i == 2:
        raise KeyError("inner")
    return i

def outer_bad(i: int) -> int:
    print("outer", i)
    return each(i, inner_bad) + 100

def half(acc: float, i: int) -> float:
    return acc + i / 2

def bad_fold(acc: float, i: int) -> float:
    if i == 2:
        raise RuntimeError("fold")
    return acc + 1.0

def odd(i: int) -> bool:
    return i % 2 == 1

def show(s: str, i: int) -> None:
    print("name", i, s, len(s))

def items(n: int, xs: list[int], words: list[str], ds: list[float]) -> int:
    print("items", n, xs, words, ds)
    return sum(xs) + n

def step(p: int, k: int) -> int:
    return p + k

def stop_at_two(i: int) -> None:
    print("tick", i)
    if i == 2:
        raise IndexError("tick")

def double_or_raise(b: int) -> int:
    if b > 20:
        raise ValueError("too big")
    return b * 2

def main():
    print(each(2, third))
    print(got(1), got(2))
    try:
        print(each(5, third))
    except ValueError as e:
        print("caught:", e)
    print(got(1), got(2), got(3), got(4), got(5))
    try:
        each(2, big)
    except OverflowError as e:
        print("overflow:", e)
    print(got(1), got(2))
    print(each(3, outer))
    try:
        each(3, outer_bad)
    except KeyError as e:
        print("nested:", e)
    print(got(1), got(2), got(3))
    print(fold(4, half, 1.0))
    try:
        fold(4, bad_fold, 0.0)
    except RuntimeError as e:
        print("fold:", e)
    print(count_if(7, odd))
    names(show)
    print(lists(items))
    print(poke(step, 4096))
    try:
        tick(5, stop_at_two)
    except IndexError as e:
        print("tick:", e)
    buf = bytearray([1, 2, 3, 4])
    print(scale(buf, double_or_raise), buf[0], buf[3])
    buf = bytearray([5, 30, 7])
    try:
        scale(buf, double_or_raise)
    except ValueError as e:
        print("scale:", e, buf[0], buf[1], buf[2])

main()
"""
THIRD_OUT = (
    "call 1\ncall 2\n30\n10 20\ncall 1\ncall 2\ncall 3\ncaught: raised in call 3\n10 20 -1 -1 -1\n"
    "overflow: each: the result of big does not fit c_int\n-1 -1\n10\nouter 1\nouter 2\nnested: 'inner'\n1 -1 -1\n"
    "6.0\nfold: fold\n3\nname 1 alpha 5\nname 2 \u03b2eta 4\nname 3  0\n"
    "items 3 [4, -5, 6] ['x', '', 'zz'] [0.5, 1.5, -2.0]\nitems 0 [] [] []\n8\n4296\ntick 0\ntick 1\ntick 2\ntick: tick\n"
    "20 2 8\nscale: too big 10 255 255\n")

UNCAUGHT = CB_STUBS + r"""
def third(i: int) -> int:
    print("call", i)
    if i == 3:
        raise ValueError("raised in call 3")
    return i

def main():
    print(each(5, third))
    print("not reached")

main()
"""
UNCAUGHT_OUT = "call 1\ncall 2\ncall 3\n"

# C breaks the contract: it calls the callback from a thread of its own, or keeps it and calls it after the call
OTHER_THREAD = CB_STUBS + r"""
def seen(i: int) -> int:
    print("not reached", i)
    return i

def main():
    print("before")
    print(in_thread(seen))

main()
"""
AFTER_CALL = CB_STUBS + r"""
def seen(i: int) -> int:
    print("seen", i)
    return i

def main():
    keep(seen)
    print("kept")
    print(fire())

main()
"""
ABORT_MESSAGE = "ail_ffi: the callback of %s was called from another thread or after its C call returned"

SQLITE = r"""
from ail_ffi import *

link("sqlite3")
Db = Handle("sqlite3", free="sqlite3_close")
Row = callback(c_int, c_void_p, c_int, array(c_mut_char_p, 1), array(c_mut_char_p, 1), on_error=1)

@extern(header="sqlite3.h", trust=True)
def sqlite3_open(path: c_char_p, out: ptr(c_void_p)) -> c_int: ...
@extern(header="sqlite3.h", trust=True)
def sqlite3_exec(db: Db, sql: c_char_p, cb: Row, arg: c_void_p, err: c_void_p) -> c_int: ...

def ignore(ctx: int, n: int, values: list[str], names: list[str]) -> int:
    return 0

def show(ctx: int, n: int, values: list[str], names: list[str]) -> int:
    print(ctx, n, ", ".join(names), "|", ", ".join(values))
    return 0

def first_two(ctx: int, n: int, values: list[str], names: list[str]) -> int:
    print("row", values[0])
    if values[0] == "2":
        return 1
    return 0

def fail_on_pear(ctx: int, n: int, values: list[str], names: list[str]) -> int:
    print("row", values[1])
    if values[1] == "pear":
        raise ValueError("no pears")
    return 0

def main():
    out = bytearray(8)
    print(sqlite3_open(":memory:", out))
    db = Db.adopt(out)
    print(sqlite3_exec(db, "create table item(id integer primary key, name text, qty integer)", ignore, 0, 0))
    print(sqlite3_exec(db, "insert into item(name, qty) values('apple', 3), ('pear', null), ('plum', 10)", ignore, 0, 0))
    print(sqlite3_exec(db, "select id, name, qty from item order by id", show, 77, 0))
    print(sqlite3_exec(db, "select id from item order by id", first_two, 0, 0))
    try:
        sqlite3_exec(db, "select id, name from item order by id", fail_on_pear, 0, 0)
    except ValueError as e:
        print("caught:", e)
    print(sqlite3_exec(db, "select count(*) as n from item", show, 0, 0))
    db.close()

main()
"""
SQLITE_OUT = ("0\n0\n0\n77 3 id, name, qty | 1, apple, 3\n77 3 id, name, qty | 2, pear, \n77 3 id, name, qty | 3, plum, 10\n0\n"
              "row 1\nrow 2\n4\nrow apple\nrow pear\ncaught: no pears\n0 1 n | 3\n0\n")

# refusals: (name, program, line, words that the message must name)
REFUSE_HEAD = CB_STUBS + "\n"
HEAD_LINES = REFUSE_HEAD.count("\n")
REFUSALS = [
    ("lambda", "def main():\n    print(each(3, lambda i: i))\n\nmain()\n", 2, ["lambda", "def name(a0: int) -> int:"]),
    ("closure", "def main():\n    def f(i: int) -> int:\n        return i\n    print(each(3, f))\n\nmain()\n", 4,
     ["closure"]),
    ("method", "class K:\n    def f(self, i: int) -> int:\n        return i\n\ndef main():\n    k = K()\n"
               "    print(each(3, k.f))\n\nmain()\n", 7, ["method k.f"]),
    ("variable", "def g(i: int) -> int:\n    return i\n\ndef main():\n    f = g\n    print(each(3, f))\n\nmain()\n", 6,
     ["local variable f"]),
    ("mismatch", "def g(i: int) -> float:\n    return 1.0\n\ndef main():\n    print(each(3, g))\n\nmain()\n", 5,
     ["result annotation float", "def g(a0: int) -> int:"]),
    ("value", "def main():\n    f = each\n    print(f)\n\nmain()\n", 2, ["each takes a callback"]),
    ("parallel", "import threading\n\ndef g(i: int) -> int:\n    return i\n\ndef work(n: int) -> None:\n"
                 "    print(each(n, g))\n\ndef main():\n    t = threading.Thread(target=work, args=(3,))\n    t.start()\n"
                 "    t.join()\n\nmain()\n", 10, ["parallel worker", "work (which makes a C call that takes a callback)"]),
]
RETAIN = r"""
from ail_ffi import *

@extern(lib="./libcb.so", header="cb.h")
def each(n: c_int, f: callback(c_int, c_int, on_error=0, retain=True)) -> c_int: ...
"""
THREADS = r"""
from ail_ffi import *

Each = callback(c_int, c_int, on_error=0,
                threads=True)
"""

# programs without callbacks: the lowered text and the adapter C, sha256, as F4 writes them (lowered at the fixed path
# below; the adapter's compile step is not run)
GOLDEN_PATH = "/ail-f7-golden/prog.py"
GOLDEN = {
    "libc": r"""
from ail_ffi import *

@extern(header="stdlib.h")
def abs(x: c_int) -> c_int: ...
@extern(header="string.h")
def strlen(s: c_char_p) -> c_size_t: ...
@extern(header="unistd.h", check="minus1", errno=True)
def close(fd: c_int) -> c_int: ...

def main():
    print(abs(-4), strlen("hello"))
    try:
        close(-1)
    except OSError as e:
        print(e.errno)

main()
""",
    "bytes": r"""
from ail_ffi import *

link("z")

@extern(header="zlib.h")
def crc32(crc: c_ulong, buf: bytes, n: length("buf", c_uint)) -> c_ulong: ...
@extern(header="string.h")
def memset(s: bytearray, c: c_int, n: length("s", c_size_t)) -> c_void_p: ...
@extern(header="stdlib.h", trust=True)
def strtol(s: c_char_p, end: ptr(c_void_p), base: c_int) -> c_long: ...

def main():
    b = bytearray(4)
    memset(b, 7)
    print(crc32(0, b"hello"), b[0], strtol("42", bytearray(8), 10))

main()
""",
    "handle": r"""
from ail_ffi import *

link("sqlite3")
Db = Handle("sqlite3", free="sqlite3_close")

@extern(header="sqlite3.h", trust=True)
def sqlite3_open(path: c_char_p, out: ptr(c_void_p)) -> c_int: ...
@extern(header="sqlite3.h", trust=True)
def sqlite3_exec(db: Db, sql: c_char_p, cb: c_void_p, arg: c_void_p, err: c_void_p) -> c_int: ...

def main():
    out = bytearray(8)
    sqlite3_open(":memory:", out)
    db = Db.adopt(out)
    print(sqlite3_exec(db, "create table t(x)", 0, 0, 0))
    db.close()

main()
""",
}
GOLDEN_SHA = {
    "libc": ("d196bb55703c310d3da9a8e100054968bb27f62cc18d8f731a0a0371962240c5",
               "40f67875f01ca2240012b086ad547b333e793ac80af29f018ffc0858779e1390"),
    "bytes": ("37c47290cc40f8f36398d59ef3935c0d2df8c03467995275906a7b9d936969b9",
               "0dfe30459b62074b12879f100c4279492160a692ec4cb08ac158d36922f1909f"),
    "handle": ("4671aa3d2fe69e63683510cd10862f68ba17c929954cff4bce79114efef23ccb",
               "a30529176b3286e6065ac5fee9061e17df8c87f65f065c94e4d6698ac2c7d3ef"),
}


def lowered_and_adapter(module, text):
    """The text `module` (ail_ffi_lower) lowers `text` to at GOLDEN_PATH, and the adapter C it writes."""
    with tempfile.TemporaryDirectory() as directory:
        session = module.Session(workdir=directory)
        lowered = session.lower(GOLDEN_PATH, text)
        try:
            session.build(Path(directory) / "no-such-cli.py")    # writes ffi_adapter.c, then fails to compile it
        except ValueError:
            pass
        return lowered, (Path(directory) / "ffi_adapter.c").read_text(encoding="utf8")


def sha(text):
    return hashlib.sha256(text.encode("utf8")).hexdigest()


def have_sqlite():
    if not CC:
        return False
    with tempfile.TemporaryDirectory() as directory:
        source = Path(directory, "probe.c")
        source.write_text('#include <sqlite3.h>\nint main(void) { return sqlite3_libversion_number() == 0; }\n')
        done = subprocess.run([CC, str(source), "-lsqlite3", "-o", str(Path(directory, "probe"))], capture_output=True)
        return done.returncode == 0


def compile_cli(directory, source, mode, name):
    out = Path(directory) / name
    if out.exists():
        out.unlink()
    env = dict(os.environ, PYTHONPATH=str(ROOT), AIL_NO_CACHE="1")
    env.update(dict(MODES)[mode])
    done = subprocess.run([sys.executable, "-B", CLI, "compile", source, "-o", str(out)], cwd=directory,
                          capture_output=True, text=True, timeout=900, env=env)
    return done, out


def run_cpython(directory, source):
    env = dict(os.environ, PYTHONPATH=str(ROOT), PYTHONDONTWRITEBYTECODE="1")
    return subprocess.run([sys.executable, "-B", source], cwd=directory, capture_output=True, text=True, timeout=120, env=env)


class K:
    def f(self, i: int) -> int:
        return i


@unittest.skipUnless(CC, "installed C compiler required")
class CallbackTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory(prefix="ail-ffi-callbacks-")
        cls.dir = Path(cls.temp.name)
        (cls.dir / "cb.h").write_text(CB_H, encoding="utf8")
        (cls.dir / "cb.c").write_text(CB_C, encoding="utf8")
        done = subprocess.run([CC, "-shared", "-fPIC", "-O1", "-o", str(cls.dir / "libcb.so"), str(cls.dir / "cb.c"), "-lpthread"],
                              capture_output=True, text=True)
        if done.returncode:
            raise RuntimeError(done.stderr)

    @classmethod
    def tearDownClass(cls):
        cls.temp.cleanup()

    def write(self, name, text):
        (self.dir / name).write_text(text, encoding="utf8")
        return name

    def compare(self, name, text, expected_out, expected_code=0):
        """CPython's stdout and exit code, then the typed and the general build's: all equal, and equal to expected."""
        source = self.write(name + ".py", text)
        cpy = run_cpython(self.dir, source)
        self.assertEqual((cpy.stdout, cpy.returncode), (expected_out, expected_code), cpy.stderr)
        for mode, _ in MODES:
            with self.subTest(mode):
                built, exe = compile_cli(self.dir, source, mode, "%s_%s.out" % (name, mode))
                self.assertEqual(built.returncode, 0, built.stderr + built.stdout)
                ran = subprocess.run([str(exe)], cwd=self.dir, capture_output=True, text=True, timeout=60)
                self.assertEqual(ran.stdout, cpy.stdout)
                self.assertEqual(ran.returncode, cpy.returncode, ran.stderr)

    def test_qsort_and_bsearch(self):
        self.compare("sort", SORT, SORT_OUT)

    def test_exception_in_the_third_call_and_other_callbacks(self):
        self.compare("third", THIRD, THIRD_OUT)

    def test_uncaught_exception_from_a_callback(self):
        self.compare("uncaught", UNCAUGHT, UNCAUGHT_OUT, 1)

    def test_callback_from_another_thread_aborts(self):
        source = self.write("thread.py", OTHER_THREAD)
        runs = [run_cpython(self.dir, source)]
        for mode, _ in MODES:
            built, exe = compile_cli(self.dir, source, mode, "thread_%s.out" % mode)
            self.assertEqual(built.returncode, 0, built.stderr + built.stdout)
            runs.append(subprocess.run([str(exe)], cwd=self.dir, capture_output=True, text=True, timeout=60))
        for ran in runs:        # (stdout is flushed before the abort, in both)
            self.assertEqual((ran.stdout, ran.returncode), ("before\n", -6), ran.stderr)
            self.assertIn(ABORT_MESSAGE % "in_thread", ran.stderr)

    def test_callback_after_the_call_aborts(self):
        # (under CPython the ctypes function object is gone by then: not compared)
        source = self.write("after.py", AFTER_CALL)
        for mode, _ in MODES:
            with self.subTest(mode):
                built, exe = compile_cli(self.dir, source, mode, "after_%s.out" % mode)
                self.assertEqual(built.returncode, 0, built.stderr + built.stdout)
                ran = subprocess.run([str(exe)], cwd=self.dir, capture_output=True, text=True, timeout=60)
                self.assertEqual((ran.stdout, ran.returncode), ("kept\n", -6), ran.stderr)
                self.assertIn(ABORT_MESSAGE % "keep", ran.stderr)

    @unittest.skipUnless(have_sqlite(), "libsqlite3-dev (sqlite3.h and -lsqlite3) is not installed")
    def test_sqlite_exec_row_callback(self):
        self.compare("sqlite", SQLITE, SQLITE_OUT)

    def refused(self, name, text, line, words):
        source = self.write(name + ".py", text)
        built, _ = compile_cli(self.dir, source, "typed", name + ".out")
        self.assertNotEqual(built.returncode, 0, built.stdout)
        self.assertIn("%s:%d:" % (source, line), built.stderr)
        self.assertIn("write instead:", built.stderr)
        for word in words:
            self.assertIn(word, built.stderr)

    def test_refusals(self):
        for name, body, line, words in REFUSALS:
            with self.subTest(name):
                self.refused("refuse_" + name, REFUSE_HEAD + body, HEAD_LINES + line, words)
        with self.subTest("retain"):
            self.refused("refuse_retain", RETAIN, 5, ["retain=", "valid only during the call"])
        with self.subTest("threads"):
            self.refused("refuse_threads", THREADS, 5, ["threads=", "another thread"])

    def test_shim_refuses_the_same_callbacks(self):
        sys.path.insert(0, str(ROOT))
        import ail_ffi
        cb = ail_ffi.callback(ail_ffi.c_int, ail_ffi.c_int, on_error=0)
        with self.assertRaises(TypeError):
            ail_ffi.callback(ail_ffi.c_int, ail_ffi.c_int, on_error=0, retain=True)
        with self.assertRaises(TypeError):
            ail_ffi.callback(ail_ffi.c_int, ail_ffi.c_int, on_error=0, threads=True)
        with self.assertRaises(TypeError):
            ail_ffi.callback(ail_ffi.c_int, ail_ffi.c_int)

        def closure(i: int) -> int:
            return i

        for value, word in ((lambda i: i, "lambda"), (closure, "closure"), (K().f, "method"), (K.f, "method"), (len, "def")):
            with self.assertRaisesRegex(TypeError, word):
                ail_ffi._cb_function("each", "f", cb, value)

    def test_programs_without_callbacks_keep_their_c(self):
        sys.path.insert(0, str(ROOT))
        import ail_ffi_lower
        for name, text in GOLDEN.items():
            with self.subTest(name):
                lowered, adapter = lowered_and_adapter(ail_ffi_lower, text)
                self.assertEqual((sha(lowered), sha(adapter)), GOLDEN_SHA[name])


if __name__ == "__main__":
    unittest.main()

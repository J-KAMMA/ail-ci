"""F4: owned handles. `Handle("sqlite3", free="sqlite3_close")` (ail_ffi.py, ail_ffi_lower.py).

A Handle is the object that owns one C pointer: `h.close()` calls the C free function once and zeroes the pointer, a
use after close raises `ValueError("<name> handle is closed")`, `with h:` closes it, `Type.adopt(buf)` takes the
pointer out of a `ptr(c_void_p)` out-parameter, and what is still open at exit is freed (newest first). Each program
below runs under CPython (ail_ffi.py, ctypes) and as the compiled executable, typed path and general path, and the
outputs must be equal. The C library records every free in a log file, so the number, the order and the exactly-once
of the frees are compared too.

* a counter library (built here): result handles, `check="null"`, out-parameter adoption, `with`, double close,
  use after close, a handle left open at exit, an inline `Handle(...)` annotation, a bare `c_void_p` that still is an int;
* a user-written SQLite wrapper over libsqlite3 (open, prepare, bind, step, finalize, close, use after close, double
  close); skipped with a reason when libsqlite3-dev is missing;
* no leak under AddressSanitizer's leak checker (preloaded: the executables are the ordinary builds);
* named refusals with file:line and `write instead:` (arithmetic on a Handle, a Handle in a parallel worker, a stub
  that calls the free function);
* programs that do not use Handle get the same lowered text and adapter source as before.
"""
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

H_H = r"""
void *h_new(int start);
void *h_find(int k);
int h_next(void *h);
int h_open(int k, void **out);
void h_free(void *h);
int h_freed(void);
int h_live(void);
"""

H_C = r"""
#include "h.h"
#include <stdio.h>
#include <stdlib.h>
static int freed, live;
void *h_new(int start) { int *p = malloc(sizeof(int)); *p = start; live++; return p; }
void *h_find(int k) { return k >= 0 ? h_new(k) : NULL; }
int h_next(void *h) { return (*(int *)h)++; }
int h_open(int k, void **out) { *out = h_new(k); return 0; }
void h_free(void *h) {
    const char *log = getenv("H_LOG");
    if (log) { FILE *f = fopen(log, "a"); if (f) { fprintf(f, "free %d\n", *(int *)h); fclose(f); } }
    free(h); freed++; live--;
}
int h_freed(void) { return freed; }
int h_live(void) { return live; }
"""

STUBS = r"""
from ail_ffi import *

Counter = Handle("counter", free="h_free")

@extern(lib="./libh.so", header="h.h")
def h_new(start: c_int) -> Counter: ...
@extern(lib="./libh.so", header="h.h", check="null", exc=ValueError)
def h_find(k: c_int) -> Counter: ...
@extern(lib="./libh.so", header="h.h")
def h_next(h: Counter) -> c_int: ...
@extern(lib="./libh.so", header="h.h")
def h_open(k: c_int, out: ptr(c_void_p)) -> c_int: ...
@extern(lib="./libh.so", header="h.h")
def h_freed() -> c_int: ...
@extern(lib="./libh.so", header="h.h")
def h_live() -> c_int: ...
"""

COUNTER = STUBS + r"""
leak_a = h_new(10)
leak_b = h_new(20)

def main():
    h = h_new(100)
    print(h_next(h), h_next(h), h_live())
    h.close()
    print(h_freed(), h_live())
    h.close()
    print(h_freed())
    try:
        h_next(h)
    except ValueError as e:
        print("use after close:", {MSG})
    with h_new(5) as w:
        print(h_next(w))
    print(h_freed(), h_live())
    try:
        h_next(w)
    except ValueError as e:
        print("after with:", {MSG})
    try:
        with w:
            print("not reached")
    except ValueError as e:
        print("with on closed:", {MSG})
    out = bytearray(8)
    print(h_open(7, out))
    a = Counter.adopt(out)
    print(h_next(a), out[0], len(out))
    a.close()
    try:
        Counter.adopt(bytearray(3))
    except ValueError as e:
        print("adopt:", {MSG})
    try:
        h_find(-1)
    except ValueError as e:
        print("find:", {MSG})
    g = h_find(3)
    print(h_next(g), h_next(g))
    g.close()
    try:
        with h_new(1) as t:
            h_next(t)
            raise ValueError("inside")
    except ValueError as e:
        print("closed on the way out:", {MSG}, h_freed())
    print(h_freed(), h_live())

main()
"""
COUNTER_OUT = (
    "100 101 3\n1 2\n1\nuse after close: counter handle is closed\n5\n2 2\nafter with: counter handle is closed\n"
    "with on closed: counter handle is closed\n0\n7 0 8\nadopt: adopt takes the bytearray(8) of a ptr(c_void_p) out-parameter\n"
    "find: h_find failed with 0\n3 4\nclosed on the way out: inside 5\n5 2\n")
# 102 is `h` closed explicitly; the two module-level handles are still open when main returns and are freed at exit,
# newest first
COUNTER_LOG = "free 102\nfree 6\nfree 8\nfree 5\nfree 2\nfree 20\nfree 10\n"

INLINE = r"""
from ail_ffi import *

@extern(lib="./libh.so", header="h.h")
def h_new(start: c_int) -> Handle("counter", free="h_free"): ...
@extern(lib="./libh.so", header="h.h")
def h_next(h: Handle("counter", free="h_free")) -> c_int: ...
@extern(lib="./libh.so", header="h.h")
def h_raw(start: c_int) -> c_void_p: ...
@extern(lib="./libh.so", header="h.h")
def h_raw_next(h: c_void_p) -> c_int: ...
@extern(lib="./libh.so", header="h.h")
def h_raw_free(h: c_void_p) -> None: ...
@extern(lib="./libh.so", header="h.h")
def h_live() -> c_int: ...

def main():
    x = h_new(1)
    print(h_next(x), h_next(x), h_live())
    x.close()
    try:
        h_next(x)
    except ValueError as e:
        print({MSG})
    raw = h_raw(50)
    print(raw != 0, h_raw_next(raw), h_raw_next(raw), h_live())
    h_raw_free(raw)
    print(h_live())

main()
"""
INLINE_OUT = "1 2 1\ncounter handle is closed\nTrue 50 51 1\n0\n"
INLINE_H = H_H + "void *h_raw(int start);\nint h_raw_next(void *h);\nvoid h_raw_free(void *h);\n"
INLINE_C = H_C + ("void *h_raw(int start) { return h_new(start); }\nint h_raw_next(void *h) { return h_next(h); }\n"
                  "void h_raw_free(void *h) { free(h); live--; }\n")

SQLITE = r"""
from ail_ffi import *

link("sqlite3")
Db = Handle("sqlite3", free="sqlite3_close")
Stmt = Handle("sqlite3_stmt", free="sqlite3_finalize")

@extern(header="sqlite3.h", trust=True)
def sqlite3_open(path: c_char_p, out: ptr(c_void_p)) -> c_int: ...
@extern(header="sqlite3.h", trust=True)
def sqlite3_exec(db: Db, sql: c_char_p, cb: c_void_p, arg: c_void_p, err: c_void_p) -> c_int: ...
@extern(header="sqlite3.h", trust=True)
def sqlite3_prepare_v2(db: Db, sql: c_char_p, n: c_int, out: ptr(c_void_p), tail: ptr(c_void_p)) -> c_int: ...
@extern(header="sqlite3.h", trust=True)
def sqlite3_bind_int(stmt: Stmt, i: c_int, v: c_int) -> c_int: ...
@extern(header="sqlite3.h", trust=True)
def sqlite3_bind_double(stmt: Stmt, i: c_int, v: c_double) -> c_int: ...
@extern(header="sqlite3.h", trust=True)
def sqlite3_step(stmt: Stmt) -> c_int: ...
@extern(header="sqlite3.h", trust=True)
def sqlite3_reset(stmt: Stmt) -> c_int: ...
@extern(header="sqlite3.h", trust=True)
def sqlite3_column_int(stmt: Stmt, i: c_int) -> c_int: ...
@extern(header="sqlite3.h", trust=True)
def sqlite3_column_double(stmt: Stmt, i: c_int) -> c_double: ...
@extern(header="sqlite3.h", trust=True)
def sqlite3_column_text(stmt: Stmt, i: c_int) -> c_char_p: ...
@extern(header="sqlite3.h", trust=True)
def sqlite3_errmsg(db: Db) -> c_char_p: ...
@extern(header="sqlite3.h", trust=True)
def sqlite3_changes(db: Db) -> c_int: ...

ROW = 100
DONE = 101

class Database:
    def __init__(self, db: Db, name: str):
        self.db = db
        self.name = name

    def run(self, sql: str) -> int:
        return sqlite3_exec(self.db, sql, 0, 0, 0)

    def close(self) -> None:
        self.db.close()

def open_db(path: str) -> Db:
    out = bytearray(8)
    rc = sqlite3_open(path, out)
    if rc != 0:
        print("open failed", rc)
    return Db.adopt(out)

def prepare(db: Db, sql: str) -> Stmt:
    out = bytearray(8)
    tail = bytearray(8)
    rc = sqlite3_prepare_v2(db, sql, -1, out, tail)
    if rc != 0:
        print("prepare failed:", rc, sqlite3_errmsg(db))
    return Stmt.adopt(out)

def total(db: Db) -> int:
    stmt = prepare(db, "select sum(qty) from item")
    n = 0
    if sqlite3_step(stmt) == ROW:
        n = sqlite3_column_int(stmt, 0)
    stmt.close()
    return n

def show(db: Db) -> None:
    stmt = prepare(db, "select id, name, price from item order by id")
    while sqlite3_step(stmt) == ROW:
        print(sqlite3_column_int(stmt, 0), sqlite3_column_text(stmt, 1), sqlite3_column_double(stmt, 2))
    stmt.close()

def main():
    db = open_db(":memory:")
    print(sqlite3_exec(db, "create table item(id integer primary key, name text, price real, qty integer)", 0, 0, 0))
    print(sqlite3_exec(db, "insert into item(name, price, qty) values('apple', 1.5, 3), ('pear', 2.25, 4), ('plum', 0.5, 10)", 0, 0, 0))
    print(sqlite3_changes(db))
    insert = prepare(db, "insert into item(name, price, qty) values(?, ?, ?)")
    for i in range(3):
        sqlite3_bind_double(insert, 2, i * 1.25)
        sqlite3_bind_int(insert, 3, 100 + i)
        print("step", sqlite3_step(insert))
        sqlite3_reset(insert)
    insert.close()
    insert.close()
    show(db)
    print(total(db))
    bad = prepare(db, "selec nothing")
    print(sqlite3_errmsg(db))
    bad.close()
    try:
        sqlite3_step(insert)
    except ValueError as e:
        print("finalized:", {MSG})
    wrapped = Database(db, "main")
    print(wrapped.run("delete from item where id > 3"), total(db))
    wrapped.close()
    wrapped.close()
    try:
        total(db)
    except ValueError as e:
        print("closed:", {MSG})
    try:
        wrapped.run("select 1")
    except ValueError as e:
        print("closed again:", {MSG})
    with open_db(":memory:") as scoped:
        print(sqlite3_exec(scoped, "create table t(x)", 0, 0, 0))
    try:
        sqlite3_exec(scoped, "select 1", 0, 0, 0)
    except ValueError as e:
        print("after with:", {MSG})
    left = open_db(":memory:")
    print(sqlite3_exec(left, "create table t(x)", 0, 0, 0))

main()
"""
SQLITE_OUT = (
    "0\n0\n3\nstep 101\nstep 101\nstep 101\n1 apple 1.5\n2 pear 2.25\n3 plum 0.5\n4  0.0\n5  1.25\n6  2.5\n320\n"
    'prepare failed: 1 near "selec": syntax error\nnear "selec": syntax error\n'
    "finalized: sqlite3_stmt handle is closed\n0 17\nclosed: sqlite3 handle is closed\n"
    "closed again: sqlite3 handle is closed\n0\nafter with: sqlite3 handle is closed\n0\n")


def have_sqlite():
    if not CC:
        return False
    with tempfile.TemporaryDirectory() as directory:
        source = Path(directory, "probe.c")
        source.write_text('#include <sqlite3.h>\nint main(void) { return sqlite3_libversion_number() == 0; }\n')
        done = subprocess.run([CC, str(source), "-lsqlite3", "-o", str(Path(directory, "probe"))], capture_output=True)
        return done.returncode == 0


def libasan():
    if not CC:
        return None
    found = subprocess.run([CC, "-print-file-name=libasan.so"], capture_output=True, text=True).stdout.strip()
    return found if found and os.path.isabs(found) and os.path.exists(found) else None


def compile_cli(directory, source, mode, name):
    out = Path(directory) / name
    if out.exists():
        out.unlink()
    env = dict(os.environ, PYTHONPATH=str(ROOT), AIL_NO_CACHE="1")
    env.update(dict(MODES)[mode])
    done = subprocess.run([sys.executable, "-B", CLI, "compile", source, "-o", str(out)], cwd=directory,
                          capture_output=True, text=True, timeout=900, env=env)
    return done, out


def run_cpython(directory, source, **extra):
    env = dict(os.environ, PYTHONPATH=str(ROOT), PYTHONDONTWRITEBYTECODE="1", **extra)
    return subprocess.run([sys.executable, "-B", source], cwd=directory, capture_output=True, text=True, timeout=120, env=env)


@unittest.skipUnless(CC, "installed C compiler required")
class HandleTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory(prefix="ail-ffi-handles-")
        cls.dir = Path(cls.temp.name)
        (cls.dir / "h.h").write_text(INLINE_H, encoding="utf8")
        (cls.dir / "h.c").write_text(INLINE_C, encoding="utf8")
        done = subprocess.run([CC, "-shared", "-fPIC", "-O1", "-o", str(cls.dir / "libh.so"), str(cls.dir / "h.c")],
                              capture_output=True, text=True)
        if done.returncode:
            raise RuntimeError(done.stderr)
        cls.exes = {}

    @classmethod
    def tearDownClass(cls):
        cls.temp.cleanup()

    def write(self, name, text):
        (self.dir / name).write_text(text, encoding="utf8")
        return name

    def log(self, name):
        path = self.dir / name
        if path.exists():
            path.unlink()
        return str(path)

    def compare(self, name, text, expected_out, expected_log=None):
        """CPython's output and free log, then the typed and the general build's; all equal, and equal to `expected`."""
        cpy_log = self.log(name + "_cpy.log")
        cpy = run_cpython(self.dir, self.write(name + "_cpy.py", text.replace("{MSG}", "str(e)")), H_LOG=cpy_log)
        self.assertEqual(cpy.returncode, 0, cpy.stderr)
        self.assertEqual(cpy.stdout, expected_out)
        logged = Path(cpy_log).read_text() if Path(cpy_log).exists() else ""
        if expected_log is not None:
            self.assertEqual(logged, expected_log)
        source = self.write(name + "_ail.py", text.replace("{MSG}", "e.message"))
        for mode, _ in MODES:
            with self.subTest(mode):
                built, exe = compile_cli(self.dir, source, mode, "%s_%s.out" % (name, mode))
                self.assertEqual(built.returncode, 0, built.stderr + built.stdout)
                log = self.log("%s_%s.log" % (name, mode))
                ran = subprocess.run([str(exe)], cwd=self.dir, capture_output=True, text=True, timeout=60,
                                     env=dict(os.environ, H_LOG=log))
                self.assertEqual(ran.returncode, 0, ran.stderr)
                self.assertEqual(ran.stdout, cpy.stdout)
                self.assertEqual(Path(log).read_text() if Path(log).exists() else "", logged)
                self.exes[(name, mode)] = exe

    def test_counter_handles(self):
        self.compare("counter", COUNTER, COUNTER_OUT, COUNTER_LOG)

    def test_inline_annotation_and_bare_void_p(self):
        self.compare("inline", INLINE, INLINE_OUT)

    @unittest.skipUnless(have_sqlite(), "libsqlite3-dev (sqlite3.h and -lsqlite3) is not installed")
    def test_sqlite_wrapper(self):
        self.compare("sqlite", SQLITE, SQLITE_OUT)

    @unittest.skipUnless(libasan(), "libasan (AddressSanitizer runtime) is not installed")
    def test_no_leak_under_the_leak_checker(self):
        asan = libasan()
        env = dict(os.environ, LD_PRELOAD=asan, ASAN_OPTIONS="detect_leaks=1:abort_on_error=0", H_LOG=os.devnull)
        # the checker is on: a program that leaks is reported
        (self.dir / "leak.c").write_text("#include <stdlib.h>\nint main(void) { volatile char *p = malloc(64); p[0] = 1; p = 0; return 0; }\n")
        subprocess.run([CC, "-O0", "-o", str(self.dir / "leak"), str(self.dir / "leak.c")], check=True)
        leaked = subprocess.run([str(self.dir / "leak")], capture_output=True, text=True, env=env)
        if leaked.returncode == 0 or "LeakSanitizer" not in leaked.stderr:
            self.skipTest("the preloaded leak checker does not report in this environment")
        if not self.exes:
            self.test_counter_handles()
            self.test_inline_annotation_and_bare_void_p()
            if have_sqlite():
                self.test_sqlite_wrapper()
        self.assertTrue(self.exes)
        for (name, mode), exe in sorted(self.exes.items()):
            with self.subTest(name + "/" + mode):
                ran = subprocess.run([str(exe)], cwd=self.dir, capture_output=True, text=True, timeout=120, env=env)
                self.assertEqual(ran.returncode, 0, ran.stderr[-1500:])
                self.assertNotIn("LeakSanitizer", ran.stderr)

    # ------------------------------------------------------------------ refusals

    def refused(self, name, body, message, *, stubs=STUBS, expect_line=None):
        text = stubs + body
        self.write(name + ".py", text)
        built, _ = compile_cli(self.dir, name + ".py", "typed", name + ".out")
        self.assertNotEqual(built.returncode, 0, "%s was accepted" % name)
        self.assertIn(message, built.stderr)
        self.assertIn("write instead:", built.stderr)
        line = expect_line or next(i for i, t in enumerate(text.split("\n"), 1) if "#<" in t)
        self.assertRegex(built.stderr, r"%s\.py:%d:\d+" % (name, line))

    def test_arithmetic_on_a_handle_is_refused(self):
        cases = {
            "plus": "def main():\n    h = h_new(1)\n    x = h + 1  #<\n    print(x)\n\nmain()\n",
            "negate": "def main():\n    h = h_new(1)\n    print(-h)  #<\n\nmain()\n",
            "augmented": "def main():\n    h = h_new(1)\n    h += 2  #<\n\nmain()\n",
            "call": "def main():\n    print(h_new(1) * 2)  #<\n\nmain()\n",
            "parameter": "def twice(h: Counter) -> int:\n    return h * 2  #<\n\ndef main():\n    print(twice(h_new(1)))\n\nmain()\n",
            "copy": "def main():\n    h = h_new(1)\n    g = h\n    print(g - 1)  #<\n\nmain()\n",
        }
        for label, body in cases.items():
            with self.subTest(label):
                self.refused("arith_" + label, body, "arithmetic on the Handle")

    def test_a_handle_in_a_parallel_worker_is_refused(self):
        cases = {
            "par_range": "def main():\n    h = h_new(1)\n    for i in par_range(0, 4):  #<\n        h_next(h)\n\nmain()\n",
            "thread": ("from threading import Thread\n\ndef work(h: Counter) -> None:\n    h_next(h)\n\n"
                       "def main():\n    h = h_new(1)\n    t = Thread(target=work, args=(h,))  #<\n    t.start()\n    t.join()\n\nmain()\n"),
            "executor": ("from concurrent.futures import ThreadPoolExecutor\n\ndef work(h: Counter) -> int:\n    return h_next(h)\n\n"
                         "def main():\n    h = h_new(1)\n    with ThreadPoolExecutor(2) as ex:\n"
                         "        print(ex.submit(work, h).result())  #<\n\nmain()\n"),
        }
        for label, body in cases.items():
            with self.subTest(label):
                self.refused("par_" + label, body, "is passed into a parallel worker")

    def test_a_stub_that_calls_the_free_function_is_refused(self):
        stubs = STUBS + '@extern(lib="./libh.so", header="h.h")\ndef h_free(h: Counter) -> None: ...  #<\n'
        self.refused("freestub", "\ndef main():\n    pass\n\nmain()\n", "the free function of the counter Handle", stubs=stubs)

    def test_the_shim_has_no_arithmetic_either(self):
        text = STUBS + "\nh = h_new(1)\ntry:\n    h + 1\nexcept TypeError:\n    print('TypeError')\n"
        ran = run_cpython(self.dir, self.write("shim_arith.py", text), H_LOG=os.devnull)
        self.assertEqual((ran.returncode, ran.stdout), (0, "TypeError\n"), ran.stderr)

    def test_handle_declarations_are_checked(self):
        for label, text, message in (
                ("literal", 'from ail_ffi import *\nname = "x"\nDb = Handle(name, free="f")\n', "Handle("),
                ("twice", 'from ail_ffi import *\nA = Handle("x", free="f")\nB = Handle("x", free="f")\n', "is already declared as A"),
        ):
            with self.subTest(label):
                text += '@extern(lib="./libh.so", header="h.h")\ndef h_live() -> c_int: ...\n\nprint(h_live())\n'
                self.write("decl_" + label + ".py", text)
                built, _ = compile_cli(self.dir, "decl_" + label + ".py", "typed", "decl_" + label + ".out")
                self.assertNotEqual(built.returncode, 0)
                self.assertIn(message, built.stderr)

    # ------------------------------------------------------------------ programs without Handle

    def test_programs_without_handle_do_not_change(self):
        sys.path.insert(0, str(ROOT))
        try:
            import ail_ffi_lower
        finally:
            sys.path.pop(0)
        plain = 'from ail_ffi import *\n\n@extern(lib="./libh.so", header="h.h")\ndef h_live() -> c_int: ...\n\nprint(h_live())\n'
        session = ail_ffi_lower.Session(workdir=self.dir / "plain_work")
        (self.dir / "plain_work").mkdir(exist_ok=True)
        lowered = session.lower(self.dir / "plain.py", plain)
        self.assertNotIn("class ", lowered)
        self.assertNotIn("_reg", lowered)
        session.build(CLI)
        adapter = (self.dir / "plain_work" / "ffi_adapter.c").read_text()
        self.assertNotIn("ffi_owned", adapter)
        self.assertNotIn("FFI_SYM", adapter)
        self.assertEqual(session.listing()[0].get("owned_handles"), None)
        # a file that does not mention ail_ffi comes back byte for byte
        self.assertEqual(ail_ffi_lower.Session().lower(self.dir / "p.py", "print(1)\n"), "print(1)\n")

    def test_check_ffi_lists_the_handles(self):
        self.write("listed.py", STUBS + "\nprint(h_live())\n")
        env = dict(os.environ, PYTHONPATH=str(ROOT))
        done = subprocess.run([sys.executable, "-B", CLI, "check", "listed.py", "--ffi"], cwd=self.dir, capture_output=True,
                              text=True, timeout=300, env=env)
        self.assertIn("owned_handles", done.stdout + done.stderr)
        self.assertIn("h_next", done.stdout + done.stderr)


if __name__ == "__main__":
    unittest.main()

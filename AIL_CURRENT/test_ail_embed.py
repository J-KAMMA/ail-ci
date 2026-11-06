"""ffembed1: examples/embed builds static libraries whose ABI matches CPython.

* Each example module is plain Python and names its exports in `__ail_export__`.
* `ail_embed.py build` writes `lib<name>.a` and `<name>.h`; gcc -O2 links the
  example's test.c against them.
* The C test prints what CPython's `mod.py` prints, so `expected.txt` is the
  oracle.  The same test also checks ABI-only behaviour: int64 overflow is
  status 1 with OverflowError, a short result buffer is status 2, and a raised
  ValueError gives status 1 with the exact last_error text.
* A function that needs the general path is refused by name.
* `--shared` writes `lib<name>.so`; `use_ctypes.py` calls it through ctypes and
  compares every result with the module imported directly.
* A Rust caller per example (`rust/`, no dependencies) links the static library
  from `build.rs` and prints the same lines.
* Two pthreads calling exports at once are serialised by the library's lock:
  2 x 500 calls, 1000/1000 correct, also under `-fsanitize=thread` when gcc has
  it.
"""
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parent
CLI = ROOT / "ail_embed.py"
EXAMPLES = REPO / "examples" / "embed"
CC = os.environ.get("CC") or "gcc"
CASES = ("fib", "transform", "wordcount", "raiser")

THREADS_C = r'''
#include <pthread.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>
#include "fib.h"

#define CALLS 500

static int failures;

static long long slow_fib(long long n) {
    long long a = 0, b = 1, i;
    if (n < 2) return n;
    for (i = 2; i <= n; i++) {
        long long c = a + b;
        a = b;
        b = c;
    }
    return b;
}

static void *worker(void *arg) {
    intptr_t id = (intptr_t)arg;
    int i;
    for (i = 0; i < CALLS; i++) {
        int64_t v = 0;
        long long n = (i + id) % 30;
        if (fib_fib(n, &v) != 0 || v != slow_fib(n)) __atomic_add_fetch(&failures, 1, __ATOMIC_RELAXED);
        const char *text = id == 0 ? "a12 b34 c5" : "no digits";
        int64_t sum = 0;
        if (fib_sum_line(text, strlen(text), &sum) != 0 || sum != (id == 0 ? 51 : 0))
            __atomic_add_fetch(&failures, 1, __ATOMIC_RELAXED);
    }
    return NULL;
}

int main(void) {
    pthread_t threads[2];
    intptr_t id;
    fib_init();
    for (id = 0; id < 2; id++)
        if (pthread_create(&threads[id], NULL, worker, (void *)id) != 0) return 2;
    for (id = 0; id < 2; id++) pthread_join(threads[id], NULL);
    fib_shutdown();
    printf("%d/%d calls correct\n", 2 * CALLS - failures, 2 * CALLS);
    return failures == 0 ? 0 : 1;
}
'''


def run(command, **kwargs):
    return subprocess.run(command, capture_output=True, text=True, timeout=900, **kwargs)


def oracle_env():
    env = dict(os.environ, PYTHONUTF8="1")
    env.pop("PYTHONPATH", None)
    return env


def cargo_works():
    if not shutil.which("cargo"):
        return False
    try:
        return run(["cargo", "--version"]).returncode == 0
    except (OSError, subprocess.SubprocessError):
        return False


def thread_sanitizer_works():
    if not shutil.which(CC):
        return False
    with tempfile.TemporaryDirectory(prefix="ail-tsan-probe-") as tmp:
        source = Path(tmp) / "probe.c"
        source.write_text("int main(void) { return 0; }\n", encoding="utf-8")
        built = run([CC, "-fsanitize=thread", str(source), "-o", str(Path(tmp) / "probe")])
        if built.returncode != 0:
            return False
        return run([str(Path(tmp) / "probe")]).returncode == 0


@unittest.skipUnless(shutil.which(CC), "no C compiler available")
class EmbedExamples(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="ail-embed-test-")
        self.addCleanup(self.tmp.cleanup)
        self.dir = Path(self.tmp.name)

    def test_examples_match_cpython_and_abi(self):
        for case in CASES:
            with self.subTest(case=case):
                source = EXAMPLES / case / "mod.py"
                want = run([sys.executable, str(source)], cwd=source.parent, env=oracle_env())
                self.assertEqual(want.returncode, 0, want.stderr)
                expected = (EXAMPLES / case / "expected.txt").read_text(encoding="utf-8")
                self.assertEqual(want.stdout, expected, "%s expected.txt is not CPython's output" % case)
                out = self.dir / case
                built = run([sys.executable, "-B", str(CLI), "build", str(source), "-o", str(out)])
                self.assertEqual(built.returncode, 0, built.stderr)
                library = out / ("lib%s.a" % case)
                header = out / ("%s.h" % case)
                self.assertTrue(library.is_file(), built.stdout + built.stderr)
                self.assertTrue(header.is_file(), built.stdout + built.stderr)
                exe = out / "test"
                compiled = run([CC, "-O2", "-pthread", "-I" + str(out), str(EXAMPLES / case / "test.c"),
                                str(library), "-lm", "-o", str(exe)])
                self.assertEqual(compiled.returncode, 0, compiled.stderr)
                got = run([str(exe)], cwd=out)
                self.assertEqual(got.returncode, 0, got.stderr)
                self.assertEqual(got.stdout, expected)

    @unittest.skipUnless(cargo_works(), "cargo is not installed")
    def test_rust_examples_match_cpython(self):
        for case in CASES:
            with self.subTest(case=case):
                expected = (EXAMPLES / case / "expected.txt").read_text(encoding="utf-8")
                rust = EXAMPLES / case / "rust"
                target = self.dir / ("cargo-" + case)
                env = dict(oracle_env(), CARGO_TARGET_DIR=str(target), CARGO_NET_OFFLINE="true")
                built = run(["cargo", "build", "--release", "--offline"], cwd=rust, env=env)
                self.assertEqual(built.returncode, 0, built.stderr[-4000:])
                got = run([str(target / "release" / case)], cwd=rust)
                self.assertEqual(got.returncode, 0, got.stderr)
                self.assertEqual(got.stdout, expected)

    def test_shared_library_matches_cpython_through_ctypes(self):
        for case in CASES:
            with self.subTest(case=case):
                source = EXAMPLES / case / "mod.py"
                expected = (EXAMPLES / case / "expected.txt").read_text(encoding="utf-8")
                out = self.dir / ("shared-" + case)
                built = run([sys.executable, "-B", str(CLI), "build", str(source), "-o", str(out),
                             "--shared"])
                self.assertEqual(built.returncode, 0, built.stderr)
                library = out / ("lib%s.so" % case)
                self.assertTrue(library.is_file(), built.stdout + built.stderr)
                self.assertFalse((out / ("lib%s.a" % case)).exists())
                self.assertTrue((out / ("%s.h" % case)).is_file())
                got = run([sys.executable, "-B", str(EXAMPLES / case / "use_ctypes.py"),
                           "--lib", str(library)])
                self.assertEqual(got.returncode, 0, got.stderr)
                self.assertEqual(got.stdout, expected)

    def build_thread_test(self, cc=None, cflags=()):
        out = self.dir / ("threads" + ("-tsan" if cflags else ""))
        command = [sys.executable, "-B", str(CLI), "build", str(EXAMPLES / "fib" / "mod.py"),
                   "-o", str(out)]
        if cc:
            command += ["--cc", cc]
        built = run(command)
        self.assertEqual(built.returncode, 0, built.stderr)
        source = self.dir / "threads.c"
        source.write_text(THREADS_C, encoding="utf-8")
        exe = out / "threads"
        compiled = run([CC, *cflags, "-O2", "-pthread", "-I" + str(out), str(source),
                        str(out / "libfib.a"), "-lm", "-o", str(exe)])
        self.assertEqual(compiled.returncode, 0, compiled.stderr)
        return run([str(exe)], cwd=out)

    def test_two_threads_call_exports(self):
        got = self.build_thread_test()
        self.assertEqual(got.returncode, 0, got.stderr)
        self.assertEqual(got.stdout, "1000/1000 calls correct\n")

    @unittest.skipUnless(thread_sanitizer_works(), "gcc has no -fsanitize=thread")
    def test_two_threads_under_thread_sanitizer(self):
        got = self.build_thread_test("%s -fsanitize=thread" % CC, ("-fsanitize=thread",))
        self.assertEqual(got.returncode, 0, got.stderr)
        self.assertEqual(got.stdout, "1000/1000 calls correct\n")
        self.assertNotIn("ThreadSanitizer", got.stderr)

    def test_general_path_is_refused_by_name(self):
        source = self.dir / "slow.py"
        source.write_text(
            '__ail_export__ = ["find", "add"]\n'
            'def find(d: dict[int, int], k: int) -> int | None:\n'
            '    return d.get(k)\n'
            'def add(a: int, b: int) -> int:\n'
            '    return a + b\n', encoding="utf-8")
        out = self.dir / "slow"
        built = run([sys.executable, "-B", str(CLI), "build", str(source), "-o", str(out)])
        self.assertNotEqual(built.returncode, 0)
        self.assertIn("general path", built.stderr)
        self.assertIn("find", built.stderr)
        self.assertIn("add", built.stderr)
        self.assertFalse((out / "libslow.a").exists())

    def test_missing_export_list_is_an_error(self):
        source = self.dir / "plain.py"
        source.write_text("def f(x: int) -> int:\n    return x\n", encoding="utf-8")
        built = run([sys.executable, "-B", str(CLI), "build", str(source), "-o",
                     str(self.dir / "plain")])
        self.assertNotEqual(built.returncode, 0)
        self.assertIn("__ail_export__", built.stderr)


if __name__ == "__main__":
    unittest.main()

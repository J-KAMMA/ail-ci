"""Deep recursion stops loudly by name in every build mode (recstop1).

Before this test, a recursive function on the general path (`AIL_UNIFIED_FORCE=1`, and the
default build for a recursive method, which takes the general path) exhausted the C stack and
died with a bare SIGSEGV: exit 139 and nothing on stderr.  The typed path already stopped with
`RecursionError: maximum recursion depth exceeded`; the general path now checks each generated
entry's frame address against the current stack limit (a real stack check, not a frame count)
and raises the same named exception through its own exception path, so a `try` can catch it as
CPython's `RecursionError`/`RuntimeError`.

The owner decision of 2026-11-05 keeps recursion within the real stack working: AIL does not
emulate CPython's default limit of 1000, so depth 5000 and 12000 still complete (a documented
difference, docs/LIMITATIONS.md), and only real stack exhaustion stops.  A recursive function
with many locals used to overflow before any fixed frame cap could catch it; the stack check
stops it by name.
"""
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent
CLI = str(ROOT / "ail_chatgpt.py")

MODES = (("general", {"AIL_UNIFIED_FORCE": "1"}), ("default", {}))

DIRECT = '''def countdown(n: int) -> int:
    return countdown(n + 1)


print("prefix", 10)
print("start", countdown(0))
print("unreachable", 1)
'''

MUTUAL = '''def ping(n: int) -> int:
    return pong(n + 1)


def pong(n: int) -> int:
    return ping(n + 1)


print("prefix", 10)
print("start", ping(0))
print("unreachable", 1)
'''

METHOD = '''class Counter:
    def count(self, n: int) -> int:
        return self.count(n + 1)


print("prefix", 0)
print("start", Counter().count(0))
print("unreachable", 1)
'''

CATCH_RUNTIME = '''def countdown(n: int) -> int:
    return countdown(n + 1)


try:
    countdown(0)
except RuntimeError:
    print("caught runtime")
print("done")
'''

CATCH_EXACT = '''def countdown(n: int) -> int:
    return countdown(n + 1)


try:
    countdown(0)
except RecursionError:
    print("caught recursion")
print("done")
'''

FINALLY = '''def countdown(n: int) -> int:
    return countdown(n + 1)


def main():
    try:
        countdown(0)
    finally:
        print("finally")


main()
'''

DEEP = '''def descend(n: int) -> int:
    if n == 0:
        return 0
    return 1 + descend(n - 1)


print(descend(5000))
'''

# A depth that fits the real stack (CPython refuses at its default limit of 1000, which is the
# documented difference).  A fixed frame cap must not turn this into a RecursionError.
DEEP_12000 = '''def descend(n: int) -> int:
    if n == 0:
        return 0
    return 1 + descend(n - 1)


print(descend(12000))
'''

# Large activations: a frame count cannot bound the real stack for these, so this used to
# segfault even with a 10000-frame cap.
MANY_LOCALS = '''def descend(n: int) -> int:
    a0=0; a1=1; a2=2; a3=3; a4=4; a5=5; a6=6; a7=7; a8=8; a9=9
    b0=0; b1=1; b2=2; b3=3; b4=4; b5=5; b6=6; b7=7; b8=8; b9=9
    c0=0; c1=1; c2=2; c3=3; c4=4; c5=5; c6=6; c7=7; c8=8; c9=9
    d0=0; d1=1; d2=2; d3=3; d4=4; d5=5; d6=6; d7=7; d8=8; d9=9
    e0=0; e1=1; e2=2; e3=3; e4=4; e5=5; e6=6; e7=7; e8=8; e9=9
    f0=0; f1=1; f2=2; f3=3; f4=4; f5=5; f6=6; f7=7; f8=8; f9=9
    if n == 0:
        return a0 + b0 + c0 + d0 + e0 + f0
    return 1 + descend(n - 1) + (a9 + b9 + c9 + d9 + e9 + f9) * 0


print(descend(100000))
'''

NESTED = '''def outer():
    def inner(n: int) -> int:
        return inner(n + 1)
    return inner(0)


print(outer())
'''

VARARGS = '''def f(*rest):
    return f(*rest)


print(f())
'''

GENERATOR = '''def g(n):
    yield from g(n + 1)


print(next(g(0)))
'''


def _run_cpython(directory, text):
    src = Path(directory) / "probe.py"
    src.write_text(text, encoding="utf-8")
    got = subprocess.run([sys.executable, "-B", str(src)], capture_output=True, timeout=120)
    return got.stdout.decode("utf-8", "replace"), got.returncode


def _build_and_run(directory, name, text, env_extra):
    src = Path(directory) / (name + ".py")
    src.write_text(text, encoding="utf-8")
    exe = Path(directory) / ("exe_" + name)
    env = dict(os.environ, AIL_NO_CACHE="1", AIL_QUIET_FALLBACK="1", **env_extra)
    env.pop("AIL_NO_GENERAL", None)
    if "AIL_UNIFIED_FORCE" not in env_extra:
        env.pop("AIL_UNIFIED_FORCE", None)
    built = subprocess.run([sys.executable, "-B", CLI, "compile", src.name, "--syntax", "python",
                            "-o", exe.name], cwd=directory, capture_output=True, text=True,
                           timeout=900, env=env)
    if built.returncode != 0:
        return None, (built.stdout + built.stderr)[-2000:]
    got = subprocess.run([str(exe)], capture_output=True, timeout=120, cwd=directory)
    return got, ""


def _last_line(stderr):
    lines = [line.rstrip() for line in stderr.decode("utf-8", "replace").splitlines() if line.strip()]
    return lines[-1] if lines else ""


class RecursionStop(unittest.TestCase):
    def test_three_shapes_stop_by_name(self):
        for slug, text in (("direct", DIRECT), ("mutual", MUTUAL), ("method", METHOD)):
            with tempfile.TemporaryDirectory(prefix="ail-recstop-") as directory:
                want_out, want_rc = _run_cpython(directory, text)
                self.assertNotEqual(want_rc, 0)
                for mode, env_extra in MODES:
                    got, err = _build_and_run(directory, "%s_%s" % (slug, mode), text, env_extra)
                    self.assertIsNotNone(got, "%s/%s\n%s" % (slug, mode, err))
                    self.assertEqual(got.stdout.decode("utf-8", "replace"), want_out,
                                     "%s/%s stdout" % (slug, mode))
                    self.assertNotEqual(got.returncode, 0, "%s/%s exit" % (slug, mode))
                    self.assertTrue(_last_line(got.stderr).startswith("RecursionError:"),
                                    "%s/%s stderr: %r" % (slug, mode, got.stderr[-400:]))

    def test_catchable_like_cpython(self):
        for slug, text in (("catch_runtime", CATCH_RUNTIME), ("catch_exact", CATCH_EXACT)):
            with tempfile.TemporaryDirectory(prefix="ail-recstop-") as directory:
                want_out, want_rc = _run_cpython(directory, text)
                self.assertEqual(want_rc, 0)
                for mode, env_extra in MODES:
                    got, err = _build_and_run(directory, "%s_%s" % (slug, mode), text, env_extra)
                    self.assertIsNotNone(got, "%s/%s\n%s" % (slug, mode, err))
                    self.assertEqual((got.stdout.decode("utf-8", "replace"), got.returncode),
                                     (want_out, want_rc), "%s/%s" % (slug, mode))

    def test_finally_runs_and_stop_is_named(self):
        with tempfile.TemporaryDirectory(prefix="ail-recstop-") as directory:
            want_out, want_rc = _run_cpython(directory, FINALLY)
            for mode, env_extra in MODES:
                got, err = _build_and_run(directory, "finally_" + mode, FINALLY, env_extra)
                self.assertIsNotNone(got, err)
                self.assertEqual(got.stdout.decode("utf-8", "replace"), want_out, mode)
                self.assertEqual(got.returncode, want_rc, mode)
                self.assertTrue(_last_line(got.stderr).startswith("RecursionError:"), mode)

    def test_depth_5000_still_completes(self):
        with tempfile.TemporaryDirectory(prefix="ail-recstop-") as directory:
            for mode, env_extra in MODES:
                got, err = _build_and_run(directory, "deep_" + mode, DEEP, env_extra)
                self.assertIsNotNone(got, err)
                self.assertEqual(got.returncode, 0, mode)
                self.assertEqual(got.stdout.decode("utf-8", "replace"), "5000\n", mode)

    def test_depth_12000_still_completes(self):
        # The regression the review found: a 10000-frame cap refused a depth the real stack
        # holds (12000 completed before the guard existed).  CPython itself refuses at 1000.
        with tempfile.TemporaryDirectory(prefix="ail-recstop-") as directory:
            for mode, env_extra in MODES:
                got, err = _build_and_run(directory, "deep12k_" + mode, DEEP_12000, env_extra)
                self.assertIsNotNone(got, err)
                self.assertEqual(got.returncode, 0, mode)
                self.assertEqual(got.stdout.decode("utf-8", "replace"), "12000\n", mode)
                self.assertEqual(_last_line(got.stderr), "", mode)

    def test_many_locals_stops_by_name(self):
        # A frame count cannot bound the real stack: this activation is about 1 KiB, so the old
        # guard was above the real limit and the program died with SIGSEGV.
        with tempfile.TemporaryDirectory(prefix="ail-recstop-") as directory:
            want_out, want_rc = _run_cpython(directory, MANY_LOCALS)
            self.assertNotEqual(want_rc, 0)
            for mode, env_extra in MODES:
                got, err = _build_and_run(directory, "manylocals_" + mode, MANY_LOCALS, env_extra)
                self.assertIsNotNone(got, err)
                self.assertEqual(got.stdout.decode("utf-8", "replace"), want_out, mode)
                self.assertNotEqual(got.returncode, 0, mode)
                self.assertTrue(_last_line(got.stderr).startswith("RecursionError:"),
                                "%s: %r" % (mode, got.stderr[-400:]))

    def test_nested_def_recursion_stops_by_name(self):
        with tempfile.TemporaryDirectory(prefix="ail-recstop-") as directory:
            for mode, env_extra in MODES:
                got, err = _build_and_run(directory, "nested_" + mode, NESTED, env_extra)
                self.assertIsNotNone(got, err)
                self.assertNotEqual(got.returncode, 0, mode)
                self.assertTrue(_last_line(got.stderr).startswith("RecursionError:"), mode)

    def test_varargs_and_generator_recursion_stop_by_name(self):
        for slug, text in (("varargs", VARARGS), ("generator", GENERATOR)):
            with tempfile.TemporaryDirectory(prefix="ail-recstop-") as directory:
                want_out, want_rc = _run_cpython(directory, text)
                self.assertNotEqual(want_rc, 0)
                for mode, env_extra in MODES:
                    got, err = _build_and_run(directory, "%s_%s" % (slug, mode), text, env_extra)
                    self.assertIsNotNone(got, err)
                    self.assertEqual(got.stdout.decode("utf-8", "replace"), want_out, "%s/%s" % (slug, mode))
                    self.assertNotEqual(got.returncode, 0, "%s/%s" % (slug, mode))
                    self.assertTrue(_last_line(got.stderr).startswith("RecursionError:"),
                                    "%s/%s: %r" % (slug, mode, got.stderr[-400:]))


if __name__ == "__main__":
    unittest.main()

"""Deep recursion stops loudly by name in every build mode (recstop1).

Before this test, a recursive function on the general path (`AIL_UNIFIED_FORCE=1`, and the
default build for a recursive method, which takes the general path) exhausted the C stack and
died with a bare SIGSEGV: exit 139 and nothing on stderr.  The typed path already stopped with
`RecursionError: maximum recursion depth exceeded`; the general path now keeps the same depth
count on its frames (AIL_FRAME_ENTER/LEAVE) and raises the same named exception through its own
exception path, so a `try` can catch it as CPython's `RecursionError`/`RuntimeError`.

The owner decision of 2026-11-05 keeps recursion within the real stack working: AIL does not
emulate CPython's default limit of 1000, so depth 5000 still completes (a documented difference,
docs/LIMITATIONS.md), and only real stack exhaustion stops.
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

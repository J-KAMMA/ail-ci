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

try:
    import resource
except ImportError:          # Windows: the unlimited-stack test is skipped there
    resource = None

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

# A `yield from` chain of 12000 runs each generator on its own stack, so it fits: the owner
# decision forbids an artificial nesting cap, and CPython's own limit of 1000 is the documented
# difference (docs/LIMITATIONS.md).  A fixed frame counter used to refuse this depth.
GENERATOR_CHAIN = '''def g(n):
    if n == 0:
        yield 1
    else:
        yield from g(n - 1)


print(next(g(12000)))
'''

# The caught trap must be a RecursionError instance, not a plain RuntimeError that an alias or a
# `type(e)` read reports by the wrong name; `except RecursionError` must not take plain
# RuntimeErrors (its CPython subclass relation is one-way).
CAUGHT_CLASS = '''def countdown(n: int) -> int:
    return countdown(n + 1)


try:
    countdown(0)
except RuntimeError as e:
    print(type(e).__name__)
    print(isinstance(e, RecursionError))
    print(isinstance(e, RuntimeError))
'''

# `type(e) is X` needs the typed path (the general path refuses the `type` builtin by name).
TYPED_CLASS = '''def countdown(n: int) -> int:
    return countdown(n + 1)


try:
    countdown(0)
except RuntimeError as e:
    print(type(e) is RecursionError)
    print(type(e) is RuntimeError)
'''

ONE_WAY = '''def countdown(n: int) -> int:
    return countdown(n + 1)


try:
    countdown(0)
except RecursionError:
    print("recursion")
try:
    raise RuntimeError("plain")
except RecursionError:
    print("WRONG")
except RuntimeError:
    print("runtime")
'''

# A depth that needs more than the old hard-coded 8 MiB fallback (`f(300000)` uses roughly
# 20 MiB of frames); under `ulimit -s unlimited` the stack really is larger, so this must
# complete as it did before the guard existed.
UNLIMITED = '''def descend(n: int) -> int:
    if n == 0:
        return 0
    return 1 + descend(n - 1)


print(descend(300000))
'''


def _run_cpython(directory, text):
    src = Path(directory) / "probe.py"
    src.write_text(text, encoding="utf-8")
    got = subprocess.run([sys.executable, "-B", str(src)], capture_output=True, timeout=120)
    return got.stdout.decode("utf-8", "replace"), got.returncode


# Every built program runs in a child with its own limits, set inside the child: an address-space
# cap (so an unbounded chain of generators, each on its own mmap'd stack, stops when the OS can no
# longer map one instead of growing until the machine runs out of memory) and a wall-clock timeout
# (a hang is a failure, never a pass).
CHILD_AS = 1 << 30
CHILD_TIMEOUT = 60
GEN_STACK = 8 << 20           # AIL2G_STACK in safetyrt.py: each generator's own mapped stack


def _current_as_limit():
    if resource is None:
        return None
    soft = resource.getrlimit(resource.RLIMIT_AS)[0]
    return None if soft == resource.RLIM_INFINITY else soft


def _child_limits(as_bytes):
    """preexec_fn that caps the child's address space (never above the parent's own cap)."""
    if resource is None or as_bytes is None or not sys.platform.startswith("linux"):
        return None
    parent = _current_as_limit()
    if parent is not None:
        as_bytes = min(as_bytes, parent)

    def limit():
        resource.setrlimit(resource.RLIMIT_AS, (as_bytes, as_bytes))
    return limit


def _run_child(cmd, directory, as_bytes=CHILD_AS, preexec=None):
    limit = _child_limits(as_bytes)

    def setup():
        if limit is not None:
            limit()
        if preexec is not None:
            preexec()
    try:
        return subprocess.run(cmd, capture_output=True, timeout=CHILD_TIMEOUT, cwd=directory,
                              preexec_fn=setup if (limit or preexec) else None)
    except subprocess.TimeoutExpired as error:
        raise AssertionError("%s did not stop within %d s (a hang, not a loud stop)"
                             % (cmd[0], CHILD_TIMEOUT)) from error


def _build_and_run(directory, name, text, env_extra, as_bytes=CHILD_AS):
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
    got = _run_child([str(exe)], directory, as_bytes)
    return got, ""


def _last_line(stderr):
    lines = [line.rstrip() for line in stderr.decode("utf-8", "replace").splitlines() if line.strip()]
    return lines[-1] if lines else ""


def _run_unlimited(exe, directory):
    """Run a built program with RLIMIT_STACK unlimited, as `ulimit -s unlimited` does."""
    def unlimit():
        resource.setrlimit(resource.RLIMIT_STACK, (resource.RLIM_INFINITY, resource.RLIM_INFINITY))
    return _run_child([str(exe)], directory, CHILD_AS, preexec=unlimit)


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
                    # The unbounded generator chain ends when the child's address-space cap
                    # refuses the next generator stack: a named stop either way.
                    names = ("RecursionError:", "MemoryError") if slug == "generator" \
                        else ("RecursionError:",)
                    self.assertTrue(_last_line(got.stderr).startswith(names),
                                    "%s/%s: %r" % (slug, mode, got.stderr[-400:]))

    def test_caught_stop_is_a_recursionerror_instance(self):
        # The review's p23/p12 defect: the trap was carried as plain RuntimeError, so an alias
        # read back RuntimeError and `type(e).__name__`/isinstance lied.
        with tempfile.TemporaryDirectory(prefix="ail-recstop-") as directory:
            want_out, want_rc = _run_cpython(directory, CAUGHT_CLASS)
            self.assertEqual(want_rc, 0)
            for mode, env_extra in MODES:
                got, err = _build_and_run(directory, "caught_class_" + mode, CAUGHT_CLASS, env_extra)
                self.assertIsNotNone(got, "%s\n%s" % (mode, err))
                self.assertEqual((got.stdout.decode("utf-8", "replace"), got.returncode),
                                 (want_out, want_rc), mode)

    def test_caught_stop_exact_type(self):
        with tempfile.TemporaryDirectory(prefix="ail-recstop-") as directory:
            want_out, want_rc = _run_cpython(directory, TYPED_CLASS)
            self.assertEqual(want_rc, 0)
            for mode, env_extra in MODES[1:]:        # the general path refuses `type` by name
                got, err = _build_and_run(directory, "typed_class_" + mode, TYPED_CLASS, env_extra)
                self.assertIsNotNone(got, "%s\n%s" % (mode, err))
                self.assertEqual((got.stdout.decode("utf-8", "replace"), got.returncode),
                                 (want_out, want_rc), mode)

    def test_except_recursionerror_does_not_catch_runtimeerror(self):
        with tempfile.TemporaryDirectory(prefix="ail-recstop-") as directory:
            want_out, want_rc = _run_cpython(directory, ONE_WAY)
            self.assertEqual(want_rc, 0)
            for mode, env_extra in MODES:
                got, err = _build_and_run(directory, "one_way_" + mode, ONE_WAY, env_extra)
                self.assertIsNotNone(got, "%s\n%s" % (mode, err))
                self.assertEqual((got.stdout.decode("utf-8", "replace"), got.returncode),
                                 (want_out, want_rc), mode)

    def test_generator_chain_12000_completes(self):
        # An artificial nesting cap refused this depth; each generator has its own stack and the
        # chain used to complete.  CPython refuses at its default limit 1000 (documented
        # difference), so the oracle here is the base behaviour, not CPython.
        # Each generator reserves GEN_STACK of address space (MAP_NORESERVE: its RSS is a few
        # pages), so the depth is derived from the address space this test may use: 12000 (above
        # the old 10000 cap) when no cap is set, fewer under one such as `ulimit -v 2500000`.
        # The child always runs with an explicit cap sized for that depth.
        headroom = 512 << 20
        parent = _current_as_limit()
        depth = 12000 if parent is None else max(50, min(12000, (parent - headroom) * 4 // 5 // GEN_STACK))
        budget = depth * GEN_STACK + headroom
        text = GENERATOR_CHAIN.replace("g(12000)", "g(%d)" % depth)
        with tempfile.TemporaryDirectory(prefix="ail-recstop-") as directory:
            for mode, env_extra in MODES:
                got, err = _build_and_run(directory, "gen_chain_" + mode, text, env_extra,
                                          as_bytes=budget)
                self.assertIsNotNone(got, "%s\n%s" % (mode, err))
                self.assertEqual(got.returncode, 0, "%s depth %d: %r" % (mode, depth, got.stderr[-400:]))
                self.assertEqual(got.stdout.decode("utf-8", "replace"), "1\n", mode)

    @unittest.skipUnless(resource is not None and sys.platform.startswith("linux"),
                         "RLIMIT_STACK manipulation needs POSIX resource limits")
    def test_unlimited_stack_keeps_a_deep_recursion_working(self):
        # The old hard-coded 8 MiB fallback for RLIM_INFINITY refused depth 300000; the real
        # (unlimited) stack holds it, so it must complete.  Only the general path has no typed
        # call counter (the typed path's own 50000 limit is separate).
        with tempfile.TemporaryDirectory(prefix="ail-recstop-") as directory:
            got, err = _build_and_run(directory, "unlimited_g", UNLIMITED,
                                      {"AIL_UNIFIED_FORCE": "1"})
            self.assertIsNotNone(got, err)
            try:
                ran = _run_unlimited(Path(directory) / "exe_unlimited_g", directory)
            except (ValueError, OSError) as error:
                self.skipTest("RLIMIT_STACK cannot be made unlimited here: %s" % error)
            self.assertEqual(ran.stdout.decode("utf-8", "replace"), "300000\n",
                             ran.stderr[-400:])
            self.assertEqual(ran.returncode, 0, ran.stderr[-400:])


if __name__ == "__main__":
    unittest.main()

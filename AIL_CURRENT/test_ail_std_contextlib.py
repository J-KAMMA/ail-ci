"""Stdlib coverage: the contextlib programs in lab/stdlib/contextlib, compared with CPython 3.12.

The ten programs that build use @contextmanager (plain and on a method), suppress, closing, nullcontext,
ExitStack (enter_context / push / callback / pop_all / close) and chdir.  Each is ordinary Python: CPython
runs it as the oracle and the compiled program must print the same bytes and exit with the same status.
The two redirect_stdout / redirect_stderr programs are still refused by name (see RESULTS.md).
"""
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent
LAB = ROOT.parent / "lab" / "stdlib" / "contextlib"
CLI = ROOT / "ail_chatgpt.py"

PASSING = [
    "chdir_context.py",
    "closing_demo.py",
    "contextmanager_basic.py",
    "contextmanager_edges.py",
    "contextmanager_methods.py",
    "custom_manager.py",
    "exitstack_basic.py",
    "exitstack_nested.py",
    "nullcontext_demo.py",
    "suppress_errors.py",
]


def run_python(source, cwd):
    return subprocess.run([sys.executable, "-B", str(source)], cwd=cwd, capture_output=True, timeout=120,
                          env=dict(os.environ, PYTHONUTF8="1"))


def compile_program(source, cwd, exe):
    env = dict(os.environ, AIL_NO_CACHE="1", AIL_QUIET_FALLBACK="1")
    env.pop("AIL_NO_GENERAL", None)
    env.pop("AIL_UNIFIED_FORCE", None)
    return subprocess.run([sys.executable, "-B", str(CLI), "compile", source.name, "--syntax", "python",
                           "-o", exe.name], cwd=cwd, capture_output=True, text=True, timeout=900, env=env)


class StdContextlibTests(unittest.TestCase):
    def check(self, name):
        text = (LAB / name).read_text(encoding="utf-8")
        with tempfile.TemporaryDirectory(prefix="ail-ctxlab-") as tmp:
            tmp = Path(tmp)
            source = tmp / "prog.py"
            source.write_text(text, encoding="utf-8")
            oracle = tmp / "oracle"
            oracle.mkdir()
            want = run_python(source, oracle)
            self.assertEqual(want.returncode, 0, want.stderr.decode("utf-8", "replace"))

            built = compile_program(source, tmp, tmp / "prog_exe")
            self.assertEqual(built.returncode, 0,
                             "%s: %s" % (name, (built.stdout + built.stderr)[-3000:]))
            self.assertNotIn("not in the subset", built.stderr)
            run_dir = tmp / "run"
            run_dir.mkdir()
            got = subprocess.run([str(tmp / "prog_exe")], cwd=run_dir, capture_output=True, timeout=120)
            self.assertEqual(got.returncode, want.returncode, got.stderr.decode("utf-8", "replace")[-2000:])
            if got.stdout != want.stdout:
                a = want.stdout.decode("utf-8", "replace").splitlines()
                b = got.stdout.decode("utf-8", "replace").splitlines()
                for i in range(max(len(a), len(b))):
                    x = a[i] if i < len(a) else "<none>"
                    y = b[i] if i < len(b) else "<none>"
                    if x != y:
                        self.fail("%s line %d: CPython %r, AIL %r" % (name, i + 1, x[:200], y[:200]))
            self.assertEqual(got.stdout, want.stdout, name)

    def test_programs_match_cpython(self):
        for name in PASSING:
            with self.subTest(program=name):
                self.check(name)

    def test_redirects_are_refused_by_name(self):
        for name, function in (("redirect_stdout_capture.py", "redirect_stdout"),
                               ("redirect_stderr_capture.py", "redirect_stderr")):
            with tempfile.TemporaryDirectory(prefix="ail-ctxlab-") as tmp:
                tmp = Path(tmp)
                source = tmp / "prog.py"
                source.write_text((LAB / name).read_text(encoding="utf-8"), encoding="utf-8")
                built = compile_program(source, tmp, tmp / "prog_exe")
                self.assertNotEqual(built.returncode, 0)
                self.assertIn("contextlib." + function + " is not built", built.stderr)


if __name__ == "__main__":
    unittest.main()

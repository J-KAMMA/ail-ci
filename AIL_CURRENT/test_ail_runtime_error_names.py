"""An uncaught runtime trap names the CPython exception and the source line in the default build.

The default typed build used to print only the runtime's own message (`list index out of range`).
The uncaught tail now prefixes the CPython exception name and records the statement's source line,
without changing stdout or the exit status; a caught exception prints nothing.  Explicit raises
already carry a name and must not be prefixed twice.  The forced general path (`AIL_UNIFIED_FORCE=1`)
prints the name but no source line.  The unified recursion probe is left out: that path currently
segfaults instead of reporting the trap (a separate bug).
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
CC = os.environ.get("PIPE_CC") or shutil.which("cc") or shutil.which("gcc") or shutil.which("clang")

# name: (source, needle, exception name, default message, unified message or None to skip)
CASES = {
    "index": ('''def main():
    xs: list[int] = [1, 2, 3]
    print(xs[5])
main()
''', "print(xs[5])", "IndexError", "list index out of range", "list index out of range"),
    "key": ('''def main():
    d: dict[str, int] = {"a": 1}
    print(d["b"])
main()
''', 'print(d["b"])', "KeyError", "key error", "'b'"),
    "zero": ('''def main():
    n = 0
    print(10 // n)
main()
''', "print(10 // n)", "ZeroDivisionError", "integer division by zero",
     "integer division or modulo by zero"),
    "recursion": ('''def f(n: int) -> int:
    return f(n + 1)
def main():
    print(f(0))
main()
''', "return f(n + 1)", "RecursionError", "recursion depth exceeded", None),
    "pop": ('''def main():
    xs: list[int] = []
    print(xs.pop())
main()
''', "print(xs.pop())", "IndexError", "pop from empty list", "pop from empty list"),
    "explicit": ('''def main():
    print("before")
    raise ValueError("bad n")
main()
''', 'raise ValueError("bad n")', "ValueError", "bad n", "bad n"),
}

CAUGHT = '''def main():
    xs: list[int] = [1]
    try:
        print(xs[5])
    except IndexError:
        print("caught")
main()
'''


@unittest.skipUnless(CC, "installed C compiler required")
class RuntimeErrorNames(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="ail-runtime-error-")
        self.addCleanup(self.tmp.cleanup)
        self.dir = Path(self.tmp.name)
        self.env = dict(os.environ, AIL_NO_CACHE="1", AIL_QUIET_FALLBACK="1", PYTHONUTF8="1")
        for key in ("AIL_DEBUG", "AIL_LINE_MAP", "AIL_UNIFIED_FORCE"):
            self.env.pop(key, None)

    def build(self, name, text, unified):
        source = self.dir / (name + ".py")
        source.write_text(text, encoding="utf-8")
        exe = self.dir / (name + ("_unified" if unified else "_default"))
        exe.unlink(missing_ok=True)
        env = dict(self.env)
        if unified:
            env["AIL_UNIFIED_FORCE"] = "1"
        done = subprocess.run([sys.executable, "-B", CLI, "compile", str(source), "-o", str(exe)],
                              capture_output=True, text=True, encoding="utf-8", env=env, timeout=900)
        self.assertEqual(done.returncode, 0, done.stdout + done.stderr)
        return source, exe

    @staticmethod
    def last_line(stderr):
        lines = [line for line in stderr.splitlines() if not line.startswith("  raised near ")]
        return lines[-1] if lines else ""

    def test_uncaught_traps_name_the_exception(self):
        for name, (text, needle, kind, message, unified_message) in CASES.items():
            line = next(number for number, body in enumerate(text.splitlines(), 1)
                        if needle in body)
            source, _ = self.build(name, text, False)
            cpython = subprocess.run([sys.executable, str(source)],
                                     capture_output=True, text=True, encoding="utf-8", timeout=120)
            cpython_last = self.last_line(cpython.stderr)
            for unified in (False, True):
                if unified and unified_message is None:
                    continue
                with self.subTest(name=name, unified=unified):
                    source, exe = self.build(name, text, unified)
                    done = subprocess.run([str(exe)], capture_output=True, text=True,
                                          encoding="utf-8", timeout=120)
                    self.assertEqual(done.returncode, 1)
                    self.assertEqual(done.stdout, cpython.stdout)
                    expected = "%s: %s\n" % (kind, unified_message if unified else message)
                    if not unified:
                        expected += "  raised near %s:%d\n" % (source, line)
                    self.assertEqual(done.stderr, expected)
                    # CPython's last traceback line: the name always, the whole line where AIL's
                    # trap message has the same wording (IndexError, pop, an explicit raise).
                    self.assertTrue(self.last_line(done.stderr).startswith(kind + ": "))
                    if name in ("index", "pop", "explicit") or unified:
                        self.assertEqual(self.last_line(done.stderr), cpython_last)

    def test_a_caught_exception_prints_nothing(self):
        for unified in (False, True):
            with self.subTest(unified=unified):
                _, exe = self.build("caught", CAUGHT, unified)
                done = subprocess.run([str(exe)], capture_output=True, text=True,
                                      encoding="utf-8", timeout=120)
                self.assertEqual((done.returncode, done.stdout, done.stderr), (0, "caught\n", ""))


if __name__ == "__main__":
    unittest.main()

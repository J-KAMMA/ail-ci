"""fuzz60: reading an exception's chain attributes without a `raise ... from` was a silent difference.

The general path refused `raise X from Y` in a program that reads `__cause__`, `__context__`,
`__suppress_context__` or `__traceback__`, but only because the raise node carried a cause. A program
that read one of those attributes WITHOUT `raise ... from` built, then raised
`AttributeError: 'instance' object has no attribute '__context__'` at run time, where CPython
prints None / False. Those attributes are now refused by name in both emitters (pyboxed2 and
pyboxed), on the default build and the forced general path.
"""
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent
CLI = str(ROOT / "ail_chatgpt.py")

READ_CONTEXT = r"""def f() -> None:
    try:
        int("x")
    except ValueError as e:
        print(e.__context__)

f()
"""

READ_CAUSE = r"""def f(flag: bool) -> None:
    try:
        int("x")
    except ValueError as e:
        if flag:
            print(e.__cause__)
        else:
            print(e.__suppress_context__)

f(True)
f(False)
"""

READ_TRACEBACK = r"""def f() -> None:
    try:
        int("x")
    except ValueError as e:
        print(e.__traceback__)

f()
"""

WRITE_CAUSE = r"""def f() -> None:
    try:
        int("x")
    except ValueError as e:
        e.__cause__ = None
        print(e.__cause__)

f()
"""

CASES = (
    ("context", READ_CONTEXT, "__context__"),
    ("cause+suppress", READ_CAUSE, "__cause__"),
    ("traceback", READ_TRACEBACK, "__traceback__"),
    ("write", WRITE_CAUSE, "__cause__"),
)


class ChainAttributes(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="ail-fuzz60-")
        self.dir = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def build(self, src, general):
        path = self.dir / "p.py"
        path.write_text(src, encoding="utf-8")
        env = dict(os.environ, AIL_NO_CACHE="1", AIL_QUIET_FALLBACK="1")
        env.pop("AIL_UNIFIED_FORCE", None)
        if general:
            env["AIL_UNIFIED_FORCE"] = "1"
        exe = self.dir / ("exe_g" if general else "exe_d")
        built = subprocess.run([sys.executable, "-B", CLI, "compile", str(path), "--syntax", "python",
                                "-o", str(exe)], cwd=self.dir, capture_output=True, text=True, env=env)
        return built

    def test_chain_attributes_refused_on_both_builds(self):
        for name, src, attr in CASES:
            with self.subTest(name=name):
                ref = self.dir / "ref.py"
                ref.write_text(src, encoding="utf-8")
                want = subprocess.run([sys.executable, str(ref)], cwd=self.dir, capture_output=True, timeout=60)
                self.assertEqual(want.returncode, 0, want.stderr)
                for general in (False, True):
                    built = self.build(src, general)
                    text = built.stdout + built.stderr
                    self.assertNotEqual(built.returncode, 0, "built a program whose output would differ")
                    self.assertIn(attr, text)
                    self.assertIn("exception chaining", text)


if __name__ == "__main__":
    unittest.main()

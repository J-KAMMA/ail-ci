"""ffembed1: examples/embed builds static libraries whose ABI matches CPython.

* Each example module is plain Python and names its exports in `__ail_export__`.
* `ail_embed.py build` writes `lib<name>.a` and `<name>.h`; gcc -O2 links the
  example's test.c against them.
* The C test prints what CPython's `mod.py` prints, so `expected.txt` is the
  oracle.  The same test also checks ABI-only behaviour: int64 overflow is
  status 1 with OverflowError, a short result buffer is status 2, and a raised
  ValueError gives status 1 with the exact last_error text.
* A function that needs the general path is refused by name.
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


def run(command, **kwargs):
    return subprocess.run(command, capture_output=True, text=True, timeout=900, **kwargs)


def oracle_env():
    env = dict(os.environ, PYTHONUTF8="1")
    env.pop("PYTHONPATH", None)
    return env


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
                compiled = run([CC, "-O2", "-I" + str(out), str(EXAMPLES / case / "test.c"),
                                str(library), "-lm", "-o", str(exe)])
                self.assertEqual(compiled.returncode, 0, compiled.stderr)
                got = run([str(exe)], cwd=out)
                self.assertEqual(got.returncode, 0, got.stderr)
                self.assertEqual(got.stdout, expected)

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

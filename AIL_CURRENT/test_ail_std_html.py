"""html2: `import html` in compiled programs (bundled stdlib/html/) against CPython's html.

The twelve programs in lab/stdlib/html/ use escape, unescape, the numeric and named character
references, the entities tables and a small tag stripper the way ordinary code does.  Each is
compiled with the default command (and again with AIL_UNIFIED_FORCE=1) and run beside `python3`
on the same source; stdout and the exit status must agree.  The escape-only programs must build
with no general-path note.
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
PROGRAMS = ROOT.parent / "lab" / "stdlib" / "html"
CC = os.environ.get("PIPE_CC") or shutil.which("cc") or shutil.which("gcc")

ESCAPE_ONLY = ("01_escape_quote_true.py", "02_escape_quote_false.py", "03_escape_alias.py")


def run_cpython(path):
    env = dict(os.environ)
    env.pop("PYTHONPATH", None)
    return subprocess.run([sys.executable, "-B", str(path)], cwd=str(path.parent),
                          capture_output=True, text=True, timeout=120, env=env)


@unittest.skipUnless(CC, "installed C compiler required")
class StdlibHtmlTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory(prefix="ail-html-test-")
        cls.dir = Path(cls.temp.name)
        cls.sources = sorted(PROGRAMS.glob("*.py"))

    @classmethod
    def tearDownClass(cls):
        cls.temp.cleanup()

    def test_lab_programs_exist(self):
        self.assertEqual([p.name for p in self.sources],
                         ["01_escape_quote_true.py", "02_escape_quote_false.py",
                          "03_escape_alias.py", "04_unescape_named.py",
                          "05_unescape_numeric.py", "06_unescape_invalid.py",
                          "07_unescape_plain.py", "08_entities_tables.py",
                          "09_entities_html5.py", "10_strip_tags.py",
                          "11_roundtrip.py", "12_mixed.py"])

    def _build_and_run(self, source, build_env):
        work = self.dir / (source.stem + "-" + str(len(list(self.dir.iterdir()))))
        work.mkdir(parents=True, exist_ok=True)
        program = work / source.name
        shutil.copyfile(source, program)
        exe = work / (source.stem + ".out")
        built = subprocess.run([sys.executable, "-B", CLI, "compile", str(program),
                                "--syntax", "python", "-o", str(exe)],
                               cwd=str(work), capture_output=True, text=True,
                               timeout=1800, env=build_env)
        self.assertEqual(built.returncode, 0, built.stdout + built.stderr)
        expected = run_cpython(program)
        ran = subprocess.run([str(exe)], cwd=str(work), capture_output=True,
                             text=True, timeout=120)
        self.assertEqual(ran.returncode, expected.returncode,
                         "%s exit\nexpected stderr: %s\nactual stderr: %s"
                         % (source.name, expected.stderr, ran.stderr))
        self.assertEqual(ran.stdout, expected.stdout, source.name)
        return built

    def test_programs_match_cpython(self):
        base = dict(os.environ, AIL_NO_CACHE="1")
        base.pop("PYTHONPATH", None)
        modes = [("default", base), ("unified", dict(base, AIL_UNIFIED_FORCE="1"))]
        for label, env in modes:
            for source in self.sources:
                with self.subTest(program=source.name, build=label):
                    built = self._build_and_run(source, env)
                    if source.name in ESCAPE_ONLY:
                        self.assertNotIn("general path", built.stderr,
                                         "%s built on the general path: %s"
                                         % (source.name, built.stderr))


if __name__ == "__main__":
    unittest.main()

"""html2: `import html` in compiled programs (bundled stdlib/html/) against CPython's html.

The twelve programs in lab/stdlib/html/ use escape, unescape, the numeric and named character
references, the entities tables and a small tag stripper the way ordinary code does.  Each is
compiled with the default command and in the unified build and run beside `python3` on the same
source; stdout and the exit status must agree.  The escape-only programs must build with no
general-path note.

`html.entities` stores CPython's four tables compactly and rebuilds them at import; it holds the
133 values above U+FFFF as name/code parallel lists and calls chr() only when such a name is
looked up.  The module therefore compiles in the 16-bit v2 runtime, and every BMP value,
`keys()` and `len()` are exact.  An astral lookup cannot be represented there and stops with the
named limit "AIL limit: chr_non_bmp" instead of returning a wrong character; that is the same
loud limit the compiler's own chr() already has on that runtime.
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
CHR_NON_BMP = "chr_non_bmp"


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

    def _build(self, source, build_env):
        work = self.dir / (source.stem + "-" + str(len(list(self.dir.iterdir()))))
        work.mkdir(parents=True, exist_ok=True)
        program = work / source.name
        shutil.copyfile(source, program)
        exe = work / (source.stem + ".out")
        built = subprocess.run([sys.executable, "-B", CLI, "compile", str(program),
                                "--syntax", "python", "-o", str(exe)],
                               cwd=str(work), capture_output=True, text=True,
                               timeout=1800, env=build_env)
        return work, program, exe, built

    def test_programs_match_cpython(self):
        # The compiler's own cache is left on: the build-time numbers in RESULTS.md are
        # measured separately with AIL_NO_CACHE=1.
        base = dict(os.environ)
        base.pop("PYTHONPATH", None)
        modes = [("default", base), ("unified", dict(base, AIL_UNIFIED_FORCE="1"))]
        built_ok = {"default": 0, "unified": 0}
        for label, env in modes:
            for source in self.sources:
                with self.subTest(program=source.name, build=label):
                    _, program, exe, built = self._build(source, env)
                    message = built.stdout + built.stderr
                    self.assertEqual(built.returncode, 0, message)
                    expected = run_cpython(program)
                    ran = subprocess.run([str(exe)], cwd=exe.parent, capture_output=True,
                                         text=True, timeout=120)
                    self.assertEqual(ran.returncode, expected.returncode,
                                     "%s exit\nexpected stderr: %s\nactual stderr: %s"
                                     % (source.name, expected.stderr, ran.stderr))
                    self.assertEqual(ran.stdout, expected.stdout, source.name)
                    built_ok[label] += 1
                    if source.name in ESCAPE_ONLY:
                        self.assertNotIn("general path", message,
                                         "%s built on the general path: %s"
                                         % (source.name, message))
        self.assertGreaterEqual(built_ok["default"], 12)
        self.assertGreaterEqual(built_ok["unified"], 12)

    def _build_and_run(self, source, build_env):
        with tempfile.TemporaryDirectory() as directory:
            program = Path(directory, "ent.py")
            program.write_text(source, encoding="utf-8")
            exe = Path(directory, "ent")
            built = subprocess.run([sys.executable, "-B", CLI, "compile", str(program),
                                    "--syntax", "python", "-o", str(exe)],
                                   cwd=directory, capture_output=True, text=True,
                                   timeout=1800, env=build_env)
            message = built.stdout + built.stderr
            self.assertEqual(built.returncode, 0, message)
            got = subprocess.run([str(exe)], capture_output=True, text=True, timeout=120)
            return got, message

    def test_html5_bmp_keys_and_len_are_exact(self):
        source = "import html.entities as e\n" \
                 "print(list(e.html5.keys())[:2], len(e.html5))\n" \
                 "print(repr(e.html5['amp;']), repr(e.html5['copy;']))\n"
        base = dict(os.environ)
        base.pop("PYTHONPATH", None)
        for label, env in (("default", base),
                           ("unified", dict(base, AIL_UNIFIED_FORCE="1"))):
            with self.subTest(build=label):
                got, _ = self._build_and_run(source, env)
                self.assertEqual(got.returncode, 0, got.stderr[-300:])
                self.assertEqual(got.stdout,
                                 "['Aacute', 'aacute'] 2231\n'&' '\u00a9'\n")

    def test_astral_lookup_stops_loudly(self):
        source = "import html.entities as e\nprint(e.html5['Afr;'])\n"
        base = dict(os.environ)
        base.pop("PYTHONPATH", None)
        for label, env in (("default", base),
                           ("unified", dict(base, AIL_UNIFIED_FORCE="1"))):
            with self.subTest(build=label):
                got, _ = self._build_and_run(source, env)
                self.assertEqual(got.returncode, 3, got.stderr[-300:])
                self.assertIn(CHR_NON_BMP, got.stderr)
                self.assertEqual(got.stdout, "")


if __name__ == "__main__":
    unittest.main()

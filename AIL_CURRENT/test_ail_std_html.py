"""html2: `import html` in compiled programs (bundled stdlib/html/) against CPython's html.

The twelve programs in lab/stdlib/html/ use escape, unescape, the numeric and named character
references, the entities tables and a small tag stripper the way ordinary code does.  Each is
compiled with the default command and in the unified build and run beside `python3` on the same
source; stdout and the exit status must agree.  The escape-only programs must build with no
general-path note.

`html5` carries CPython's 133 values above U+FFFF as string literals inside the function that
builds the table.  The typed path therefore returns them exactly (`html.entities.html5['Afr;']`
is `'𝔄'`), and `html.entities.html5.keys()` and `len()` are typed too.  A program that needs the
16-bit v2 runtime (for example because it reads a table with `.get()` outside a function, as
08_entities_tables does) is refused at compile time by name: "a non-BMP string literal in the
16-bit v2 runtime".  That is a loud, located refusal, not a wrong character and not a run-time
stop.
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
# 08 reads the tables with .get() outside a function, which the typed path cannot lower; it
# falls back to the 16-bit runtime, which refuses the astral literals by name.  The programs
# that read html.entities are refused by name in the unified build for the same reason.
MAY_REFUSE = {
    "default": {"08_entities_tables.py"},
    "unified": {"08_entities_tables.py", "09_entities_html5.py", "12_mixed.py"},
}
NON_BMP = "non-BMP string literal in the 16-bit v2 runtime"


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
                    if built.returncode != 0:
                        # the astral values are refused by name, never corrupted or stopped at run time
                        self.assertIn(source.name, MAY_REFUSE[label], message)
                        self.assertIn(NON_BMP, message)
                        self.assertFalse(exe.exists())
                        continue
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
        self.assertGreaterEqual(built_ok["default"], 11)
        self.assertGreaterEqual(built_ok["unified"], 9)

    def test_html5_astral_and_keys_are_exact(self):
        source = "import html.entities\n" \
                 "print(html.entities.html5['Afr;'], html.entities.html5['bopf;'])\n" \
                 "print(list(html.entities.html5.keys())[:2], len(html.entities.html5))\n"
        with tempfile.TemporaryDirectory() as directory:
            program = Path(directory, "ent.py")
            program.write_text(source, encoding="utf-8")
            exe = Path(directory, "ent")
            env = dict(os.environ)
            env.pop("PYTHONPATH", None)
            built = subprocess.run([sys.executable, "-B", CLI, "compile", str(program),
                                    "--syntax", "python", "-o", str(exe)],
                                   cwd=directory, capture_output=True, text=True,
                                   timeout=1800, env=env)
            message = built.stdout + built.stderr
            self.assertEqual(built.returncode, 0, message)
            want = subprocess.run([sys.executable, "-B", str(program)], capture_output=True,
                                  text=True, timeout=120)
            got = subprocess.run([str(exe)], capture_output=True, text=True, timeout=120)
            self.assertEqual(got.returncode, want.returncode, got.stderr[-300:])
            self.assertEqual(got.stdout, want.stdout)


if __name__ == "__main__":
    unittest.main()

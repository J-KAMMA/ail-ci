"""`import keyword` and `import token` in compiled programs against CPython's modules.

The twelve programs in lab/stdlib/keyword/ and lab/stdlib/token/ use the two modules the way small
linters, highlighters and code generators do: the keyword lists and predicates, and the token
constants, `tok_name`, `EXACT_TOKEN_TYPES` and the terminal predicates.  Each is compiled with the
default command and run beside `python3`
on the same source, in the default build and again with `AIL_UNIFIED_FORCE=1`; stdout and the exit
status must agree.  Every `keyword` program must be typed (no general-path fallback).  The bundled
files' `kwlist`, `softkwlist`, `tok_name` and `EXACT_TOKEN_TYPES` are loaded with `runpy` under
`python3` and must equal CPython's.  Two probes lock the forms the typed path cannot take: a saved
`keyword.iskeyword`/`issoftkeyword` reference falls back to the general path and prints `True`/
`False`, and `token.ISEOF` reads the module's mutable `ENDMARKER`.
"""
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent
CLI = str(ROOT / "ail_chatgpt.py")
KEYWORD = ROOT.parent / "lab" / "stdlib" / "keyword"
TOKEN = ROOT.parent / "lab" / "stdlib" / "token"
BUNDLED = ROOT / "stdlib"
CC = os.environ.get("PIPE_CC") or shutil.which("cc") or shutil.which("gcc")

KEYWORD_PROGRAMS = ["01_kwlist.py", "02_soft_keywords.py", "03_iskeyword.py",
                    "04_value_passing.py", "05_identifier_checker.py", "06_keyword_table.py"]
TOKEN_PROGRAMS = ["07_token_constants.py", "08_tok_name.py", "09_exact_token_types.py",
                  "10_terminal_predicates.py", "11_token_lookup.py", "12_token_table.py"]

LOADER = """
import json, runpy, sys
import keyword, token
kw = runpy.run_path(sys.argv[1])
tk = runpy.run_path(sys.argv[2])
print(json.dumps([
    kw["kwlist"], kw["softkwlist"], tk["tok_name"], tk["EXACT_TOKEN_TYPES"],
    keyword.kwlist, keyword.softkwlist, token.tok_name, token.EXACT_TOKEN_TYPES,
]))
"""

SAVED_REFERENCE = '''import keyword


def main() -> None:
    f = keyword.iskeyword
    g = keyword.issoftkeyword
    print(f("if"), f("value"))
    print(g("match"), g("if"))


main()
'''

ISEOF_MUTATES = '''import token


def main() -> None:
    token.ENDMARKER = 5
    print(token.ENDMARKER, token.ISEOF(5), token.ISEOF(0))


main()
'''


def run_cpython(path):
    env = dict(os.environ)
    env.pop("PYTHONPATH", None)
    return subprocess.run([sys.executable, "-B", str(path)], cwd=str(path.parent),
                          capture_output=True, text=True, timeout=120, env=env)


@unittest.skipUnless(CC, "installed C compiler required")
class StdlibKeywordTokenTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory(prefix="ail-keyword-test-")
        cls.dir = Path(cls.temp.name)

    @classmethod
    def tearDownClass(cls):
        cls.temp.cleanup()

    def test_lab_programs_exist(self):
        self.assertEqual([p.name for p in sorted(KEYWORD.glob("*.py"))], KEYWORD_PROGRAMS)
        self.assertEqual([p.name for p in sorted(TOKEN.glob("*.py"))], TOKEN_PROGRAMS)

    def build(self, source, mode):
        work = self.dir / source.stem / mode
        work.mkdir(parents=True, exist_ok=True)
        program = work / source.name
        shutil.copyfile(source, program)
        env = dict(os.environ, AIL_NO_CACHE="1")
        env.pop("PYTHONPATH", None)
        if mode == "force":
            env["AIL_UNIFIED_FORCE"] = "1"
        else:
            env.pop("AIL_UNIFIED_FORCE", None)
        exe = work / (source.stem + ".out")
        built = subprocess.run([sys.executable, "-B", CLI, "compile", str(program),
                                "--syntax", "python", "-o", str(exe)],
                               cwd=str(work), capture_output=True, text=True,
                               timeout=600, env=env)
        return program, exe, built

    def test_programs_match_cpython(self):
        for source in [KEYWORD / name for name in KEYWORD_PROGRAMS] + \
                      [TOKEN / name for name in TOKEN_PROGRAMS]:
            expected = run_cpython(source)
            for mode in ("default", "force"):
                with self.subTest(program=source.name, mode=mode):
                    program, exe, built = self.build(source, mode)
                    self.assertEqual(built.returncode, 0, built.stdout + built.stderr)
                    if mode == "default" and source.parent == KEYWORD:
                        self.assertNotIn("built on the general path", built.stderr,
                                         "%s must be typed: %s" % (source.name, built.stderr))
                    ran = subprocess.run([str(exe)], cwd=str(program.parent), capture_output=True,
                                         text=True, timeout=120)
                    self.assertEqual(ran.returncode, expected.returncode,
                                     "%s %s exit\nexpected stderr: %s\nactual stderr: %s"
                                     % (source.name, mode, expected.stderr, ran.stderr))
                    self.assertEqual(ran.stdout, expected.stdout, "%s %s" % (source.name, mode))

    def test_bundled_tables_match_cpython(self):
        env = dict(os.environ)
        env.pop("PYTHONPATH", None)
        loaded = subprocess.run([sys.executable, "-B", "-c", LOADER,
                                 str(BUNDLED / "keyword.py"), str(BUNDLED / "token.py")],
                                capture_output=True, text=True, timeout=120, env=env)
        self.assertEqual(loaded.returncode, 0, loaded.stderr)
        got = json.loads(loaded.stdout)
        bundled_kwlist, bundled_soft, bundled_names, bundled_exact, \
            cpython_kwlist, cpython_soft, cpython_names, cpython_exact = got
        self.assertEqual(bundled_kwlist, cpython_kwlist)
        self.assertEqual(bundled_soft, cpython_soft)
        self.assertEqual(bundled_names, cpython_names)
        self.assertEqual(bundled_exact, cpython_exact)
        self.assertEqual(len(bundled_names), len(cpython_names))
        self.assertEqual(len(bundled_exact), len(cpython_exact))

    def compile_source(self, name, text):
        path = self.dir / name
        path.write_text(text, encoding="utf-8")
        return path

    def run_probe(self, name, text, fallback_note=None):
        source = self.compile_source(name, text)
        expected = run_cpython(source)
        self.assertEqual(expected.returncode, 0, expected.stderr)
        for mode in ("default", "force"):
            with self.subTest(program=name, mode=mode):
                program, exe, built = self.build(source, mode)
                self.assertEqual(built.returncode, 0, built.stdout + built.stderr)
                if mode == "default" and fallback_note:
                    self.assertIn(fallback_note, built.stderr)
                ran = subprocess.run([str(exe)], cwd=str(program.parent), capture_output=True,
                                     text=True, timeout=120)
                self.assertEqual(ran.returncode, expected.returncode,
                                 "%s %s exit\nexpected stderr: %s\nactual stderr: %s"
                                 % (name, mode, expected.stderr, ran.stderr))
                self.assertEqual(ran.stdout, expected.stdout, "%s %s" % (name, mode))

    def test_saved_reference_falls_back(self):
        self.run_probe("saved_reference.py", SAVED_REFERENCE,
                       fallback_note="keyword.iskeyword is used as a value")

    def test_iseof_reads_endmarker(self):
        self.run_probe("iseof_mutates.py", ISEOF_MUTATES)


if __name__ == "__main__":
    unittest.main()

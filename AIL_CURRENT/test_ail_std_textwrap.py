"""textwrap lab programs, compared byte for byte with CPython 3.12.

The twelve programs in lab/stdlib/textwrap use textwrap the way ordinary code does: wrap / fill /
dedent / indent / shorten, the TextWrapper class and its common options (initial_indent,
subsequent_indent, expand_tabs, replace_whitespace, fix_sentence_endings, break_long_words,
drop_whitespace, break_on_hyphens, tabsize, max_lines, placeholder), keyword arguments and the
ValueErrors for an invalid width or an oversized placeholder.  Each one is run by CPython as the
oracle and by the compiled program on the default build and on the general path; stdout and the
exit status must match.
"""
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent
PROGRAMS = sorted((ROOT.parent / "lab" / "stdlib" / "textwrap").glob("*.py"))


def compile_source(directory, source, name, general=False):
    path = Path(directory) / (name + ".py")
    path.write_text(source.read_text(encoding="utf-8"), encoding="utf-8")
    env = dict(os.environ, AIL_NO_CACHE="1", AIL_QUIET_FALLBACK="1")
    env.pop("AIL_UNIFIED_FORCE", None)
    if general:
        env["AIL_UNIFIED_FORCE"] = "1"
    exe = Path(directory) / (name + ("_g" if general else "_d"))
    built = subprocess.run([sys.executable, "-B", str(ROOT / "ail_chatgpt.py"), "compile",
                            path.name, "--syntax", "python", "-o", exe.name],
                           cwd=directory, capture_output=True, text=True, timeout=900, env=env)
    return built, exe


class StdTextwrap(unittest.TestCase):
    def test_twelve_lab_programs_match_cpython(self):
        self.assertGreaterEqual(len(PROGRAMS), 12)
        for source in PROGRAMS:
            with self.subTest(program=source.name):
                with tempfile.TemporaryDirectory() as directory:
                    oracle = subprocess.run([sys.executable, "-X", "utf8", str(source)],
                                            capture_output=True, timeout=120)
                    self.assertEqual(oracle.returncode, 0, oracle.stderr)
                for general in (False, True):
                    with self.subTest(program=source.name, general=general), \
                            tempfile.TemporaryDirectory() as directory:
                        built, exe = compile_source(directory, source, source.stem, general=general)
                        self.assertEqual(built.returncode, 0,
                                         "%s (general=%s)\n%s%s" % (
                                             source.name, general, built.stdout[-2000:],
                                             built.stderr[-2000:]))
                        ran = subprocess.run([str(exe)], capture_output=True, timeout=120)
                        self.assertEqual(ran.returncode, oracle.returncode, ran.stderr[-1000:])
                        self.assertEqual(ran.stdout.replace(b"\r\n", b"\n"),
                                         oracle.stdout.replace(b"\r\n", b"\n"),
                                         "%s (general=%s)\n%s" % (
                                             source.name, general, ran.stderr[-1000:]))


if __name__ == "__main__":
    unittest.main()

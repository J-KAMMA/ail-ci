"""Standard-library batch 1: textwrap.shorten / textwrap.indent and string.capwords.

The corpus program lab/corpus/programs/deepseek-v4.1-flash-free/t116.py was refused only because
`textwrap.shorten` was not built. It is now compiled on both builds (AIL_IR=0 and AIL_IR=1) and its
three recorded inputs must print what CPython 3.12 prints. Every other use checked here is compared
with CPython too; uses outside the built subset stay named compile-time refusals.
"""
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent
CORPUS = ROOT.parent / "lab" / "corpus"

TEXTWRAP = r"""import textwrap
from textwrap import shorten as short, indent as add_prefix

TEXTS = [
    "Hello  world!",
    "one two three four",
    "supercalifragilistic word",
    "",
    "   ",
    "a b c d e",
    "abcdefghij",
    "  leading and trailing  ",
]

def main() -> None:
    for text in TEXTS:
        print(textwrap.wrap(text, width=15))
        print(textwrap.fill(text, width=15))
        print(textwrap.wrap(text))
        for width in (1, 4, 5, 6, 9, 11, 12, 13, 20, 70):
            try:
                print(width, repr(textwrap.shorten(text, width)))
            except ValueError as exc:
                print(width, "ValueError", exc)
        print(repr(short(text, width=11)))
    print(repr(textwrap.dedent("  a\n  b\n\tc\n")))
    for text in ("a\nb\n", "a\n\n b\r\nc", "", "  \n\t\n"):
        print(repr(textwrap.indent(text, "> ")))
        print(repr(add_prefix(text, "## ")))

main()
"""

STRING = r"""import string
from string import capwords as cw

print(string.ascii_lowercase)
print(string.ascii_uppercase)
print(string.ascii_letters)
print(string.digits)
print(string.hexdigits)
print(string.octdigits)
print(string.punctuation)
print(repr(string.whitespace))
print(repr(string.printable))

for text in ("hello  world FOO", "a,b,c", "", "one two", "  x  "):
    print(repr(string.capwords(text)))
    print(repr(string.capwords(text, ",")))
    print(repr(cw(text)))
    print(repr(cw(text, " ")))
"""

REFUSALS = {
    "textwrap class": ("import textwrap\n\nprint(textwrap.TextWrapper(width=10))\n", "textwrap"),
    "shorten options": ("import textwrap\n\nprint(textwrap.shorten('a b c', 10, placeholder='...'))\n", "textwrap"),
    "string template": ("import string\n\nprint(string.Template('x').substitute(x=1))\n", "string"),
}


def compile_python(directory, text, name, **env):
    source, exe = Path(directory, name + ".ail"), Path(directory, name)
    source.write_text(text, encoding="utf-8")
    built = subprocess.run([sys.executable, "-B", str(ROOT / "ail_chatgpt.py"), "compile", source.name,
                            "--syntax", "python", "-o", exe.name], cwd=directory, capture_output=True,
                           text=True, timeout=1800, env=dict(os.environ, **env))
    return built, source, exe


def run_program(path, data=b"", cwd=None):
    return subprocess.run([str(path)], input=data, cwd=cwd, capture_output=True, timeout=300)


class CompiledPrograms(unittest.TestCase):
    def compare(self, name, text, inputs=(b"",)):
        with tempfile.TemporaryDirectory() as directory:
            oracle = Path(directory, "oracle.py")
            oracle.write_text(text, encoding="utf-8")
            for ir in ("0", "1"):
                built, _, exe = compile_python(directory, text, name + ir, AIL_IR=ir)
                self.assertEqual(built.returncode, 0, "%s (AIL_IR=%s)\n%s%s" % (
                    name, ir, built.stdout, built.stderr))
                for index, data in enumerate(inputs):
                    want = subprocess.run([sys.executable, "-X", "utf8", str(oracle)], input=data,
                                          capture_output=True, timeout=300)
                    got = run_program(exe, data)
                    self.assertEqual(got.returncode, want.returncode,
                                     "%s input %d (AIL_IR=%s)\n%s" % (
                                         name, index, ir, got.stderr.decode("utf-8", "replace")))
                    if got.stdout != want.stdout:
                        want_lines, got_lines = want.stdout.splitlines(), got.stdout.splitlines()
                        for line, (a, b) in enumerate(zip(want_lines, got_lines), 1):
                            if a != b:
                                self.fail("%s input %d (AIL_IR=%s) line %d:\n  compiled: %r\n  CPython:  %r"
                                          % (name, index, ir, line, b, a))
                        self.fail("%s input %d (AIL_IR=%s): output lengths differ" % (name, index, ir))

    def test_textwrap(self):
        self.compare("textwrap", TEXTWRAP)

    def test_string(self):
        self.compare("string", STRING)

    def test_corpus_t116(self):
        program = CORPUS / "programs" / "deepseek-v4.1-flash-free" / "t116.py"
        if not program.exists():
            self.skipTest("corpus is not present")
        inputs = [(CORPUS / "tasks" / "t116" / ("in%d.txt" % n)).read_bytes() for n in range(3)]
        self.compare("corpus_t116", program.read_text(encoding="utf-8"), inputs)


class Refusals(unittest.TestCase):
    def test_unsupported_uses_are_named(self):
        for label, (text, wanted) in REFUSALS.items():
            with self.subTest(label), tempfile.TemporaryDirectory() as directory:
                for ir in ("0", "1"):
                    built, _, _ = compile_python(directory, text, "refused" + ir, AIL_IR=ir)
                    self.assertNotEqual(built.returncode, 0, "%s (AIL_IR=%s) compiled" % (label, ir))
                    message = built.stdout + built.stderr
                    self.assertIn(wanted, message, "%s (AIL_IR=%s): %s" % (label, ir, message))


if __name__ == "__main__":
    unittest.main()

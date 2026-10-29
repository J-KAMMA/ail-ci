"""Library batch 31: textwrap.shorten(text, width) for CPython 3.12's default options, compared with CPython
on the default build and AIL_IR=1.

The text has its whitespace collapsed first, then the default TextWrapper (expandtabs(8), the whitespace /
em-dash / hyphen chunking, break_long_words and break_on_hyphens) keeps as many chunks as fit and appends
CPython's default placeholder " [...]".  The lowering reuses the chunking of the existing wrap helper, so a
program that imports none of textwrap keeps its text.  A width below 5 raises CPython's "placeholder too
large for max width", a width <= 0 its "invalid width" ValueError, and any keyword other than text / width
stays a named compile-time refusal.
"""
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent

PROGRAM = r"""import textwrap


class Holder:
    def __init__(self, text: str, width: int) -> None:
        self.text = text
        self.width = width


def cut(text: str, width: int) -> str:
    return textwrap.shorten(text, width)


def main() -> None:
    texts = [
        "Hello  world!",
        "a b c d e",
        "abcdefghij",
        "abc defghij",
        "a-b-c-d-e",
        "with\ttab and space",
        "",
        "  padded  text  ",
        "alpha beta gamma delta",
        "a-very-long-hyphenated-word indeed",
        "one\u2014two\u2014three four",
        "caf\u00e9 na\u00efve r\u00e9sum\u00e9 text",
    ]
    widths = [5, 6, 7, 8, 9, 10, 11, 12, 14, 20, 70]
    for text in texts:
        for width in widths:
            try:
                print(repr(textwrap.shorten(text, width)))
            except ValueError as error:
                print(type(error).__name__, str(error))
    for text in texts[:5]:
        print(textwrap.shorten(text, width=11))
        print(textwrap.shorten(text=text, width=9))
    holder = Holder("attribute text with several words", 14)
    print(cut(holder.text, holder.width))
    print(cut("argument text with several words", 13))
    xs = ["list item text with several words", 12, "alpha beta gamma"]
    print(textwrap.shorten(xs[0], xs[1]))
    print(textwrap.shorten(xs[2], 8))
    values = {"text": "dict value text with several words", "width": 15}
    print(textwrap.shorten(values["text"], values["width"]))
    alias = holder.text
    print(textwrap.shorten(alias, 10))


main()
"""


def compile_python(directory, text, name, **env):
    source, exe = Path(directory, name + ".ail"), Path(directory, name)
    source.write_text(text, encoding="utf-8")
    built = subprocess.run([sys.executable, "-B", str(ROOT / "ail_chatgpt.py"), "compile", source.name,
                            "--syntax", "python", "-o", exe.name], cwd=directory, capture_output=True,
                           text=True, timeout=900, env=dict(os.environ, **env))
    return built, source, exe


class Stdlib31Tests(unittest.TestCase):
    def same_as_cpython(self, text, name, env):
        with tempfile.TemporaryDirectory() as directory:
            built, source, exe = compile_python(directory, text, name, **env)
            self.assertEqual(built.returncode, 0, "%s: %s%s" % (env, built.stdout, built.stderr))
            expected = subprocess.run([sys.executable, "-X", "utf8", str(source)], capture_output=True, timeout=120)
            ran = subprocess.run([str(exe)], capture_output=True, timeout=120)
            self.assertEqual(expected.returncode, 0, expected.stderr)
            self.assertEqual((ran.returncode, ran.stdout), (0, expected.stdout), ran.stderr[-500:])

    def test_shorten_matches_cpython_on_both_builds(self):
        for env in ({}, {"AIL_IR": "1"}):
            with self.subTest(env=env):
                self.same_as_cpython(PROGRAM, "shorten", env)

    def test_unsupported_options_are_refused_by_name(self):
        programs = [
            'import textwrap\n\n\ndef main() -> None:\n    print(textwrap.shorten("hello world", 10, placeholder="..."))\n\n\nmain()\n',
            'import textwrap\n\n\ndef main() -> None:\n    print(textwrap.indent("a\\nb", "> "))\n\n\nmain()\n',
        ]
        for text in programs:
            for env in ({}, {"AIL_IR": "1"}):
                with self.subTest(env=env, text=text.splitlines()[2]):
                    with tempfile.TemporaryDirectory() as directory:
                        built, _, exe = compile_python(directory, text, "refused", **env)
                        self.assertNotEqual(built.returncode, 0, built.stdout + built.stderr)
                        self.assertIn("with these arguments is not built", built.stderr)
                        self.assertFalse(exe.exists())


if __name__ == "__main__":
    unittest.main()

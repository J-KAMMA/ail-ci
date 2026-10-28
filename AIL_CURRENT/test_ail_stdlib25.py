"""Library batch 25: textwrap.shorten, compared with CPython 3.12.

`textwrap.shorten(text, width)` collapses runs of whitespace, returns the text when it fits,
and otherwise keeps as many whole chunks as fit before CPython's default placeholder
(" [...]"), dropping chunks from the end when the placeholder needs room.  The default build
(AIL_IR=0 and 1) and the general path are both compared byte for byte, including the
ValueError for a width that cannot hold the placeholder.  A placeholder= or any other
option is still refused by name.
"""
import os
import random
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent

SHORTEN_PROGRAM = r'''import textwrap


def show(label: str, text: str, width: int) -> None:
    try:
        print(label, repr(textwrap.shorten(text, width)))
    except ValueError as e:
        print(label, "ValueError", e)


class Box:
    text: str = "co-op  mode"

    def __init__(self, s: str) -> None:
        self.text = s


def text_for(n: int) -> str:
    if n == 0:
        return ""
    if n == 1:
        return "  one   two\tthree\nfour  "
    return "well-known goof-ball rule -- em\u2014dash end"


def main() -> None:
    for w in [5, 6, 7, 10, 11, 12, 20, 70, 0, -1]:
        show("hello", "Hello  world!", w)
    for t in ["", " ", "   ", "\t\n", "abc", "abcdef", "a b c"]:
        for w in [5, 6, 10]:
            show("edge", t, w)
    for t in ["well-known goof-ball rule", "a-b-c-d-e", "one two three four five", "a--b---c",
              "x1-2y a1-b2", "\u2014dash\u2014here"]:
        for w in [5, 6, 7, 8, 9, 10]:
            show("hyphen", t, w)
    items: list[str] = ["first item", "  a\tb\n c  "]
    show("item", items[1], 10)
    box = Box("co-op mode")
    show("attr", box.text, 8)
    vals: dict[str, str] = {"k": "x-y-z  end"}
    show("dict", vals["k"], 7)
    show("arg", text_for(1), 9)
    show("arg2", text_for(2), 14)
    width = 12
    show("expr", "one two three four", width + 1)
    print(repr(textwrap.shorten("Hello world!", width=11)))
    print(repr(textwrap.shorten("  leading\t\tand\n\nnew   spaces  ", 20)))
    print(repr(textwrap.shorten("\u00e9-\u00e0-ab \u2014 dash", 7)))
    print(repr(textwrap.shorten("word " * 20, 25)))
    print(repr(textwrap.shorten("short", 5)))
    print(repr(textwrap.shorten("short", 4)))
    print(repr(textwrap.shorten("short", 6)))


main()
'''


def generated_program(seed=25):
    rng = random.Random(seed)
    lines = [
        "import textwrap", "", "",
        "def show(text: str, width: int) -> None:",
        "    try:",
        "        print(repr(textwrap.shorten(text, width)))",
        "    except ValueError as e:",
        "        print('ValueError', e)", "", "",
    ]
    alphabet = "ab -_1.\t\n\u00e9\u2014"
    for _ in range(250):
        text = "".join(rng.choice(alphabet) for _ in range(rng.randrange(0, 45)))
        width = rng.choice([0, -1, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 12, 15, 20, 70])
        lines.append("show(%r, %d)" % (text, width))
    return "\n".join(lines) + "\n"


def compile_python(directory, text, name, **env):
    source, exe = Path(directory, name + ".ail"), Path(directory, name)
    source.write_text(text, encoding="utf-8")
    built = subprocess.run([sys.executable, "-B", str(ROOT / "ail_chatgpt.py"), "compile", source.name,
                            "--syntax", "python", "-o", exe.name], cwd=directory, capture_output=True,
                           text=True, timeout=900, env=dict(os.environ, **env))
    return built, source, exe


class Stdlib25(unittest.TestCase):
    def check(self, name, text, ir, general=False):
        with tempfile.TemporaryDirectory() as directory:
            env = dict(os.environ, AIL_IR="1" if ir else "0")
            env.pop("AIL_NO_GENERAL", None)
            env.pop("AIL_UNIFIED_FORCE", None)
            if general:
                env["AIL_UNIFIED_FORCE"] = "1"
            built, source, exe = compile_python(directory, text, "p_" + name, **env)
            self.assertEqual(built.returncode, 0, "%s (IR=%s general=%s)\n%s%s"
                             % (name, env["AIL_IR"], general, built.stdout[-2000:], built.stderr[-2000:]))
            want = subprocess.run([sys.executable, "-X", "utf8", str(source)], capture_output=True, timeout=300)
            got = subprocess.run([str(exe)], capture_output=True, timeout=300)
            self.assertEqual(got.returncode, want.returncode, got.stderr[-1000:])
            if got.stdout != want.stdout:
                a, b = got.stdout.decode("utf-8", "replace").splitlines(), want.stdout.decode("utf-8", "replace").splitlines()
                for n, (x, y) in enumerate(zip(a, b)):
                    if x != y:
                        self.fail("%s (IR=%s general=%s) line %d:\n  compiled: %r\n  CPython:  %r"
                                  % (name, env["AIL_IR"], general, n + 1, x, y))
                self.fail("%s (IR=%s general=%s): %d lines against %d"
                          % (name, env["AIL_IR"], general, len(a), len(b)))

    def test_shorten_boundaries_and_routes(self):
        for general in (False, True):
            for ir in (False, True):
                with self.subTest(general=general, ir=ir):
                    self.check("shorten_main", SHORTEN_PROGRAM, ir, general)

    def test_shorten_generated(self):
        text = generated_program()
        for general in (False, True):
            for ir in (False, True):
                with self.subTest(general=general, ir=ir):
                    self.check("shorten_fuzz", text, ir, general)

    def test_shorten_options_are_refused(self):
        text = ('import textwrap\n\n\ndef main() -> None:\n'
                '    print(textwrap.shorten("hello world", 8, placeholder="..."))\n\n\nmain()\n')
        with tempfile.TemporaryDirectory() as directory:
            built, _, exe = compile_python(directory, text, "refused")
            self.assertEqual(built.returncode, 3, built.stdout + built.stderr)
            self.assertIn("textwrap.shorten() with these arguments is not built", built.stderr)
            self.assertFalse(exe.exists())


if __name__ == "__main__":
    unittest.main()

"""html.escape on the general path (stdtop.py + prelude_html.py), compared with CPython 3.12.

* the prelude runs under CPython next to html.escape: generated strings over the special characters, with quote
  true / false / keyword, and the exceptions for arguments that are not strings (the text of CPython's own errors);
* a Python program is compiled with the default build and with AIL_UNIFIED_FORCE=1 and must print the same bytes as
  CPython on generated stdin (`html.escape` and `from html import escape`);
* html.unescape and the rest of the module are refused at compile time by name with `write instead:`.
"""
import html
import os
import random
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent
PKG = ROOT / "python" / "pkg-v12"
for each in (str(PKG), str(ROOT)):
    if each not in sys.path:
        sys.path.insert(0, each)

PROGRAM = r'''
import html
import sys
from html import escape


def page(rows):
    return "<ul>" + "".join("<li title=\"%s\">%s</li>" % (html.escape(r), escape(r, quote=False)) for r in rows) + "</ul>"


def main():
    rows = sys.stdin.read().split("\n")
    for line in rows:
        print(repr(line), html.escape(line), escape(line, quote=False), escape(line, False), html.escape(line, quote=True))
    print(page(rows))
    esc = html.escape
    print(esc("a<b"), html.escape("a<b", quote=0), html.escape("'", 1), html.escape("\"", ""))
    print(list(map(esc, ["<", "&", "'"])), [esc(r) for r in rows[:3]])
    for bad in [5, None, b"a", ["x"], 1.5]:
        try:
            print(html.escape(bad))
        except Exception as e:
            print(type(e).__name__, e)


main()
'''

LINES = "\n".join([
    "Hello, World!", "<a href=\"x\">Tom & Jerry's</a>", "café ¿qué? 中文。 (\"quoted\")", "&amp; &lt; already", "",
    "&&&&", "<<>>", "'''", "\"\"\"", "&#x27; &quot;", "tab\t and \\ backslash", "emoji-free ☃ €"]) + "\n"


def compile_python(directory, text, name, **env):
    source, exe = Path(directory, name + ".py"), Path(directory, name)
    source.write_text(text, encoding="utf-8")
    built = subprocess.run([sys.executable, "-B", str(ROOT / "ail_chatgpt.py"), "compile", source.name, "--syntax", "python",
                            "-o", exe.name], cwd=directory, capture_output=True, text=True, timeout=1800,
                           env=dict(os.environ, **env))
    return built, source, exe


def attempt(f):
    try:
        return ("ok", f())
    except Exception as e:
        return ("err", type(e).__name__, str(e))


class PreludeEscape(unittest.TestCase):
    def test_matches_html(self):
        import prelude_html as P
        rnd = random.Random(4)
        alphabet = ["&", "<", ">", "\"", "'", "a", "Z", " ", "&amp;", "&lt;", "&#x27;", "é", "中", "\n", "\\", "%", "{", "}"]
        for _ in range(3000):
            text = "".join(rnd.choice(alphabet) for _ in range(rnd.randint(0, 25)))
            self.assertEqual(P._ail_html_escape(text), html.escape(text), repr(text))
            self.assertEqual(P._ail_html_escape_q(text, False), html.escape(text, False), repr(text))
            self.assertEqual(P._ail_html_escape_q(text, True), html.escape(text, quote=True), repr(text))
            self.assertEqual(P._ail_html_escape_q(text, 0), html.escape(text, 0), repr(text))
            self.assertEqual(P._ail_html_escape_q(text, "x"), html.escape(text, "x"), repr(text))
        for bad in [5, None, b"a", bytearray(b"a"), ["x"], 1.5, ("a",), {"a": 1}, True]:
            self.assertEqual(attempt(lambda: P._ail_html_escape(bad)), attempt(lambda: html.escape(bad)), repr(bad))


class CompiledProgram(unittest.TestCase):
    def test_matches_cpython(self):
        for env in ({}, {"AIL_UNIFIED_FORCE": "1"}):
            with self.subTest(env=env), tempfile.TemporaryDirectory() as directory:
                built, source, exe = compile_python(directory, PROGRAM, "esc", **env)
                self.assertEqual(built.returncode, 0, "%r\n%s%s" % (env, built.stdout, built.stderr))
                want = subprocess.run([sys.executable, "-X", "utf8", str(source)], input=LINES.encode(), capture_output=True)
                got = subprocess.run([str(exe)], input=LINES.encode(), capture_output=True)
                self.assertEqual(got.returncode, want.returncode, got.stderr[-300:])
                a, b = got.stdout.decode().splitlines(), want.stdout.decode().splitlines()
                for n, (x, y) in enumerate(zip(a, b)):
                    self.assertEqual(x, y, "line %d %r" % (n + 1, env))
                self.assertEqual(len(a), len(b))


class Refusals(unittest.TestCase):
    CASES = {
        "unescape": ("import html\nprint(html.unescape('&lt;'))\n", "html.unescape is not supported"),
        "from import": ("from html import unescape\nprint(unescape('&lt;'))\n", "html.unescape is not supported"),
        "entities": ("import html\nprint(html.entities.name2codepoint['lt'])\n", "html.entities"),
        "module as value": ("import html\nm = html\nprint(m.escape('<'))\n", "html used as a value"),
        "escape keyword": ("import html\nprint(html.escape('<', flag=1))\n", "html.escape(flag=...) is not supported"),
        "escape args": ("import html\nprint(html.escape('<', True, 3))\n", "html.escape with 3 arguments is not supported"),
        "star": ("from html import *\nprint(escape('<'))\n", "from html import *"),
    }

    def test_refusals_name_the_use(self):
        for name, (text, wanted) in self.CASES.items():
            with self.subTest(name), tempfile.TemporaryDirectory() as directory:
                built, _, exe = compile_python(directory, text, "refused")
                shown = built.stdout + built.stderr
                self.assertNotEqual(built.returncode, 0, "compiled but should be refused: " + name)
                self.assertIn(wanted, shown)
                self.assertFalse(exe.exists())
        with tempfile.TemporaryDirectory() as directory:
            built, _, _ = compile_python(directory, self.CASES["unescape"][0], "refused")
            self.assertIn("write instead:", built.stdout + built.stderr)


class UnchangedPrograms(unittest.TestCase):
    def test_programs_without_html_keep_their_text(self):
        import stdlib5
        for text in ["# html only in a comment\nprint(1)\n", "s = 'import html'\nprint(s.upper())\n"]:
            notes = []
            self.assertEqual(stdlib5.rewrite_text(text, notes), text)
            self.assertEqual(notes, [])


if __name__ == "__main__":
    unittest.main()

"""The `string` module: constants, capwords() and Template, compared with CPython 3.12.

The programs in lab/stdlib/string/ are the coverage set.  Eleven of the twelve build on the
default and forced-general paths and must print exactly what CPython prints with the same exit
code; formatter_table.py stays a named compile-time refusal (string.Formatter is not built).
capwords() accepts `s=` / `sep=` keywords, and string.Template lowers to a small prelude object
whose substitute / safe_substitute / is_valid / get_identifiers match CPython's Template.
"""
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent
LAB = ROOT.parent / "lab" / "stdlib" / "string"

BUILT = [
    "word_stats",
    "slugify",
    "password_rules",
    "name_formatter",
    "csv_punctuation_report",
    "identifier_check",
    "hex_parser",
    "text_sanitizer",
    "initials",
    "template_email",
    "template_config",
]
REFUSED = "formatter_table"

METHODS = r"""import string

LITERAL = "$x ${y}"


def render(t, mapping):
    return t.substitute(mapping)


class Holder:
    def __init__(self, t):
        self.t = t


def show_bad(tpl):
    label = type(tpl).__name__
    bad = string.Template(tpl)
    try:
        print(label, "substitute", bad.substitute({}))
    except Exception as exc:
        print(label, "substitute", type(exc).__name__, exc)
    try:
        print(label, "safe_substitute", bad.safe_substitute({}))
    except Exception as exc:
        print(label, "safe_substitute", type(exc).__name__, exc)
    try:
        print(label, "is_valid", bad.is_valid())
    except Exception as exc:
        print(label, "is_valid", type(exc).__name__, exc)
    try:
        print(label, "get_identifiers", bad.get_identifiers())
    except Exception as exc:
        print(label, "get_identifiers", type(exc).__name__, exc)


def main():
    t = string.Template(LITERAL)
    print(getattr(t, "substitute")({"x": 1, "y": 2}))
    print(getattr(t, "safe_substitute")({"x": 3}))
    print(getattr(t, "is_valid")())
    print(getattr(t, "get_identifiers")())
    print(getattr(t, "template"))
    print(getattr(t, "delimiter"))
    print(render(t, {"x": 4, "y": 5}))
    values = [t, string.Template("$a/$b")]
    print(values[1].substitute({"a": "A", "b": "B"}))
    table = {"one": t}
    print(table["one"].substitute({"x": 6, "y": 7}))
    holder = Holder(string.Template("${p}-${q}"))
    print(holder.t.substitute({"p": "P", "q": "Q"}))
    for tpl in (b"$x", bytearray(b"$x"), 5, None, ["$x"], 3.5):
        show_bad(tpl)


main()
"""

VALUE_READ = r"""import string

t = string.Template("$x ${y}")
f = t.substitute
print(f({"x": 1, "y": 2}))
"""

GETATTR_VALUE_READ = r"""import string

t = string.Template("$x")
g = getattr(t, "get_identifiers")
print(g())
"""


def compile_python(directory, source, name, **env):
    exe = Path(directory, name)
    built = subprocess.run([sys.executable, "-B", str(ROOT / "ail_chatgpt.py"), "compile", source.name,
                            "--syntax", "python", "-o", exe.name], cwd=directory, capture_output=True,
                           text=True, timeout=1800, env=dict(os.environ, **env))
    return built, exe


class StringPrograms(unittest.TestCase):
    def compare(self, name, **env):
        text = (LAB / (name + ".py")).read_text(encoding="utf-8")
        self.compare_text(name, text, **env)

    def compare_text(self, name, text, **env):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory, name + ".py")
            source.write_text(text, encoding="utf-8")
            built, exe = compile_python(directory, source, name, **env)
            self.assertEqual(built.returncode, 0, "%s %s\n%s%s" % (name, env, built.stdout, built.stderr))
            want = subprocess.run([sys.executable, "-X", "utf8", str(source)], cwd=directory,
                                  capture_output=True, timeout=300)
            got = subprocess.run([str(exe)], cwd=directory, capture_output=True, timeout=300)
            self.assertEqual(got.returncode, want.returncode,
                             "%s %s\n%s" % (name, env, got.stderr.decode("utf-8", "replace")))
            if got.stdout != want.stdout:
                want_lines, got_lines = want.stdout.splitlines(), got.stdout.splitlines()
                for line, (a, b) in enumerate(zip(want_lines, got_lines), 1):
                    if a != b:
                        self.fail("%s %s line %d:\n  compiled: %r\n  CPython:  %r"
                                  % (name, env, line, b, a))
                self.fail("%s %s: output lengths differ" % (name, env))

    def test_built_programs_match_cpython(self):
        for name in BUILT:
            for env in ({}, {"AIL_UNIFIED_FORCE": "1"}):
                with self.subTest(program=name, env=env):
                    self.compare(name, **env)

    def test_template_methods_and_bad_templates(self):
        for env in ({}, {"AIL_UNIFIED_FORCE": "1"}):
            with self.subTest(env=env):
                self.compare_text("template_methods", METHODS, **env)

    def test_template_method_value_is_refused_by_name(self):
        for text in (VALUE_READ, GETATTR_VALUE_READ):
            for env in ({}, {"AIL_UNIFIED_FORCE": "1"}):
                with self.subTest(env=env), tempfile.TemporaryDirectory() as directory:
                    source = Path(directory, "value.py")
                    source.write_text(text, encoding="utf-8")
                    built, exe = compile_python(directory, source, "value", **env)
                    self.assertNotEqual(built.returncode, 0, built.stdout + built.stderr)
                    self.assertIn("not in the subset", built.stdout + built.stderr)
                    self.assertIn("as a value", built.stdout + built.stderr)
                    self.assertFalse(exe.exists())

    def test_formatter_is_refused_by_name(self):
        text = (LAB / (REFUSED + ".py")).read_text(encoding="utf-8")
        for env in ({}, {"AIL_UNIFIED_FORCE": "1"}):
            with self.subTest(env=env), tempfile.TemporaryDirectory() as directory:
                source = Path(directory, REFUSED + ".py")
                source.write_text(text, encoding="utf-8")
                built, exe = compile_python(directory, source, REFUSED, **env)
                self.assertNotEqual(built.returncode, 0, built.stdout + built.stderr)
                self.assertIn("string.Formatter", built.stdout + built.stderr)
                self.assertFalse(exe.exists())


if __name__ == "__main__":
    unittest.main()

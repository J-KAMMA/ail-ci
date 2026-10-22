"""`re.sub` / `re.subn` with a function as the replacement: it is called with each Match.

CPython accepts any callable there.  A replacement value this compiler can tell is a function -- a lambda, a
def, a name that holds one (`f = up`, `g = f`, `h = i = up`, `f = lambda m: ...`), a dict or list of functions
indexed at run time (`TABLE["k"]`, `FS[0]`), the target of a loop over such a list, a call of a def whose every
return is a function, or a parameter (annotated `Callable[...]`, or whose every call site passes a function) --
is lowered to the form that walks the matches and calls it: `_ail_re_subN(s, fn, count)`, whose `fn` receives
the Match object, so `m.group(i)`, `m.group("name")`, `m.start()`, `m.end()` work, a `None` result is an empty
piece, and `subn` returns `(text, count)`.  `count` is honoured (0 and a negative count replace nothing, as in
CPython).  A value that is not a function keeps the string lowering (`_ail_re_sublit`, a replacement template).

A bound method cannot be a value in this language at all (`f = obj.m` does not build either), so
`re.sub(P, obj.m, s)` is refused by name at build time, with the lambda spelling that works, instead of
failing at run time.

Every program below is ordinary Python: CPython runs it as the oracle and both builds (the default build, which
falls back to the general path, and the general path itself with AIL_UNIFIED_FORCE=1) print the same bytes.
"""
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
import ail_syntax  # noqa: E402


def compile_python(directory, text, name, env_extra=None):
    source, exe = Path(directory, name + ".ail"), Path(directory, name)
    source.write_text(text, encoding="utf-8")
    env = dict(os.environ, AIL_NO_CACHE="1", AIL_QUIET_FALLBACK="1")
    env.update(env_extra or {})
    built = subprocess.run([sys.executable, "-B", str(ROOT / "ail_chatgpt.py"), "compile", source.name,
                            "--syntax", "python", "-o", exe.name], cwd=directory, capture_output=True,
                           text=True, timeout=900, env=env)
    return built, source, exe


CALLABLE_VALUES = r'''import re
from typing import Callable

P = r"([a-z])-(\d)"
Q = re.compile(r"(?P<w>[a-z])-(?P<n>\d)")


def up(m):
    return m.group(1).upper()


def low(m):
    return m.group(1).lower()


def pair(m):
    return m.group(2) + m.group(1)


def named(m):
    return m.group("n") + ":" + m.group("w") + "@" + str(m.start(0)) + "-" + str(m.end(0))


def nothing(m):
    return None


def make(suffix):
    return lambda m: m.group(1) + suffix


def run(f: Callable[[object], str], s):
    return re.sub(P, f, s)


def runn(f: Callable[[object], str], s, n):
    return re.subn(P, f, s, n)


def loose(fn, s):
    return re.sub(P, fn, s)


def main():
    s = "a-1 b-2 c-3"
    print(re.sub(P, up, s))
    print(re.sub(P, up, s, 1), re.sub(P, up, s, count=2))
    print(re.subn(P, up, s), re.subn(P, up, s, 2), re.subn(P, up, s, count=1))
    # a function held in a name, an alias of an alias, a two-target assignment, a lambda
    f = up
    g = f
    print(re.sub(P, f, s), re.sub(P, g, s, 2), re.subn(P, g, s, count=1))
    h = i = low
    print(re.sub(P, i, "A-1 B-2"), re.subn(P, h, "A-1 B-2"))
    k = "!"
    lam = lambda m: m.group(1) + k
    print(re.sub(P, lam, s), re.subn(P, lam, s, 1))
    # a function from a dict, a dict of lambdas, a list, a dict with an int key
    table = {"u": up, "l": low}
    print(re.sub(P, table["u"], s), re.sub(P, table["l"], "A-1 B-2"))
    lams = {"bang": lambda m: m.group(2) + "!"}
    print(re.subn(P, lams["bang"], s, 1))
    fs = [up, low]
    print(re.sub(P, fs[0], s), re.sub(P, fs[1], "A-1 B-2"))
    numbered = {0: up, 1: low}
    print(re.sub(P, numbered[0], s))
    pick = 1
    print(re.sub(P, fs[pick], "A-1 B-2"))
    # a loop over a tuple, a list and a module-level tuple
    for each in (up, low):
        print(re.sub(P, each, s), re.subn(P, each, s, 1))
    for each in fs:
        print(re.sub(P, each, "Z-9"))
    # a call of a def that returns a function
    print(re.sub(P, make("<"), s), re.subn(P, make(">"), s, 2))
    # a parameter: annotated Callable, and one whose call sites all pass a function
    print(run(up, s), run(lambda m: m.group(2), s), runn(up, s, 1), runn(up, s, -1))
    print(loose(low, "A-1 B-2"), loose(up, s))
    # groups, named groups, start and end
    print(Q.sub(pair, s), Q.subn(pair, s), Q.sub(pair, s, 2))
    print(Q.sub(named, "x-1 y-2"))
    print(re.sub(Q, named, "x-1 y-2", 1))
    # a None result is an empty piece
    print(repr(re.sub(P, nothing, s)), re.subn(P, nothing, s, 2))
    # count: 0, negative, larger than the number of matches, a variable
    n = 2
    print(re.sub(P, f, s, 0), re.sub(P, f, s, -1), re.sub(P, f, s, 99), re.sub(P, f, s, n))
    print(re.subn(P, f, s, 0), re.subn(P, f, s, -2), re.subn(P, f, s, n))
    # empty subject, empty matches, no match at all
    print(re.sub(P, f, ""), re.subn(P, f, ""), re.sub(P, f, "zz"))
    dash = lambda m: "-"
    print(re.sub(r"x*", dash, ""), re.sub(r"x*", dash, "abc"), re.subn(r"x*", dash, "abc", 2))
    print(re.sub(r"", dash, "ab"), re.subn(r"", dash, "ab"))
    # bytes
    B = re.compile(rb"([a-z])(\d)")
    data = b"a1 b2 c3"
    bswap = pair
    print(B.sub(bswap, data), B.subn(bswap, data), B.sub(bswap, data, 1))
    print(re.sub(rb"\d", lambda m: b"#", data), re.subn(rb"\d", lambda m: None, data, 2))
    print(re.sub(rb"\d", b"X", data, -1), re.subn(rb"\d", b"X", data, -1))
    # the replacement runs once per match, in order
    seen = []
    def note(m):
        seen.append(m.group(0))
        return "[" + m.group(0) + "]"
    print(re.sub(P, note, s), len(seen), " ".join(seen))
    print(re.sub(P, note, s, 1), len(seen))
main()
'''

STRING_VALUES = r'''import re

Q = re.compile(r"\d+")


class Holder:
    def __init__(self, text):
        self.text = text


def replace_with(repl: str, s: str) -> str:
    return re.sub(r"([a-z])-\d", repl, s)


def main():
    s = "a-1 b-2 c-3"
    print(re.sub(r"([a-z])-\d", "X", s), re.sub(r"([a-z])-\d", "<&>", s), re.sub(r"([a-z])-\d", "", s))
    repl = "Y"
    print(re.sub(r"([a-z])-\d", repl, s))
    pre = "<"
    print(re.sub(r"([a-z])-\d", pre + "!", s), re.sub(r"([a-z])-\d", f"{pre}?", s))
    print(replace_with("V", s), replace_with("<" + "&" + ">", s))
    print(Q.sub("#", "a1b22"))
    # a negative count replaces nothing, as in CPython
    print(repr(re.sub(r"([a-z])-\d", "X", s, -1)))
    print(repr(re.sub(r"\d+", "#", "a1b22", -3)))
    print(repr(re.sub(r"([a-z])-\d", "X", s, 0)), re.sub(r"([a-z])-\d", "X", s, 2))
main()
'''

STRING_VALUES_GENERAL = r'''import re

P = r"([a-z])-\d"


class Holder:
    def __init__(self, text):
        self.text = text


def main():
    s = "a-1 b-2"
    table = {"k": "Z", "n": 1}
    print(re.sub(P, table["k"], s))
    h = Holder("W")
    print(re.sub(P, h.text, s))
    nested = {"a": {"b": "Q"}}
    print(re.sub(P, nested["a"]["b"], s))
    # and a function from a dict with the same shape
    up = lambda m: m.group(1).upper()
    fns = {"u": up, "s": "T"}
    print(re.sub(P, fns["u"], s))
main()
'''

BOUND_METHOD = '''import re


class R:
    def __init__(self):
        self.pre = "<"

    def fmt(self, m):
        return self.pre + m.group(1)


def main():
    r = R()
    s = "a-1"
    print(re.sub(r"([a-z])-\\d", r.fmt, s))
    print(re.sub(r"([a-z])-\\d", r.fmt, s, 1))
    print(re.subn(r"([a-z])-\\d", r.fmt, s))
main()
'''

BOUND_METHOD_SELF = '''import re


class R:
    def __init__(self):
        self.pre = "<"

    def fmt(self, m):
        return self.pre + m.group(1)

    def go(self, s):
        return re.sub(r"([a-z])-\\d", self.fmt, s)


def main():
    print(R().go("a-1"))
main()
'''

AMBIGUOUS = '''import re


def up(m):
    return m.group(1).upper()


def main():
    up = "X"
    s = "a-1"
    print(re.sub(r"([a-z])-\\d", up, s))
main()
'''

REFUSALS = [
    ("bound method of a variable", BOUND_METHOD, "a bound method (fmt) as the replacement is not built"),
    ("bound method of self", BOUND_METHOD_SELF, "a bound method (fmt) as the replacement is not built"),
    ("a def and a variable of one name", AMBIGUOUS, "both a function and a variable"),
]


class ReSub2Tests(unittest.TestCase):
    def same_as_cpython(self, text, name, env_extra=None, minimum_lines=1):
        with tempfile.TemporaryDirectory() as directory:
            built, source, exe = compile_python(directory, text, name, env_extra)
            self.assertEqual(built.returncode, 0, built.stdout + built.stderr)
            ran = subprocess.run([str(exe)], capture_output=True, timeout=900)
            expected = subprocess.run([sys.executable, str(source)], capture_output=True, timeout=900)
            self.assertEqual(expected.returncode, 0, expected.stderr)
            self.assertGreaterEqual(expected.stdout.count(b"\n"), minimum_lines)
            if ran.stdout != expected.stdout:
                got, want = ran.stdout.split(b"\n"), expected.stdout.split(b"\n")
                for number, (a, b) in enumerate(zip(got, want)):
                    if a != b:
                        self.fail("line %d differs:\n  compiled: %r\n  CPython:  %r" % (number + 1, a, b))
                self.fail("lengths differ: %d vs %d lines" % (len(got), len(want)))
            self.assertEqual(ran.returncode, 0, ran.stderr)
            return expected.stdout

    def refused(self, text, wanted, env_extra=None):
        with tempfile.TemporaryDirectory() as directory:
            built, _, exe = compile_python(directory, text, "prog", env_extra)
            self.assertEqual(built.returncode, 3, built.stdout + built.stderr)
            self.assertIn(wanted, built.stderr)
            self.assertFalse(exe.exists())

    def test_callable_replacement_values_match_cpython(self):
        out = self.same_as_cpython(CALLABLE_VALUES, "resub2_values", minimum_lines=30)
        self.assertIn(b"A B C", out)

    def test_callable_replacement_values_match_cpython_general_path(self):
        self.same_as_cpython(CALLABLE_VALUES, "resub2_values_general",
                             {"AIL_UNIFIED_FORCE": "1"}, minimum_lines=30)

    def test_string_replacements_still_match_cpython_typed_path(self):
        self.same_as_cpython(STRING_VALUES, "resub2_strings", {"AIL_NO_GENERAL": "1"}, minimum_lines=8)

    def test_string_replacements_still_match_cpython_general_path(self):
        self.same_as_cpython(STRING_VALUES, "resub2_strings_general", {"AIL_UNIFIED_FORCE": "1"},
                             minimum_lines=8)

    def test_a_str_from_a_dict_or_an_attribute_stays_a_replacement(self):
        """A general-path program: a str value from a dict, a nested dict or an attribute is a template."""
        self.same_as_cpython(STRING_VALUES_GENERAL, "resub2_strings_values", {"AIL_UNIFIED_FORCE": "1"},
                             minimum_lines=4)

    def test_refusals_are_named(self):
        for label, text, wanted in REFUSALS:
            with self.subTest(label):
                self.refused(text, wanted)
                self.refused(text, wanted, {"AIL_UNIFIED_FORCE": "1"})

    def test_a_function_value_gets_the_callable_helper(self):
        """The lowering, without building: a name, a table lookup and a loop target go to `_ail_re_subN`."""
        text = ("import re\n\n\ndef up(m):\n    return m.group(1)\n\n\n"
                "def main():\n    s = 'a-1'\n    f = up\n    t = {'u': up}\n"
                "    print(re.sub(r'([a-z])-\\d', f, s))\n"
                "    print(re.subn(r'([a-z])-\\d', t['u'], s, 1))\n"
                "    for each in (up,):\n        print(re.sub(r'([a-z])-\\d', each, s))\n"
                "    print(re.sub(r'([a-z])-\\d', lambda m: m.group(1), s))\n"
                "    print(re.sub(r'([a-z])-\\d', 'X', s))\n\n\nmain()\n")
        out = ail_syntax.python_surface(text)
        self.assertIn("_ail_re_sub0(s, f, 0)", out)
        self.assertIn("_ail_re_sub1(s, t['u'], 1)", out)
        self.assertIn("_ail_re_sub0(s, each, 0)", out)
        self.assertIn("_ail_re_sub0(s, lambda m: m.group(1), 0)", out)
        self.assertIn("_ail_re_sublit(_ail_re_p0, s, 'X', 0)", out)

    def test_a_string_value_keeps_the_string_helper(self):
        """A str variable, a dict of strings and an attribute are not functions: no Match object is built."""
        text = ("import re\n\n\nclass C:\n    def __init__(self, t):\n        self.t = t\n\n\n"
                "def main():\n    s = 'a-1'\n    r = 'X'\n    d = {'k': 'Y'}\n    c = C('Z')\n"
                "    print(re.sub(r'([a-z])-\\d', r, s))\n"
                "    print(re.sub(r'([a-z])-\\d', d['k'], s))\n"
                "    print(re.sub(r'([a-z])-\\d', c.t, s))\n\n\nmain()\n")
        out = ail_syntax.python_surface(text)
        self.assertEqual(out.count("_ail_re_sublit(_ail_re_p0, s"), 3)
        self.assertNotIn("_ail_re_sub0", out)


if __name__ == "__main__":
    unittest.main()

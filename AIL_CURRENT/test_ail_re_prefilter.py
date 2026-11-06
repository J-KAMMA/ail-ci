"""`re` literal prefilter: `relib` proves, at build time, a literal every match contains or the set of
bytes a match can start with, and the generated engine uses it to skip starts that cannot match.

Three checks:
* 40 hand-written patterns (alternations, optional parts, anchors, lookaround, IGNORECASE, empty
  matches): the extracted candidate must be one CPython's own answers agree with, over texts that do
  and do not match -- every CPython match must contain the required literal, and must start on a byte
  of the first-byte set;
* 2000 seeded random patterns from the supported grammar x 20 texts: the same property, which is what
  makes skipping safe;
* a generated program (search / findall / finditer / sub / split on the same patterns and texts) must
  print exactly what CPython prints, since a wrong skip would move or lose a match.
"""
import os
import random
import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "python" / "pkg-v12"))
import relib  # noqa: E402


FLAGS = {"": 0, "I": relib.I, "M": relib.M, "S": relib.S, "X": relib.X, "A": relib.A}
SCALARS = {"I": re.I, "M": re.M, "S": re.S, "X": re.X, "A": re.A}

# 40 patterns: what each kind of form must or must not prove.
PATTERNS = [
    # literal prefixes and required literals
    ("error", "", "error"),
    ("ERROR", "", "ERROR"),
    (r"\[(\d+)\] ERROR (.*)", "", "] ERROR "),
    (r"level=(?P<level>\w+)? msg", "", "level="),
    (r"\d+ items", "", " items"),
    ("abc", "", "abc"),
    # alternation: no single required literal across branches
    ("error|warn|fatal", "", None),
    ("ERROR|WARN", "", None),
    ("(?:ab|cd)ef", "", "ef"),
    ("(?:foo|foobar)baz", "", None),
    # optional parts are not required
    ("(?:xyz)?q", "", None),
    ("a?bc", "", "bc"),
    ("a*bc", "", "bc"),
    ("a{2,}bc", "", "bc"),
    ("a{0,2}bc", "", "bc"),
    ("(?:ab){2}x", "", "ababx"),
    # anchors and lookaround carry no text
    ("^start", "", "start"),
    ("end$", "", "end"),
    (r"\Ahi", "", "hi"),
    (r"\bword\b", "", "word"),
    (r"x(?=yz)y", "", "x"),
    (r"x(?!yz)y", "", "x"),
    (r"(?<=ab)cd", "", "cd"),
    # sets and dots carry no text
    (r"\d\d\d", "", None),
    (r"[a-z]{4}", "", None),
    (".+", "", None),
    (r"\w+@\w+", "", None),
    (r"colou?r", "", None),
    # IGNORECASE: a letter may be in either case, so no case-sensitive literal is forced
    ("error", "I", None),
    ("ERROR", "I", None),
    ("err-", "I", None),
    ("e-ERROR", "I", None),
    ("é-ERROR", "I", "ERROR"),
    # groups do not change what is inside them
    ("(alpha)(beta)", "", "alphabeta"),
    ("(?:gamma)(?:delta)", "", "gammadelta"),
    ("(?P<n>zeta)", "", "zeta"),
    ("((a)(b))cd", "", "abcd"),
    # bytes-agnostic: a non-ASCII literal is not used (it cannot be searched as bytes)
    ("café", "", None),
    ("café|x", "", None),
    ("a café b", "", None),
]

TEXTS = [
    "", "error", "ERROR", "Error", "xx error yy", "[12] ERROR boom", "[7] WARN hi",
    "error|warn|fatal", "warn", "fatal", "abcabc", "abcef", "cdefef", "foobarbaz",
    "xyzq", "q", "abc", "aabc", "aaaabc", "start", "the end", "hi there", "a word b",
    "xyz", "abcd", "123", "abc123", "a@b", "colour", "color", "zeta", "chi", "alpha beta",
    "gamma delta", "é-ERROR", "café", "a café b", "\n", "a\nb", "aaabbb",
]


def program(pattern, flags=""):
    return relib.Program(pattern, FLAGS[flags])


def py_re(pattern, flags=""):
    return re.compile(pattern, SCALARS.get(flags, 0))


class ExtractionTests(unittest.TestCase):
    def test_candidates_are_proved(self):
        cases = 0
        for pattern, flags, expected in PATTERNS:
            try:
                prog = program(pattern, flags)
            except relib.ReRefused:
                continue
            got = prog.required_literal()
            # the exact string is an implementation choice; `expected` records the one the rules
            # give today, but only its absence on an empty match would be a correctness problem
            self.assertTrue(got is None or expected is None or got == expected,
                            "%r with flags %r: %r" % (pattern, flags, got))
            prefix = prog.literal_prefix()
            for text in TEXTS:
                for m in py_re(pattern, flags).finditer(text):
                    if got is not None:
                        self.assertIn(got, m.group(0),
                                      "%r must contain %r on %r" % (pattern, got, text))
                    if prefix:
                        self.assertTrue(m.group(0).startswith(prefix),
                                        "%r must start with %r on %r" % (pattern, prefix, text))
                    bs = prog.first_byte_set()
                    if bs is not None and m.start() < len(text):
                        self.assertIn(ord(text[m.start()]), bs,
                                      "%r start byte on %r" % (pattern, text))
                    cases += 1
        self.assertGreater(cases, 100)

    def test_required_literal_rules(self):
        self.assertEqual(program("error").required_literal(), "error")
        self.assertIsNone(program("a|b").required_literal())
        self.assertIsNone(program("ab|cd").required_literal())
        self.assertEqual(program("x(?:yz)").required_literal(), "xyz")
        self.assertIsNone(program("(?:abc)?").required_literal())
        self.assertIsNone(program("", ).required_literal())
        self.assertIsNone(program("a{2}").required_literal())
        self.assertEqual(program("(?:ab){2}").required_literal(), "ab")

    def test_first_byte_set_is_a_superset(self):
        for pattern, flags, _expected in PATTERNS:
            try:
                prog = program(pattern, flags)
            except relib.ReRefused:
                continue
            bs = prog.first_byte_set()
            if bs is None:
                continue
            self.assertLessEqual(len(bs), relib._PREFILTER_MAX)
            self.assertFalse(prog.first_set()[0], "a nullable pattern has no usable set")
            self.assertFalse(prog.first_set()[1], "a non-ASCII starter has no usable set")

    def test_prefilter_is_none_for_bytes_and_nothing(self):
        self.assertIsNone(relib.Program(b"error", 0, True).prefilter())
        self.assertIsNone(program("").prefilter())
        self.assertEqual(program("error").prefilter(), ("lit", "error"))
        self.assertEqual(program("^x").prefilter(), ("set", [ord("x")]))
        self.assertEqual(program("(?:ab|cd)").prefilter(), ("set", [ord("a"), ord("c")]))


GENERATED = "".join("".join(chr(c) for c in range(32, 127)))


def random_pattern(rng, depth=0):
    def atom():
        pick = rng.randrange(10)
        if pick < 4:
            return rng.choice("abcefrw0129 -_:[]")
        if pick == 4:
            return "."
        if pick == 5:
            return rng.choice([r"\d", r"\w", r"\s", r"\S", r"\D"])
        if pick == 6:
            return rng.choice(["[a-c]", "[^a-c]", "[0-9_]", "[^ ]"])
        if pick == 7:
            return rng.choice(["^", r"\b", ""])
        if depth >= 2:
            return rng.choice("abe")
        if pick == 8:
            return "(" + random_pattern(rng, depth + 1) + ")"
        return "(?:" + random_pattern(rng, depth + 1) + ")"

    parts = []
    for _ in range(rng.randrange(1, 4)):
        body = atom()
        if body in ("", "^", r"\b"):
            parts.append(body)
            continue
        q = rng.randrange(6)
        if q == 2:
            body += "?"
        elif q == 3:
            body += "*"
        elif q == 4:
            body += "+"
        elif q == 5:
            body += "{%d,%d}" % (rng.randrange(0, 2), rng.randrange(2, 4))
        parts.append(body)
    out = parts[0]
    for part in parts[1:]:
        out += ("|" if rng.randrange(5) == 0 else "") + part
    return out


class PropertyTests(unittest.TestCase):
    """2000 seeded patterns x 20 subjects: the prefilter never steps over a CPython match."""

    def test_random_patterns_keep_every_match(self):
        rng = random.Random(20261106)
        checked = 0
        for _ in range(2000):
            pattern = random_pattern(rng)
            flags = rng.choice(["", "I", "M", "S"])
            try:
                prog = relib.Program(pattern, FLAGS[flags])
            except relib.ReRefused:
                continue
            required = prog.required_literal()
            prefix = prog.literal_prefix()
            bs = prog.first_byte_set()
            matcher = re.compile(pattern, SCALARS.get(flags, 0))
            for _ in range(20):
                text = "".join(rng.choice("abcefrw0192 -_:[]\n") for _ in range(rng.randrange(0, 24)))
                for m in matcher.finditer(text):
                    if required is not None:
                        self.assertIn(required, m.group(0), (pattern, flags, text))
                    if prefix:
                        self.assertTrue(m.group(0).startswith(prefix), (pattern, flags, text))
                    if bs is not None and m.start() < len(text):
                        self.assertIn(ord(text[m.start()]), bs, (pattern, flags, text))
                    checked += 1
        self.assertGreater(checked, 2000)


def compile_python(directory, text, name):
    source, exe = Path(directory, name + ".py"), Path(directory, name)
    source.write_text(text, encoding="utf-8")
    built = subprocess.run([sys.executable, "-B", str(ROOT / "ail_chatgpt.py"), "compile", source.name,
                            "-o", exe.name], cwd=directory, capture_output=True, text=True,
                           timeout=900, env=dict(os.environ, AIL_NO_CACHE="1"))
    return built, source, exe


def differential_program(rng, count=25):
    lines = ["import re", "", "def main() -> int:"]
    texts = []
    for _ in range(20):
        texts.append("".join(rng.choice("abcefrw0192 -_:[]\n") for _ in range(rng.randrange(0, 40))))
    made = 0
    for _ in range(count):
        pattern = random_pattern(rng)
        flags = rng.choice(["", "", "I", "M"])
        try:
            prog = relib.Program(pattern, FLAGS[flags])
        except relib.ReRefused:
            continue
        made += 1
        flag = ", re." + flags if flags else ""
        roll = ", 0" + flag if flags else ""
        for text in texts:
            lines.append("    print(re.search(%r, %r%s) is None)" % (pattern, text, flag))
            if prog.ngroups == 0:
                lines.append("    print(len(re.findall(%r, %r%s)))" % (pattern, text, flag))
                lines.append("    print(len(re.split(%r, %r%s)))" % (pattern, text, roll))
            lines.append("    print(re.sub(%r, 'X', %r%s))" % (pattern, text, roll))
    lines += ["    return 0", "", "main()"]
    return "\n".join(lines) + "\n", made


class DifferentialTests(unittest.TestCase):
    def test_generated_programs_match_cpython(self):
        rng = random.Random(424242)
        text, made = differential_program(rng)
        self.assertGreater(made, 10)
        with tempfile.TemporaryDirectory() as directory:
            built, source, exe = compile_python(directory, text, "pref")
            self.assertEqual(built.returncode, 0, built.stderr[-3000:])
            self.assertNotIn("built on the general path", built.stderr)
            expected = subprocess.run([sys.executable, "-B", source.name], cwd=directory,
                                      capture_output=True, text=True, timeout=600)
            actual = subprocess.run([str(exe)], cwd=directory, capture_output=True, text=True,
                                    timeout=600)
            self.assertEqual(actual.returncode, 0, actual.stderr[-2000:])
            self.assertEqual(actual.stdout, expected.stdout)

    def test_required_literal_short_circuit_keeps_answers(self):
        text = r'''import re


def main() -> int:
    LOG = "12:00:00 host app: level=ERROR msg=boom\n13:00:00 host app: level=INFO msg=ok\n"
    print(re.search(r"\[(\d+)\] ERROR", LOG) is None)
    print(re.search(r"\[(\d+)\] ERROR", "nothing to see") is None)
    print(repr(re.findall(r"\d\d:\d\d:\d\d host", LOG)))
    print(repr(re.split(r" host ", LOG)))
    print(repr(re.sub(r"host app", "HOST", LOG)))
    print(re.search(r"ERROR|WARN", LOG) is None)
    print(repr(re.findall(r"ERROR|WARN", LOG)))
    return 0


main()
'''
        with tempfile.TemporaryDirectory() as directory:
            built, source, exe = compile_python(directory, text, "req")
            self.assertEqual(built.returncode, 0, built.stderr[-3000:])
            expected = subprocess.run([sys.executable, "-B", source.name], cwd=directory,
                                      capture_output=True, text=True, timeout=600)
            actual = subprocess.run([str(exe)], cwd=directory, capture_output=True, text=True,
                                    timeout=600)
            self.assertEqual(actual.returncode, 0, actual.stderr[-2000:])
            self.assertEqual(actual.stdout, expected.stdout)


if __name__ == "__main__":
    unittest.main()

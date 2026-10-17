"""`import re`: literal patterns compiled at build time, every result compared with CPython's `re`.

Every program below is ordinary Python.  CPython runs it as the oracle and the compiled program (the
Python syntax, AIL_NO_GENERAL=1 so the typed path must take it) prints the same bytes, or the spelling
is refused by name -- there is no third outcome where the answers differ.

Built: re.match / fullmatch / search / findall (zero or one group) / finditer / split (no groups) / sub
(string replacement with \\1, \\g<1>, \\g<name>, \\n ...; a non-literal replacement without a backslash)
/ escape, `NAME = re.compile(literal)` with the same methods, match objects with group / start / end
(`m.group()`, `m.group("name")`, `a, b = m.span()`, `a, b = m.groups()`), truthiness and `is None`; str and
bytes patterns; flags I M S X A.  The pattern has to be a string literal (or a name bound once to one).
Refused by name: lookahead / lookbehind, backreferences, atomic and possessive forms, conditionals, scoped
flags, a repeated group that can match the empty string, IGNORECASE with a non-ASCII pattern character,
findall with several groups, split with groups, a function as the replacement, m.groups() as a value.

The engine is a leftmost-first Pike VM (CPython's backtracking priority, linear time), so groups and
spans are CPython's.  Generated tests: random patterns from the supported grammar x random subjects,
compared on fullmatch / match / search spans of every group, findall, finditer, sub and split.
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


def compile_python(directory, text, name):
    source, exe = Path(directory, name + ".ail"), Path(directory, name)
    source.write_text(text, encoding="utf-8")
    built = subprocess.run([sys.executable, "-B", str(ROOT / "ail_chatgpt.py"), "compile", source.name,
                            "--syntax", "python", "-o", exe.name], cwd=directory, capture_output=True,
                           text=True, timeout=900, env=dict(os.environ, AIL_NO_GENERAL="1"))
    return built, source, exe


BASIC = r'''import re

PHONE = re.compile(r"(\d{3})-(\d{4})")
DATE = re.compile(r"(?P<year>[0-9]{4})-(?P<month>[0-9]{2})-(?P<day>[0-9]{2})")
WORD = r"[a-z]+"
TOKEN = re.compile(r"\s*(?:(\d+)|([a-z_][a-z0-9_]*)|(<>|==|!=|[-+*/()]))")


def classify(s: str) -> int:
    n = 0
    if re.fullmatch(r"[0-9]+", s):
        n += 1
    if not re.fullmatch(r"[a-z]{1,10}", s):
        n += 10
    if re.match(WORD, s) is None:
        n += 100
    if re.search(r"\d", s) is not None and re.search(r"[a-z]", s):
        n += 1000
    while re.fullmatch(r"x*", s):
        n += 10000
        break
    return n


def main() -> int:
    for s in ["abc", "ab1", "", "123", "x", "xxx", "Hello World", "tab\there", "e\u0301", "caf\u00e9 \u0663\u0664"]:
        print(len(s), classify(s))
        m = re.match(WORD, s)
        if m is not None:
            print("word", m.group(), m.group(0), m.start(), m.end())
        print(len(re.findall(r"\w", s)), len(re.findall(r"\d", s)), len(re.findall(r"\s", s)),
              len(re.findall(r"\W", s)), len(re.findall(r"\S+", s)))
    m = PHONE.search("call 555-1234 now")
    if m:
        a, b = m.span()
        print(m.group(1), m.group(2), a, b, m.start(1), m.end(2))
        x, y = m.groups()
        print(x + y)
    d = DATE.fullmatch("2026-10-17")
    if d is not None:
        print(d.group("year"), d.group("month"), d.group("day"), d.start("day"), d.end("month"))
        print(int(d.group(1)) * 10000 + int(d.group(2)) * 100 + int(d.group(3)))
    print(DATE.fullmatch("2026-1-17") is None, bool(DATE.search("x 2026-10-17 y")), not PHONE.match("1"))
    print(re.sub(r"(\d+)", r"<\1>", "a1b22c333"))
    print(re.sub(r"(?P<w>[a-z]+)", r"[\g<w>|\g<1>|\g<0>]", "ab 12 cd"))
    print(re.sub(r"\s+", " ", "a   b \t c\n\nd"))
    print(re.sub(r"x*", "-", "abxd"))
    print(re.sub(r"a", "b", "aaaa", 2), re.sub(r"a", "b", "aaaa", count=1), re.sub("", "-", "ab"))
    print(re.sub(r"(a)|(b)", r"[\1\2]", "abc"))
    print(re.sub(r"a", r"\\n\t\n", "xay"))
    rep = "<" + "k" + ">"
    print(re.sub(r"\d", rep, "a1b2"))
    print(re.sub(r"(\w+)@(\w+)", r"\2 at \1", "me@home you@work"))
    for part in re.split(r",\s*", "a, b,c,,d"):
        print("[" + part + "]")
    for part in re.split(r"\s*", "ab  c"):
        print("<" + part + ">")
    for part in re.split(r"x", "axbxc", 1):
        print("{" + part + "}")
    for part in re.split(r"(?:,|;)", ""):
        print("empty", len(part))
    for x in re.findall(r"\d+", "a1b22c333"):
        print(x)
    for x in re.findall(r"(\d)(?:x|$)", "1x2x34"):
        print("g", x)
    for x in re.findall(r"(a)|b", "abab"):
        print("opt", len(x))
    for mm in re.finditer(r"[a-z]", "a1b"):
        print(mm.group(0), mm.start(), mm.end())
    for mm in re.finditer(r"\b", "ab cd"):
        print("b", mm.start())
    for mm in re.finditer(r"", "abc"):
        print("empty", mm.start(), mm.end())
    pos = 0
    text = "12 + x1 <> (7)"
    while True:
        t = TOKEN.match(text[pos:])
        if t is None:
            break
        if t.start(1) >= 0:
            print("num", t.group(1))
        elif t.start(2) >= 0:
            print("name", t.group(2))
        else:
            print("op", t.group(3))
        pos += t.end(0)
    print(re.escape("a.b*c[d] e_f-g"))
    print(re.fullmatch(r"(?i)hello", "HeLLo") is not None, re.fullmatch(r"hello", "HELLO", re.I) is not None)
    print(len(re.findall(r"^\w+$", "ab\ncd\n", re.M)), len(re.findall(r"^\w+$", "ab\ncd\n")))
    print(len(re.findall(r"a.b", "a\nb a b")), len(re.findall(r"a.b", "a\nb a b", re.S)))
    print(re.fullmatch(r"""
        (\d+)   # digits
        \.      # dot
        (\d+)
    """, "12.5", re.X) is not None)
    print(re.fullmatch(r"\w+", "caf\u00e9") is not None, re.fullmatch(r"\w+", "caf\u00e9", re.A) is not None)
    print(re.fullmatch(r"[^\W\d_]+", "abc\u00e9") is not None, re.fullmatch(r"\d+", "\u0663\u0664") is not None)
    print(re.fullmatch(r"\s+", "\u3000\u00a0 ") is not None, re.fullmatch(r"\s", "\x1c") is not None)
    print(re.search(r"\Bb", "ab") is not None, re.search(r"\bb", "ab") is not None, re.search(r"b\Z", "ab\n") is not None,
          re.search(r"b$", "ab\n") is not None, re.search(r"\Ab", "ab") is not None)
    print(len(re.findall(r"a(?=b)", "ab ac ab")), len(re.findall(r"a(?!b)", "ab ac ab")),
          len(re.findall(r"(?<=a)b", "ab cb ab")), len(re.findall(r"(?<!a)b", "ab cb ab")),
          re.search(r"~(?![01])", "~0 ~2").start(), re.search(r"(?<![0-9])0[0-9]", "10 07").start())
    for x in re.findall(r"\w+(?=,)", "ab, cd, ef"):
        print("look", x)
    for k, v in re.findall(r"(\w+)=(\d+)", "a=1 bb=22 c=x d=4"):
        print(k, int(v) + 1)
    for k3, v3, w3 in re.findall(r"(\w)(\d)?(x)", "a1x bx"):
        print(k3, len(v3), w3)
    q = re.fullmatch(r"(\d+)(?:\.(\d+))?(e\d+)?", "12.5")
    if q:
        print(q.group(1), q.group(2) or "none", q.group(3) or "none", q.group(3) is None, q.group(2) is not None)
    print(re.fullmatch(r"a{2,3}?", "aa") is not None, re.fullmatch(r"a{,2}b", "aab") is not None,
          re.fullmatch(r"a{x}", "a{x}") is not None, re.fullmatch(r"[a-c-]+", "a-c") is not None)
    return 0


main()
'''

BYTES_PROGRAM = r'''import re
import sys

TOK = re.compile(rb"[A-Za-z0-9\x80-\xff]+(?:['-][A-Za-z0-9\x80-\xff]+)*")
R_DATE = re.compile(rb'([0-9]{4})-([0-9]{2})-([0-9]{2})')
NUM = re.compile(rb"-?(?:0|[1-9][0-9]*)")


def main() -> int:
    data = sys.stdin.buffer.read()
    n = 0
    for m in TOK.finditer(data):
        n += len(m.group(0)) * 3 + m.start(0)
    print(n)
    d = R_DATE.search(data)
    if d:
        print(int(d.group(1)) + int(d.group(2)) + int(d.group(3)), d.start(), d.end())
    print(len(re.findall(rb"[0-9]+", data)), len(re.findall(rb"(\d)\d", data)))
    print(len(re.sub(rb"[0-9]+", b"#", data)), len(re.sub(rb"([a-z])([0-9])", rb"\2\1", data)))
    print(len(re.split(rb"\s+", data)), len(re.split(rb"[ \t\n\r\f\v]+", data, 2)))
    if re.fullmatch(rb"[0-9]+", b"123") and not NUM.fullmatch(b"01"):
        print("ok")
    print(re.fullmatch(rb"\w+", b"caf\xc3\xa9") is None, re.fullmatch(rb"[^a]+", b"\xc3\xa9") is not None)
    print(re.search(rb"(?i)ABC", data) is not None, re.search(rb"\bworld\b", data, re.I) is not None)
    print(len(re.findall(rb"\xc3[\xa0-\xbf]", data)))
    for a, b in re.findall(rb"([a-z])(\d)", data):
        print(a.hex(), b.hex())
    print(len(re.findall(rb"x(?=1)|(?<=-)w", data)))
    return 0


main()
'''

BYTES_INPUT = b"hello wor-ld 2024-05-17 abc9 x1 caf\xc3\xa9 \n42 it's  Hello, WORLD -7 07\n"

BOOL_CONTEXTS = r'''import re

P = re.compile(r"a+b?")


def f(s: str) -> int:
    n = 0
    if P.fullmatch(s):
        n += 1
    if not P.search(s):
        n += 10
    if P.match(s) is None:
        n += 100
    if P.match(s) is not None and re.search(r"b", s):
        n += 1000
    k = 5 if re.fullmatch(r"\d+", s) else 7
    n += k
    xs = [c for c in "ab1" if re.fullmatch(r"[a-z]", c)]
    n += len(xs) * 10000
    return n


def g(s: str) -> int:
    m = re.search(r"(\d+)", s)
    if not m:
        return -1
    return int(m.group(1)) + m.start(1)


def main() -> int:
    for s in ["", "a", "ab", "aab", "ba", "12", "x9"]:
        print(f(s), g(s))
    return 0


main()
'''

CODEPOINTS = r'''import re


def main() -> int:
    for name in range(3):
        prev = False
        start = 0
        for cp in range(0x110000):
            if 0xD800 <= cp < 0xE000:
                continue
            s = chr(cp)
            if name == 0:
                hit = re.fullmatch(r"\d", s) is not None
            elif name == 1:
                hit = re.fullmatch(r"\w", s) is not None
            else:
                hit = re.fullmatch(r"\s", s) is not None
            if hit != prev:
                print(name, cp, hit)
                prev = hit
    return 0


main()
'''

REFUSALS = [
    ("group in lookahead", 're.search(r"a(?=(b))", s)', "capturing group inside a lookahead"),
    ("variable lookbehind", 're.search(r"(?<=a+)b", s)', "fixed-width"),
    ("quantified lookahead", 're.search(r"(?=a)*b", s)', "quantifier on an anchor"),
    ("backreference", 're.search(r"(a)\\1", s)', "backreference"),
    ("named backreference", 're.search(r"(?P<x>a)(?P=x)", s)', "backreference"),
    ("atomic", 're.search(r"(?>a+)b", s)', "atomic"),
    ("possessive", 're.search(r"a*+b", s)', "possessive"),
    ("conditional", 're.search(r"(a)?(?(1)b|c)", s)', "conditional"),
    ("scoped flags", 're.search(r"(?i:a)b", s)', "inline flags"),
    ("empty repeat", 're.search(r"(a*)*b", s)', "can match the empty string"),
    ("empty alt repeat", 're.search(r"(?:a|b?)+", s)', "can match the empty string"),
    ("ignorecase non-ASCII", 're.search("\u00e9", s, re.I)', "IGNORECASE with a non-ASCII"),
    ("dynamic pattern", 're.search(s, s)', "string literal"),
    ("compile in a call", 're.search(re.compile("a"), s)', "string literal"),
    ("findall groups", 're.findall(r"(a)(b)", s)', "tuples"),
    ("split groups", 're.split(r"(,)", s)', "group"),
    ("sub function", 're.sub(r"a", lambda m: "b", s)', "replacement"),
    ("bad template", 're.sub(r"a", r"\\q", s)', "bad escape"),
    ("bad group in template", 're.sub(r"a", r"\\3", s)', "invalid group reference"),
    ("subn", 're.subn(r"a", "b", s)', "re.subn is not built"),
    ("groups value", 're.search(r"(a)", s).groups()', "m.groups()"),
    ("groupdict", 're.search(r"(a)", s).groupdict()', "m.groupdict()"),
    ("unbalanced", 're.search(r"(a", s)', "missing )"),
    ("nothing to repeat", 're.search(r"*a", s)', "nothing to repeat"),
    ("bad escape", 're.search(r"\\q", s)', "bad escape"),
    ("pos argument", 're.compile("a").search(s, 1)', "not built"),
    ("compile value", 'print(re.compile("a"))', "re.compile"),
]


# -- generated patterns and subjects ---------------------------------------------------------------
ALPHA = list("abc") + ["A", "B", "1", "2", " ", "_", "-", "\n", "\u00e9", "\u0663", "!"]
BALPHA = list("abc") + ["A", "B", "1", "2", " ", "_", "-", "\n", "\xe9", "\xff", "!"]


def gen_look(rng, behind):
    parts = [rng.choice(["a", "b", "1", r"\d", r"\w", r"\s", "[ab]", "[^a]", ".", "-", r"\W"])
             for _ in range(rng.randint(1, 2))]
    if not behind and rng.random() < 0.4:
        parts[-1] += rng.choice(["*", "+", "?", "{1,2}"])
    return "".join(parts)


def gen_atom(rng, depth, bytes_mode):
    if rng.random() < 0.08:
        kind = rng.choice(["(?=", "(?!", "(?<=", "(?<!"])
        return kind + gen_look(rng, "<" in kind) + ")"
    r = rng.random()
    if r < 0.30:
        choices = ["a", "b", "c", "A", "1", "-", "_", " ", "\\.", "\\n", "x"] + (["\\xe9"] if bytes_mode else ["\u00e9"])
        return rng.choice(choices)
    if r < 0.38:
        return "."
    if r < 0.50:
        return rng.choice([r"\d", r"\w", r"\s", r"\D", r"\W", r"\S"])
    if r < 0.62:
        items = []
        for _ in range(rng.randint(1, 3)):
            items.append(rng.choice(["a", "b", "a-c", "0-9", r"\d", r"\w", r"\s", "_", "A-B", r"\-", " ", r"\n",
                                     "a-b0-1", r"\xe9-\xff" if bytes_mode else "\u00e9", r"\S"]))
        neg = "^" if rng.random() < 0.3 else ""
        body = "".join(items)
        if rng.random() < 0.1:
            body = "]" + body
        if rng.random() < 0.1:
            body += "-"
        return "[" + neg + body + "]"
    if r < 0.70:
        return rng.choice(["^", "$", r"\b", r"\B", r"\A", r"\Z"])
    if depth < 3:
        inner = gen_alt(rng, depth + 1, bytes_mode)
        k = rng.random()
        if k < 0.5:
            return "(" + inner + ")"
        if k < 0.85:
            return "(?:" + inner + ")"
        return "(?P<n%d>%s)" % (rng.randint(0, 99999), inner)
    return rng.choice(["a", "b"])


def gen_piece(rng, depth, bytes_mode):
    a = gen_atom(rng, depth, bytes_mode)
    if a in ("^", "$", r"\b", r"\B", r"\A", r"\Z") or a.startswith(("(?=", "(?!", "(?<=", "(?<!")):
        return a
    if rng.random() < 0.55:
        return a
    q = rng.choice(["*", "+", "?", "{2}", "{1,2}", "{0,3}", "{2,}", "{,2}", "{3}", "{1,}", "{0}", "{,}", "{ 1}"])
    return a + q + ("?" if rng.random() < 0.25 else "")


def gen_seq(rng, depth, bytes_mode):
    return "".join(gen_piece(rng, depth, bytes_mode) for _ in range(rng.randint(1, 4)))


def gen_alt(rng, depth, bytes_mode):
    return "|".join(gen_seq(rng, depth, bytes_mode) for _ in range(rng.choice([1, 1, 1, 2, 3])))


def gen_subject(rng, alpha):
    return "".join(rng.choice(alpha) for _ in range(rng.randint(0, 9)))


def usable(pattern, flags, bytes_mode):
    """CPython compiles it and this compiler builds it: (compiled, group count) or None."""
    try:
        if bytes_mode:
            compiled = re.compile(pattern.encode("latin-1"), flags)
        else:
            compiled = re.compile(pattern, flags)
    except re.error:
        return None
    try:
        relib.Library().pattern(pattern.encode("latin-1") if bytes_mode else pattern, flags, bytes_mode)
    except relib.ReRefused:
        return None
    return compiled


def lit(value):
    return repr(value)


def case_function(index, pattern, flags, compiled, bytes_mode, subjects):
    """The source of one function that exercises every API on one pattern over SUBS."""
    groups = compiled.groups
    text = lit(pattern.encode("latin-1") if bytes_mode else pattern)
    flagtext = "" if not flags else ", flags=" + " | ".join(
        name for name, bit in (("re.I", re.I), ("re.M", re.M), ("re.S", re.S), ("re.A", re.A), ("re.X", re.X))
        if flags & bit)
    if bytes_mode:       # a bytes literal list is not an iterable here: split one bytes literal
        loop = "%s.split(b'|')" % lit(b"|".join(subjects))
    else:
        loop = lit(subjects)
    lines = ["def case_%d() -> int:" % index, "    n = 0", "    for s in %s:" % loop]

    hexed = ".hex()" if bytes_mode else ""

    def show(tag, call):
        out = ["        m = %s" % call, "        if m is None:", "            print(%d, %r, '-')" % (index, tag),
               "        else:"]
        spans = ", ".join("m.start(%d), m.end(%d)" % (g, g) for g in range(groups + 1))
        out.append("            print(%d, %r, %s)" % (index, tag, spans))
        for g in range(groups + 1):
            out.append("            if m.start(%d) >= 0:" % g)
            out.append("                print(%d, %r, m.group(%d)%s)" % (index, tag + str(g), g, hexed))
        return out

    for tag, fn in (("F", "fullmatch"), ("M", "match"), ("S", "search")):
        lines += show(tag, "re.%s(%s, s%s)" % (fn, text, flagtext))
    if groups <= 1:
        lines += ["        for x in re.findall(%s, s%s):" % (text, flagtext), "            print(%d, 'A', x%s)" % (index, hexed)]
    lines += ["        for mm in re.finditer(%s, s%s):" % (text, flagtext),
              "            print(%d, 'I', mm.start(0), mm.end(0))" % index]
    empty = "b''" if bytes_mode else "''"
    arrow = b"<>" if bytes_mode else "<>"
    lines += ["        r = re.sub(%s, %s, s%s)" % (text, lit(arrow), flagtext), "        print(%d, 'U', r%s)" % (index, hexed)]
    if groups:
        template = rb"<\g<1>|\g<0>>" if bytes_mode else r"<\g<1>|\g<0>>"
        lines += ["        r = re.sub(%s, %s, s%s)" % (text, lit(template), flagtext),
                  "        print(%d, 'T', r%s)" % (index, hexed)]
    lines += ["        r = re.sub(%s, %s, s, 1%s)" % (text, lit(b"-" if bytes_mode else "-"), flagtext),
              "        print(%d, 'C', r%s)" % (index, hexed)]
    if groups == 0:
        for limit in (0, 2):
            args = (", %d" % limit if limit else "") + flagtext
            lines += ["        for x in re.split(%s, s%s):" % (text, args), "            print(%d, 'P', x%s)" % (index, hexed)]
    lines += ["        n += 1", "    return n", ""]
    return "\n".join(lines)


def fuzz_program(seed, count, subjects, bytes_mode=False):
    rng = random.Random(seed)
    cases = []
    while len(cases) < count:
        pattern = gen_alt(rng, 0, bytes_mode)
        flags = rng.choice([0, 0, 0, re.I, re.M, re.S, re.A, re.I | re.M, re.M | re.S, re.X])
        if bytes_mode:
            flags &= ~re.A
        compiled = usable(pattern, flags, bytes_mode)
        if compiled is not None:
            cases.append((pattern, flags, compiled))
    alpha = BALPHA if bytes_mode else ALPHA
    subs = [gen_subject(rng, alpha) for _ in range(subjects)]
    if bytes_mode:
        subs = [s.encode("latin-1") for s in subs]
    ascii_subs = [s for s in subs if s.isascii()]
    parts = ["import re", ""]
    for index, (pattern, flags, compiled) in enumerate(cases):
        # IGNORECASE on a str subject needs ASCII text: those cases use only the ASCII subjects
        chosen = ascii_subs if flags & re.I and not bytes_mode else subs
        parts.append(case_function(index, pattern, flags, compiled, bytes_mode, chosen))
    parts += ["def main() -> int:", "    total = 0"]
    parts += ["    total += case_%d()" % i for i in range(len(cases))]
    parts += ["    print(total)", "    return 0", "", "", "main()", ""]
    return "\n".join(parts), len(cases), len(subs)


class ReTests(unittest.TestCase):
    def same_as_cpython(self, text, name, stdin=b"", minimum_lines=1):
        with tempfile.TemporaryDirectory() as directory:
            built, source, exe = compile_python(directory, text, name)
            self.assertEqual(built.returncode, 0, built.stdout + built.stderr)
            ran = subprocess.run([str(exe)], input=stdin, capture_output=True, timeout=600)
            expected = subprocess.run([sys.executable, str(source)], input=stdin, capture_output=True, timeout=600)
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

    def refused(self, text, wanted):
        with tempfile.TemporaryDirectory() as directory:
            built, _, exe = compile_python(directory, text, "prog")
            self.assertEqual(built.returncode, 3, built.stdout + built.stderr)
            self.assertIn(wanted, built.stderr)
            self.assertFalse(exe.exists())

    def test_str_api_matches_cpython(self):
        out = self.same_as_cpython(BASIC, "re_basic", minimum_lines=100)
        self.assertIn(b"[1|1|1]" if False else b"<1>", out)

    def test_bytes_api_matches_cpython(self):
        self.same_as_cpython(BYTES_PROGRAM, "re_bytes", stdin=BYTES_INPUT, minimum_lines=8)

    def test_match_results_in_conditions(self):
        self.same_as_cpython(BOOL_CONTEXTS, "re_bool", minimum_lines=7)

    def test_unicode_classes_match_cpython_for_every_code_point(self):
        out = self.same_as_cpython(CODEPOINTS, "re_codepoints", minimum_lines=100)
        self.assertIn(b"\n1 48 True\n", b"\n" + out)

    def test_refusals_are_named(self):
        for label, expression, wanted in REFUSALS:
            with self.subTest(label):
                text = "import re\n\n\ndef main() -> int:\n    s = input()\n    x = %s\n    return 0\n\n\nmain()\n" \
                       % expression
                if expression.startswith("print"):
                    text = text.replace("x = print", "print")
                self.refused(text, wanted)

    def test_no_re_import_adds_nothing(self):
        """A program without `import re` gets none of the generated text."""
        text = "def main() -> int:\n    print(len(\"abc\"))\n    return 0\n\n\nmain()\n"
        with tempfile.TemporaryDirectory() as directory:
            built, source, exe = compile_python(directory, text, "plain")
            self.assertEqual(built.returncode, 0, built.stdout + built.stderr)
            sys.path.insert(0, str(ROOT))
            import ail_syntax
            self.assertNotIn("_ail_re_", ail_syntax.python_surface(text))

    def test_generated_str_patterns_match_cpython(self):
        total = 0
        for seed in (101, 102, 103):
            text, patterns, subjects = fuzz_program(seed, 45, 36)
            total += patterns * subjects
            out = self.same_as_cpython(text, "re_fuzz_%d" % seed, minimum_lines=patterns)
            self.assertTrue(out.rstrip().split(b"\n")[-1].isdigit())
        self.assertGreaterEqual(total * 8, 10000)      # >= 10k (pattern, subject, operation) results

    def test_generated_bytes_patterns_match_cpython(self):
        text, patterns, subjects = fuzz_program(201, 40, 30, bytes_mode=True)
        self.same_as_cpython(text, "re_fuzz_bytes", minimum_lines=patterns)


if __name__ == "__main__":
    unittest.main()

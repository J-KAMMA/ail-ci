"""Compiled patterns used past `NAME.method(s)`: pos / endpos, a bound-method alias, and the refusals kept loud.

lab/compare's tree_fold and tally_lang (plain CPython sources) were refused with "the compiled pattern NODE is used
as a value": `match = NODE.match` then `match(s, pos)`, and `TOK.match(s, i)` with a start position.  Now:

V1  PATTERN.match / search / fullmatch (s, pos[, endpos]) as CPython: `^` and `\\A` do not match at pos > 0, `\\b` and
    lookbehind see the text before pos, endpos cuts the text ($ matches there), pos / endpos are clamped, non-ASCII
    text and bytes patterns; the typed path takes the program (AIL_NO_GENERAL=1) and both builds agree with CPython
    (V2 has m.span() on the default and forced builds: printing a span tuple built at module level is not typed)
V2  `match = NODE.match` bound once in a function body and only called after it; with tree_fold's other shapes on
    the general path (`it.__class__ is str`, `pop = st.pop`)
V3  still refused by name: a pattern passed to a function, a pattern bound twice, a pattern a function reads
    before its binding runs (CPython: NameError), an alias called before it is bound
V4  loud stops: an int beyond int64 parsed from matched text, match() with endpos before pos
V5  long subjects (pos more than 1024 from the end): the match runs on a window around pos that grows until the
    scan ends inside it, so a greedy run, a far search hit, \\b / \\Z at the window edge, empty matches, groups that
    did not take part, bytes and non-ASCII text all give CPython's answers in linear total time
"""
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent
CLI = str(ROOT / "ail_chatgpt.py")

POS = r'''import re

TOK = re.compile(r"[ \t]*(?:(\d+)|([a-z_][a-z0-9_]*)|(==|<|>|\+|-|\(|\)))")
WORD = re.compile(r'\b\w+')
START = re.compile(r'^b')
AFTER = re.compile(r'(?<=a)b')
END = re.compile(r'c$')
EMPTY = re.compile(r'')
NODE = re.compile(r'([a-z]{1,16}):(0|[1-9][0-9]{0,6})')
BYTES = re.compile(rb'(\d+)x')
OPT = re.compile(r'(\d)(\d)?')


def tokenize(s):
    out = []
    i = 0
    n = len(s)
    while i < n:
        m = TOK.match(s, i)
        if m is None:
            out.append("err@" + str(i))
            break
        if m.end() == i:
            break
        i = m.end()
        if m.group(1) is not None:
            out.append("n" + str(int(m.group(1)) * 3))
        elif m.group(2) is not None:
            out.append("v" + m.group(2))
        else:
            out.append("o" + m.group(3))
    return out


for line in ["x + 12 == (y-3)", "a $ b", "", "   ", "q<1>2", "922337203685477580"]:
    print(tokenize(line))
subj = 'xx abc dé'
print(WORD.match(subj, 1) is None, WORD.match(subj, 3).group(0), WORD.search(subj, 4).group(0), WORD.search(subj, 7).group(0))
print(START.match('ab', 1) is None, AFTER.match('ab', 1).start(), AFTER.search('xbab', 0).start())
print(END.search('abcd', 0, 3).end(), END.search('abcd', 0) is None, END.match('abc', 2, 3).group(0))
print(NODE.fullmatch('zz ab:12', 3).group(1), NODE.fullmatch('zz ab:12x', 3) is None, NODE.fullmatch('zz ab:12x', 3, 8).group(2))
print(NODE.search('..ab:5', pos=1).group(0), NODE.match('ab:5x', endpos=4).group(0), NODE.match('ab:5', endpos=3) is None)
print(NODE.match('ab:5', -4).end(), NODE.match('ab:5', 10) is None, EMPTY.match('abc', 10).start())
print(EMPTY.search('abc', 2, 1) is None, NODE.fullmatch('abc', 2, 1) is None, EMPTY.match('abc', 3, 99).end())
txt = 'ñab:7'
print(NODE.match(txt, 1).group(0), NODE.search(txt, 0).start(), NODE.search(txt, 2).start(), NODE.search(txt, 4) is None)
if NODE.match('ab:1', 0):
    print('ok')
if not NODE.match('ab:1', 1):
    print('no')
print(BYTES.match(b'a12x', 1).group(1).decode(), BYTES.search(b'aa3x', 1).end(), BYTES.match(b'a12x', 1, 3) is None)
found = OPT.match('a1b', 1)
print(found.group(1), found.group(2) is None, found.end(1))
'''

ALIAS = r'''import re
import sys

NODE = re.compile(r'([a-z]{1,16}):(0|[1-9][0-9]{0,6})')


def walk(s):
    match = NODE.match
    pos = 0
    names = []
    total = 0
    while pos < len(s):
        m = match(s, pos)
        if m is None:
            names.append('?%d' % pos)
            pos += 1
            continue
        names.append(m.group(1))
        total += int(m.group(2))
        pos = m.end()
        if pos < len(s) and s[pos] == ' ':
            pos += 1
    return names, total


def show(kids):
    res = []
    st = [0]
    pop = st.pop
    while st:
        it = pop()
        if it.__class__ is str:
            res.append(it)
            continue
        res.append(str(it))
        k = kids[it]
        if k:
            res.append('[')
            st.append(']')
            for c in reversed(k):
                st.append(c)
    return ''.join(res)


print(walk('ab:1 cd:22 ef:333'))
print(walk('ab:1 X cd:0'))
print(walk('n:9999999 ' * 3))
print(show([[1, 2], (), [3], ()]))
d = {'a': 1}
dp = d.pop
s = {7}
sp = s.pop
print(dp('a'), d, sp(), s)
print(NODE.match('xab:1', 1).span(), NODE.search('..ab:5', 1, 6).span())
sys.exit(3)
'''

LONG = r'''import re

TOK = re.compile(r"[ \t]*(?:(\d+)|([a-z_][a-z0-9_]*)|(==|<|>|\+|-|\(|\)))")
RUN = re.compile(r'(a*b|a)')
WB = re.compile(r'\b(\w+)\b')
EOL = re.compile(r'x+\Z')
OPTG = re.compile(r'(\d)(z)?')
EMPTYOK = re.compile(r'q*')
BYT = re.compile(rb'([a-z]+):(\d+)')


def lcg(seed):
    x = seed
    while True:
        x = (x * 1103515245 + 12345) % 2147483648
        yield x


g = lcg(7)
parts = []
for i in range(3000):
    k = next(g) % 6
    if k == 0:
        parts.append(str(next(g) % 100000))
    elif k == 1:
        parts.append('v' + str(next(g) % 50))
    elif k == 2:
        parts.append(' == ')
    elif k == 3:
        parts.append('(')
    elif k == 4:
        parts.append(')')
    else:
        parts.append('  -')
text = ' '.join(parts)
i = 0
n = len(text)
toks = 0
acc = 0
while i < n:
    m = TOK.match(text, i)
    if m is None or m.end() == i:
        break
    i = m.end()
    toks += 1
    if m.group(1) is not None:
        acc = (acc * 31 + int(m.group(1))) % 1000000007
    elif m.group(2) is not None:
        acc = (acc + len(m.group(2))) % 1000000007
print(toks, acc, i)
long_a = 'c' * 10 + 'a' * 5000 + 'b' + 'a' * 3000
for p in (5, 10, 11, 300, 4999, 5009, 5010, 5011, 6000, 8005):
    m = RUN.match(long_a, p)
    s = RUN.search(long_a, p)
    print(p, None if m is None else (m.start(), m.end(), m.group(1)[:3]), None if s is None else (s.start(), s.end()))
words = ('alpha beta  gamma_1 ' * 400) + '!!'
pos = 0
cnt = 0
last = ''
while True:
    m = WB.search(words, pos)
    if m is None:
        break
    cnt += 1
    last = m.group(1)
    pos = m.end()
print(cnt, last, pos)
far = ' ' * 5000 + 'zz9' + ' ' * 3000
print(WB.search(far, 1).span(), WB.search(far, 5001) is None, WB.search(far, 5003) is None, WB.match(far, 5000).group(0))
xs = 'y' * 3000 + 'x' * 3000
print(EOL.search(xs, 10).span(), EOL.match(xs, 2999), EOL.match(xs, 3000).end(), EOL.search(xs + 'y', 10))
digits = ('1z2' * 2000)
pos = 1
out = []
while pos < len(digits):
    m = OPTG.search(digits, pos)
    if m is None:
        break
    out.append(m.group(2) is None)
    pos = m.end()
print(len(out), sum(out))
print(EMPTYOK.search('a' * 3000, 5).span(), EMPTYOK.match('a' * 3000 + 'qq', 2999).span(), EMPTYOK.match('b' * 3000, 1500).span())
bt = b'pad ' * 600 + b'abc:12 de:3'
print(BYT.search(bt, 10).group(1).decode(), BYT.match(bt, 2400).group(2).decode(), BYT.search(bt, 2403).span())
uni = 'x' * 2000 + 'é' + ' 42 zz' + 'q' * 2000
print(TOK.match(uni, 2001).group(1), WB.search(uni, 3).span(), WB.search(uni, 2002).group(0))
# zero-width patterns whose scan reaches every window end: the window grows to the whole text and stops
ZW = re.compile(r'\b')
NONE = re.compile(r'(?:)')
TAIL = re.compile(r'a*\Z')
blank = ' ' * 9000
print(ZW.search(blank, 10), NONE.search(blank, 3000).span(), NONE.match(blank, 7000).span(), ZW.match(blank, 4000))
print(TAIL.search('a' * 9000, 5).span(), TAIL.match('a' * 9000, 100).end(), TAIL.search('b' * 9000, 7).span())
'''


class ReValueTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def build(self, text, mode):
        (self.dir / "main.py").write_text(text, encoding="utf-8")
        env = dict(os.environ)
        env.pop("AIL_NO_GENERAL", None)
        env.pop("AIL_PATH", None)
        env["AIL_UNIFIED_FORCE"] = "1" if mode == "forced" else ""
        if mode == "typed":
            env["AIL_NO_GENERAL"] = "1"
        exe = self.dir / ("out_" + mode)
        if exe.exists():
            exe.unlink()
        built = subprocess.run([sys.executable, "-B", CLI, "compile", "main.py", "--syntax", "python", "-o", str(exe)],
                               cwd=self.dir, capture_output=True, text=True, timeout=900, env=env)
        return built, exe

    def same_as_cpython(self, text, modes=("default", "forced")):
        (self.dir / "main.py").write_text(text, encoding="utf-8")
        want = subprocess.run([sys.executable, "-B", "main.py"], cwd=self.dir, capture_output=True, timeout=60)
        for mode in modes:
            built, exe = self.build(text, mode)
            self.assertEqual(built.returncode, 0, built.stderr)
            ran = subprocess.run([str(exe)], capture_output=True, timeout=60)
            self.assertEqual(ran.stdout.decode(), want.stdout.decode(), mode)
            self.assertEqual(ran.returncode, want.returncode, ran.stderr.decode())

    def refused(self, text, *needles):
        built, exe = self.build(text, "default")
        self.assertNotEqual(built.returncode, 0, built.stdout)
        self.assertFalse(exe.exists())
        for needle in needles:
            self.assertIn(needle, built.stderr)
        self.assertNotIn("Traceback", built.stderr)

    def loud(self, text, needle):
        for mode in ("default", "forced"):
            built, exe = self.build(text, mode)
            self.assertEqual(built.returncode, 0, built.stderr)
            ran = subprocess.run([str(exe)], capture_output=True, timeout=60)
            self.assertNotEqual(ran.returncode, 0, mode)
            self.assertIn(needle, ran.stderr.decode(), mode)

    def test_v1_pos_endpos(self):
        self.same_as_cpython(POS, ("typed", "default", "forced"))

    def test_v2_alias_and_tree_shapes(self):
        self.same_as_cpython(ALIAS)

    def test_v3_refused_by_name(self):
        self.refused("import re\n\nP = re.compile(r'(\\d+)')\n\n\ndef use(p, s):\n    return p.match(s)\n\n\n"
                     "print(use(P, '12').group(1))\n", "the compiled pattern P is used as a value")
        self.refused("import re\n\nP = re.compile(r'a')\nP = re.compile(r'b')\nprint(P.match('b') is not None)\n",
                     "re.compile is built only as")
        self.refused("import re\n\n\ndef f(s):\n    return P.match(s, 1) is not None\n\n\ndef g(s):\n    return f(s)\n\n\n"
                     "h = g\nprint(h('xa'))\nP = re.compile(r'a')\n", "may be used before")
        self.refused("import re\n\nP = re.compile(r'(\\d+)')\n\n\ndef f(s):\n    if len(s) > 3:\n        return m(s, 1)\n"
                     "    m = P.match\n    return m(s, 0)\n\n\nprint(f('12').group(1))\n",
                     "the compiled pattern P is used as a value")

    def test_v4_loud_stops(self):
        self.loud("import re\n\nT = re.compile(r' *(\\d+)')\nprint(int(T.match('x 99999999999999999999', 1).group(1)))\n",
                  "OverflowError")
        self.loud("import re\n\nE = re.compile(r'')\nprint(E.match('abc', 2, 1) is None)\n", "endpos before pos")

    def test_v5_long_subjects(self):
        self.same_as_cpython(LONG)


if __name__ == "__main__":
    unittest.main()

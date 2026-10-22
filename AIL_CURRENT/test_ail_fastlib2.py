"""Branch fastlib2: json, re and statistics on the general path run their hot loops in C (jsonbrt.py, rebrt.py,
statbrt.py). Each program below is built by the general path (a generator function forces it), run, and must print
what CPython 3.12 prints, error messages included; the C is checked to be there where the library is used and absent
where it is not.

The declared differences stay: strings are 16-bit (no astral characters, no surrogate escapes), a group that did not
take part in a match is not built, inf / nan are not literals.
"""
import json
import random
import re as pyre
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent
PKG = ROOT / "python" / "pkg-v12"
if str(PKG) not in sys.path:
    sys.path.insert(0, str(PKG))


def compile_python(directory, text, name):
    source, exe = Path(directory, name + ".ail"), Path(directory, name)
    source.write_text(text, encoding="utf-8")
    built = subprocess.run([sys.executable, "-B", str(ROOT / "ail_chatgpt.py"), "compile", source.name, "--syntax", "python",
                            "-o", exe.name, "--debug-dir", "dbg"], cwd=directory, capture_output=True, text=True, timeout=1800)
    return built, exe


def check_against_cpython(case, text, name):
    with tempfile.TemporaryDirectory() as directory:
        built, exe = compile_python(directory, text, name)
        case.assertEqual(built.returncode, 0, built.stdout + built.stderr)
        oracle = Path(directory, "oracle.py")
        oracle.write_text(text, encoding="utf-8")
        want = subprocess.run([sys.executable, "-X", "utf8", str(oracle)], capture_output=True, timeout=300)
        got = subprocess.run([str(exe)], capture_output=True, timeout=300)
        case.assertEqual(got.returncode, want.returncode, got.stderr[-300:])
        a, b = got.stdout.decode().splitlines(), want.stdout.decode().splitlines()
        for n, (x, y) in enumerate(zip(a, b)):
            if x != y:
                case.fail("%s line %d:\n  compiled: %r\n  CPython:  %r" % (name, n + 1, x, y))
        case.assertEqual(len(a), len(b), name)
        return Path(directory, "dbg", "program.c").read_text(encoding="utf-8")


def c_of(case, text, name):
    with tempfile.TemporaryDirectory() as directory:
        built, exe = compile_python(directory, text, name)
        case.assertEqual(built.returncode, 0, built.stdout + built.stderr)
        return Path(directory, "dbg", "program.c").read_text(encoding="utf-8")


FORCE = "\n\ndef _force_general():\n    yield 1\n\n"

# ---------------------------------------------------------------------------------------------------------- json
CH = ['a', 'b', 'Z', ' ', '"', '\\', '/', '\n', '\t', '\r', '\b', '\f', '\x00', '\x1f', '\x7f', 'é', '日', '€', '\u2028', '\uffff',
      '0', '9', "'", '{', '}', '[', ']', ',', ':']


def json_program(seed, ncase):
    rng = random.Random(seed)

    def rstr():
        return ''.join(rng.choice(CH) for _ in range(rng.randrange(0, 12)))

    def rval(d=0):
        k = rng.randrange(0, 9 if d < 3 else 6)
        if k == 0:
            return None
        if k == 1:
            return rng.choice([True, False])
        if k == 2:
            return rng.randrange(-10 ** 6, 10 ** 6)
        if k == 3:
            return rng.choice([0.0, -0.0, 1.5, 1e22, 1e-7, 0.1, float('nan'), float('inf')])
        if k == 4:
            return rstr()
        if k == 5:
            return rng.randrange(-2 ** 40, 2 ** 40)
        if k == 6:
            return [rval(d + 1) for _ in range(rng.randrange(0, 4))]
        return {rstr(): rval(d + 1) for _ in range(rng.randrange(0, 4))}

    def mutate(s):
        if not s:
            return s
        i = rng.randrange(0, len(s))
        k = rng.randrange(0, 6)
        if k == 0:
            return s[:i]
        if k == 1:
            return s[:i] + s[i + 1:]
        if k == 2:
            return s[:i] + rng.choice(CH + ['\\u12', '\\x', '\\u00zz', '\\u00e9', '\\n', '\\"']) + s[i:]
        if k == 3:
            return s[:i] + rng.choice(CH) + s[i + 1:]
        if k == 4:
            return s + rng.choice([' ', 'x', ',', ']', '}'])
        return ' \n' + s

    cases = []
    while len(cases) < ncase:
        kw = dict(ensure_ascii=rng.choice([True, False]), indent=rng.choice([None, 0, 2, '\t']), sort_keys=rng.choice([False, True]))
        try:
            s = json.dumps(rval(), **kw)
        except Exception:
            continue
        cases.append(mutate(s) if rng.random() < 0.5 else s)
    for _ in range(ncase // 3):
        cases.append('"' + ''.join(rng.choice(CH + ['\\n', '\\u00e9', '\\"', '\\\\', '\\/', '\\q', '\\u00', '\\uZZZZ']) for _ in range(rng.randrange(0, 10)))
                     + rng.choice(['"', '', '"x']))
    dopts = [(rng.choice([True, False]), rng.choice([None, 0, 1, 3, '\t']), rng.choice([False, True]),
              rng.choice([None, (',', ':'), (', ', ': ')]), rng.choice([True, False]), rng.choice([True, False]))
             for _ in range(ncase // 2)]
    return '''import json
%s
CASES = %r
DOPTS = %r


def main():
    good = []
    for s in CASES:
        try:
            r = json.loads(s)
            good.append(r)
            print("ok", repr(r))
        except Exception as e:
            print(type(e).__name__, e)
    k = 0
    for v in good:
        o = DOPTS[k %% len(DOPTS)]
        k += 1
        try:
            print(json.dumps(v, ensure_ascii=o[0], indent=o[1], sort_keys=o[2], separators=o[3], allow_nan=o[4], skipkeys=o[5]))
        except Exception as e:
            print(type(e).__name__, e)


main()
''' % (FORCE, cases, dopts)


# ---------------------------------------------------------------------------------------------------------- re
PATTERNS = [r'(\d+)-(\w+)', r'\bfoo\b|ba+r', r'^\s*(\w+)\s*=\s*(.*?)\s*$', r'[a-c]{2,3}?x', r'(?:ab)+c?', r'a(?=b)', r'(?<=x)y+',
            r'[Hh]ello (\w+)', r'(?m)^(\w)', r'(?s)a.b', r'\Bo\B', r'x*', r'(?P<k>[a-z]+):(?P<v>\d+)', r'[^\W\d]+', r'\.\s|[,;]\s*',
            r'(a|ab)(c|bcd)', r'\w+@\w+\.com']
TEXTS = ['', 'foo bar baaar foobar', '12-ab 7-cd', '  key = value  ', 'abcabcx aabx', 'xyyyz abab ababc', 'Hello World, HELLO there',
         'line one\nline two\n\nthree', 'a\nb a b', 'moon boo foo', 'k1:23 zz:4', 'one. two; three,four', 'abcd', 'me@example.com you@mail.example.org',
         'naïve café 12-é', 'Ünï: 5']


def re_program():
    lines = ["import re", FORCE, "TEXTS = %r" % (TEXTS,)]
    for k, p in enumerate(PATTERNS):
        lines.append("PAT%d = %r" % (k, p))
    lines += ["", "def main():", "    for t in TEXTS:"]
    for k, p in enumerate(PATTERNS):
        ng = pyre.compile(p).groups
        lines.append("        m = re.search(PAT%d, t)" % k)
        lines.append("        if m is None:")
        lines.append("            print(%d, 'search', None)" % k)
        lines.append("        else:")
        lines.append("            print(%d, 'search', m.start(), m.end(), repr(m.group(0)))" % k)
        for g in range(1, ng + 1):
            lines.append("            print(%d, 'g%d', m.start(%d), m.end(%d), repr(m.group(%d)))" % (k, g, g, g, g))
        for op in ("match", "fullmatch"):
            lines.append("        m = re.%s(PAT%d, t)" % (op, k))
            lines.append("        if m is None:")
            lines.append("            print(%d, '%s', None)" % (k, op))
            lines.append("        else:")
            lines.append("            print(%d, '%s', m.start(), m.end(), repr(m.group(0)))" % (k, op))
        if ng <= 1:
            lines.append("        print(%d, 'findall', re.findall(PAT%d, t))" % (k, k))
        if ng == 0:
            lines.append("        print(%d, 'split', re.split(PAT%d, t))" % (k, k))
        lines.append("        print(%d, 'sub', repr(re.sub(PAT%d, '<>', t)), repr(re.sub(PAT%d, '#', t, count=2)))" % (k, k, k))
        lines.append("        for mm in re.finditer(PAT%d, t):" % k)
        lines.append("            print(%d, 'it', mm.start(), mm.end(), repr(mm.group(0)))" % k)
    lines += ["", "main()"]
    return "\n".join(lines) + "\n"


# ---------------------------------------------------------------------------------------------------------- statistics
def stat_program(seed):
    rng = random.Random(seed)
    cases = []
    for _ in range(60):
        kind = rng.randrange(0, 5)
        ln = rng.choice([0, 1, 2, 3, 5, 8, 20, 60])
        if kind == 0:
            xs = [rng.randrange(-50, 50) for _ in range(ln)]
        elif kind == 1:
            xs = [rng.randrange(-10 ** 6, 10 ** 6) for _ in range(ln)]
        elif kind == 2:
            xs = [round(rng.uniform(-100, 100), rng.randrange(0, 5)) for _ in range(ln)]
        elif kind == 3:
            xs = [rng.choice([0.1, 0.2, 0.3, 1e-9, 1e9, 2.5, -2.5, 1e15, -0.0, 0, True]) for _ in range(ln)]
        else:
            xs = [rng.uniform(-1e6, 1e6) for _ in range(ln)]
        cases.append(xs)
    mus = [None, None, 0, 3, 2.5, -1.5]
    return '''import statistics
%s
CASES = %r
MUS = %r
NAMES = ("mean", "fmean", "median", "median_low", "median_high", "mode", "multimode", "variance", "stdev", "pvariance",
         "pstdev", "harmonic_mean", "geometric_mean", "variance_mu", "stdev_mu", "pvariance_mu", "pstdev_mu")


def main():
    k = 0
    for xs in CASES:
        mu = MUS[k %% len(MUS)]
        k += 1
        for name in NAMES:
            try:
                if name == "mean": r = statistics.mean(xs)
                elif name == "fmean": r = statistics.fmean(xs)
                elif name == "median": r = statistics.median(xs)
                elif name == "median_low": r = statistics.median_low(xs)
                elif name == "median_high": r = statistics.median_high(xs)
                elif name == "mode": r = statistics.mode(xs)
                elif name == "multimode": r = statistics.multimode(xs)
                elif name == "variance": r = statistics.variance(xs)
                elif name == "stdev": r = statistics.stdev(xs)
                elif name == "pvariance": r = statistics.pvariance(xs)
                elif name == "pstdev": r = statistics.pstdev(xs)
                elif name == "harmonic_mean": r = statistics.harmonic_mean(xs)
                elif name == "geometric_mean": r = statistics.geometric_mean(xs)
                elif name == "variance_mu": r = statistics.variance(xs, mu)
                elif name == "stdev_mu": r = statistics.stdev(xs, mu)
                elif name == "pvariance_mu": r = statistics.pvariance(xs, mu)
                else: r = statistics.pstdev(xs, mu)
                print(name, len(xs), repr(r))
            except Exception as e:
                print(name, len(xs), type(e).__name__, e)


main()
''' % (FORCE, cases, mus)


class FastLib2(unittest.TestCase):
    def test_json_matches_cpython(self):
        for seed in (1, 2):
            with self.subTest(seed=seed):
                body = check_against_cpython(self, json_program(seed, 400), "fl2_json%d" % seed)
                self.assertIn("ail2j_scan", body)

    def test_re_matches_cpython(self):
        body = check_against_cpython(self, re_program(), "fl2_re")
        self.assertIn("ail2x_run_p", body)

    def test_statistics_matches_cpython(self):
        for seed in (1, 2):
            with self.subTest(seed=seed):
                body = check_against_cpython(self, stat_program(seed), "fl2_stat%d" % seed)
                self.assertIn("ail2q_partials", body)

    def test_c_only_where_the_library_is_used(self):
        body = c_of(self, "def gen():\n    yield 1\n\nprint(sum(gen()), 'x'.upper())\n", "fl2_plain")
        for mark in ("ail2j_", "ail2x_", "ail2q_partials"):
            self.assertNotIn(mark, body)
        body = c_of(self, "import json\n\ndef gen():\n    yield 1\n\nprint(json.dumps({'a': [1, 2]}), sum(gen()))\n", "fl2_jsononly")
        self.assertIn("ail2j_quote", body)
        self.assertNotIn("ail2x_", body)
        self.assertNotIn("ail2q_partials", body)


if __name__ == "__main__":
    unittest.main()

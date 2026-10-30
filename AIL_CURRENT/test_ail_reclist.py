"""Lists of records as a parameter, text of lists, and more list operations on the typed path, against CPython 3.12.

A `list[Rec]` parameter (Rec with int, float and str fields) is lowered by the IR: `for r in recs`, `recs[i]`, `len(recs)`,
`r.hits += 1`, a record handed on to a call, with an accumulator over a field kept exact (tagged). str(xs), repr(xs),
f"{xs}" and print(xs) of lists of int, exact int, float and str are written by the IR with CPython's own list repr.
`xs.pop(i)`, `xs.reverse()`, `xs.extend(ys)` and `del xs[i]` work on lists of int, float and exact int
(and with them insert/remove/`+=`/`sort(reverse=True)`, which the front end rewrites to those).

R1  the reproducer (recs_t_s) is typed (no "built on the general path" note) and prints what CPython prints
R2  probe programs: empty list, aliasing, a record mutated in the callee, a record shared by two lists, a negative and an
    out-of-range index, float fields nan/inf/-0.0/1e16/0.1+0.2, int fields at the int64 edges summing beyond int64 inside the
    accumulator, str fields with quotes/backslashes/non-ASCII/emoji: equal to CPython in the default build and under
    AIL_UNIFIED_FORCE=1 (the emoji program is refused loudly by the forced 16-bit general runtime, never wrong)
R3  a callee that resizes the list it was given keeps the program on the exact general path with the same answers
R4  list text: lists of exact ints beyond int64, floats (nan, inf, -0.0, 1e16, 1e-07), strs (quotes, escapes, non-ASCII)
R5  pop(i) / reverse / extend / del / insert / remove on a list of exact ints, with empty and big inputs
"""
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent
HAVE_CC = shutil.which('gcc') is not None or shutil.which('cc') is not None

PROGRAMS = {
    'pa5': 'from dataclasses import dataclass\n\n\n@dataclass\nclass Rec:\n    id: int\n    name: str\n    score: float\n    hits: int\n\n\ndef count_hits(recs: list[Rec]) -> int:\n    h = 0\n    for r in recs:\n        h += r.hits\n    return h\n\n\ndef inner(recs: list[Rec], k: int) -> int:\n    s = 0\n    for r in recs:\n        s += r.hits * k\n    return s\n\n\ndef outer(recs: list[Rec]) -> int:\n    t = 0\n    for k in range(1, 4):\n        t += inner(recs, k)\n    return t + count_hits(recs)\n\n\ndef pair(a: list[Rec], b: list[Rec]) -> int:\n    for r in a:\n        r.hits += 10\n    n = 0\n    for r in b:\n        n += r.hits\n    return n\n\n\ndef at(recs: list[Rec], i: int) -> int:\n    return recs[i].hits + 0\n\n\ndef safe_at(recs: list[Rec], i: int) -> int:\n    try:\n        x = at(recs, i)\n    except IndexError:\n        x = -999\n    return x\n\n\ndef stringy(recs: list[Rec]) -> str:\n    out = ""\n    for r in recs:\n        out += r.name + ";"\n    return out\n\n\ndef sum_big(recs: list[Rec]) -> int:\n    h = 0\n    for r in recs:\n        h += r.hits\n        h -= 1\n    return h\n\n\ndef make() -> list[Rec]:\n    out: list[Rec] = []\n    for i in range(4):\n        out.append(Rec(i, "r" + str(i), i * 1.5, i + 3))\n    return out\n\n\ndef main() -> None:\n    recs = make()\n    other = [recs[1], recs[3]]\n    print(count_hits(recs), outer(recs))\n    print(pair(recs, other), count_hits(recs), count_hits(other))\n    print(pair(recs, recs))\n    print(safe_at(recs, 0), safe_at(recs, -1), safe_at(recs, 4), safe_at(recs, -5))\n    print(stringy(recs))\n    print(sum_big(recs))\n    print(at(recs, 0))\n\n\nmain()\n',
    'pg1': 'from dataclasses import dataclass\n\n\n@dataclass\nclass Rec:\n    name: str\n    score: float\n    hits: int\n\n\ndef count_hits(recs: list[Rec]) -> int:\n    h = 0\n    for r in recs:\n        h += r.hits\n    return h\n\n\ndef bump(recs: list[Rec]) -> None:\n    for r in recs:\n        r.hits = r.hits * 4\n\n\ndef main() -> None:\n    recs: list[Rec] = []\n    for i in range(3):\n        recs.append(Rec("n" + str(i), i * 0.5, 4611686018427387904 + i))\n    print(count_hits(recs))\n    bump(recs)\n    print(recs[0].hits, count_hits(recs))\n\n\nmain()\n',
    'pg2': 'from dataclasses import dataclass\n\n\n@dataclass\nclass Rec:\n    name: str\n    score: float\n    hits: int\n\n\ndef total(recs: list[Rec]) -> int:\n    h = 0\n    for r in recs:\n        h += r.hits\n    return h\n\n\ndef grow(recs: list[Rec], k: int) -> None:\n    for r in recs:\n        r.hits += k\n\n\ndef grow2(recs: list[Rec]) -> None:\n    for r in recs:\n        r.hits *= 3\n\n\ndef main() -> None:\n    a: list[Rec] = []\n    for i in range(4):\n        a.append(Rec("é\'\\"\\\\" + str(i), float(i) / 3, 9223372036854775807 - i))\n    b: list[Rec] = []\n    for i in range(4):\n        b.append(Rec("x", -0.0, -9223372036854775807 + i * 2))\n    c: list[Rec] = []\n    for i in range(4):\n        c.append(Rec("y", 1e16, 3037000500 * 3037000500 + i))\n    print(total(a), total(b), total(c))\n    grow(a, 5)\n    print(total(a))\n    grow2(b)\n    print(total(b))\n    grow(c, 9223372036854775807)\n    print(total(c))\n\n\nmain()\n',
    'pe1': 'def main() -> None:\n    fs = [0.1 + 0.2, 1e16, -0.0, 2.5, 1e-7, 123456789.125, float("inf"), float("nan"), -float("inf"), 1e22, 5e-324]\n    ss = ["a", "it\'s", \'say "hi"\', "back\\\\slash", "tab\\t", "nl\\n", "é", "日本", "\\x00\\x7f", \'both \\\' and "\']\n    xs = [1, -2, 3, 9223372036854775807, -9223372036854775807]\n    text = str(fs) + " " + str(ss) + " " + str(xs)\n    print(text)\n    print(len(text), repr(xs), repr(fs))\n    print(f"{xs}|{fs}|{ss}")\n    print(f"{xs!r}")\n    print(str(xs), str(fs))\n    es: list[str] = []\n    ei: list[int] = []\n    print(str(es), str(ei))\n\n\nmain()\n',
    'recs': 'from dataclasses import dataclass\n\n@dataclass\nclass Rec:\n    id: int\n    name: str\n    score: float\n    hits: int\n\ndef build(n: int) -> list[Rec]:\n    out: list[Rec] = []\n    for i in range(n):\n        out.append(Rec(i, "r" + str(i % 97), (i * 37 % 1000) / 10.0, 0))\n    return out\n\ndef work(recs: list[Rec], rounds: int) -> float:\n    total = 0.0\n    n = len(recs)\n    for k in range(rounds):\n        for i in range(n):\n            r = recs[i]\n            if r.score > 50.0:\n                r.hits += 1\n                total += r.score\n            else:\n                total -= r.score * 0.5\n    return total\n\ndef count_hits(recs: list[Rec]) -> int:\n    h = 0\n    for r in recs:\n        h += r.hits\n    return h\n\ndef main() -> None:\n    recs = build(20000)\n    t = work(recs, 20)\n    print(round(t, 3), count_hits(recs))\n\nmain()\n',
    'pa1': 'from dataclasses import dataclass\n\n\n@dataclass\nclass Rec:\n    id: int\n    name: str\n    score: float\n    hits: int\n\n\ndef count_hits(recs: list[Rec]) -> int:\n    h = 0\n    for r in recs:\n        h += r.hits\n    return h\n\n\ndef total_score(recs: list[Rec]) -> float:\n    t = 0.0\n    for i in range(len(recs)):\n        r = recs[i]\n        t += r.score\n    return t\n\n\ndef bump(recs: list[Rec], by: int) -> int:\n    n = 0\n    for r in recs:\n        r.hits += by\n        n += 1\n    return n\n\n\ndef last_hits(recs: list[Rec]) -> int:\n    h = recs[-1].hits\n    return h + recs[0].hits\n\n\ndef first_or_neg(recs: list[Rec]) -> int:\n    if len(recs) == 0:\n        return -1\n    return recs[0].id\n\n\ndef weird(recs: list[Rec], a: Rec) -> int:\n    s = 0\n    for r in recs:\n        if r.id == a.id:\n            s += r.hits + a.hits\n    return s\n\n\ndef make() -> list[Rec]:\n    out: list[Rec] = []\n    out.append(Rec(1, "a\'b\\"c\\\\d", float("nan"), 9223372036854775807))\n    out.append(Rec(2, "é日本", float("inf"), -9223372036854775807))\n    out.append(Rec(3, "x", -0.0, 5))\n    out.append(Rec(4, "y", 1e16, 9223372036854775807))\n    out.append(Rec(5, "z", 0.1 + 0.2, -9223372036854775807))\n    return out\n\n\ndef main() -> None:\n    empty: list[Rec] = []\n    print(count_hits(empty), total_score(empty), bump(empty, 3), first_or_neg(empty))\n    recs = make()\n    print(count_hits(recs))\n    print(total_score(recs))\n    alias = recs\n    print(count_hits(recs), count_hits(alias))\n    for r in recs:\n        r.hits = r.hits // 2\n    print(bump(alias, 1), count_hits(recs), count_hits(alias))\n    print(bump(recs, 2))\n    print(last_hits(recs))\n    print(weird(recs, recs[2]))\n    print(first_or_neg(recs))\n    big = [Rec(i, "n", 1.5, 9223372036854775800 - i) for i in range(3)]\n    big.append(Rec(9, "m", 2.5, -9223372036854775807))\n    big.append(Rec(10, "m", 2.5, -9223372036854775807))\n    big.append(Rec(11, "m", 2.5, -9223372036854775807))\n    print(count_hits(big))\n    for r in recs:\n        print(r.id, r.name, r.score, r.hits)\n\n\nmain()\n',
    'pa2': 'from dataclasses import dataclass\n\n\n@dataclass\nclass Rec:\n    id: int\n    name: str\n    score: float\n    hits: int\n\n\ndef count_hits(recs: list[Rec]) -> int:\n    h = 0\n    for r in recs:\n        h += r.hits\n    return h\n\n\ndef inner(recs: list[Rec], k: int) -> int:\n    s = 0\n    for r in recs:\n        s += r.hits * k\n    return s\n\n\ndef outer(recs: list[Rec]) -> int:\n    t = 0\n    for k in range(1, 4):\n        t += inner(recs, k)\n    return t + count_hits(recs)\n\n\ndef pair(a: list[Rec], b: list[Rec]) -> int:\n    for r in a:\n        r.hits += 10\n    n = 0\n    for r in b:\n        n += r.hits\n    return n\n\n\ndef at(recs: list[Rec], i: int) -> int:\n    return recs[i].hits + 0\n\n\ndef safe_at(recs: list[Rec], i: int) -> int:\n    try:\n        x = at(recs, i)\n    except IndexError:\n        x = -999\n    return x\n\n\ndef stringy(recs: list[Rec]) -> str:\n    out = ""\n    for r in recs:\n        out += r.name + ";"\n    return out\n\n\ndef sum_big(recs: list[Rec]) -> int:\n    h = 0\n    for r in recs:\n        h += r.hits\n        h -= 1\n    return h\n\n\ndef make() -> list[Rec]:\n    out: list[Rec] = []\n    for i in range(4):\n        out.append(Rec(i, "r" + str(i), i * 1.5, i * 3))\n    return out\n\n\ndef main() -> None:\n    recs = make()\n    other = [recs[1], recs[3]]\n    print(count_hits(recs), outer(recs))\n    print(pair(recs, other), count_hits(recs), count_hits(other))\n    print(pair(recs, recs))\n    print(safe_at(recs, 0), safe_at(recs, -1), safe_at(recs, 4), safe_at(recs, -5))\n    print(stringy(recs))\n    print(sum_big(recs))\n    print(at(recs, 0))\n\n\nmain()\n',
    'pa3': 'from dataclasses import dataclass\n\n\n@dataclass\nclass Rec:\n    id: int\n    name: str\n    score: float\n    hits: int\n\n\ndef count_hits(recs: list[Rec]) -> int:\n    h = 0\n    for r in recs:\n        h += r.hits\n    return h\n\n\ndef inner(recs: list[Rec], k: int) -> int:\n    s = 0\n    for r in recs:\n        s += r.hits * k\n    return s\n\n\ndef outer(recs: list[Rec]) -> int:\n    t = 0\n    for k in range(1, 4):\n        t += inner(recs, k)\n    return t + count_hits(recs)\n\n\ndef pair(a: list[Rec], b: list[Rec]) -> int:\n    for r in a:\n        r.hits += 10\n    n = 0\n    for r in b:\n        n += r.hits\n    return n\n\n\ndef at(recs: list[Rec], i: int) -> int:\n    return recs[i].hits + 0\n\n\ndef safe_at(recs: list[Rec], i: int) -> int:\n    try:\n        x = at(recs, i)\n    except IndexError:\n        x = -999\n    return x\n\n\ndef stringy(recs: list[Rec]) -> str:\n    out = ""\n    for r in recs:\n        out += r.name + ";"\n    return out\n\n\ndef sum_big(recs: list[Rec]) -> int:\n    h = 0\n    for r in recs:\n        h += r.hits\n        h -= 1\n    return h\n\n\ndef clear_all(recs: list[Rec]) -> int:\n    n = 0\n    for r in recs:\n        n += 1\n        if n == 2:\n            recs.clear()\n    return n\n\n\ndef make() -> list[Rec]:\n    out: list[Rec] = []\n    for i in range(4):\n        out.append(Rec(i, "r" + str(i), i * 1.5, i * 3))\n    return out\n\n\ndef main() -> None:\n    recs = make()\n    other = [recs[1], recs[3]]\n    print(count_hits(recs), outer(recs))\n    print(safe_at(recs, 0), safe_at(recs, -1), safe_at(recs, 4), safe_at(recs, -5))\n    print(stringy(recs))\n    print(sum_big(recs))\n    print(clear_all(recs), len(recs))\n    print(at(recs, 0))\n\n\nmain()\n',
    'pa4': 'from dataclasses import dataclass\n\n\n@dataclass\nclass Rec:\n    id: int\n    name: str\n    score: float\n    hits: int\n\n\ndef count_hits(recs: list[Rec]) -> int:\n    h = 0\n    for r in recs:\n        h += r.hits\n    return h\n\n\ndef best(recs: list[Rec]) -> float:\n    top = -1.0\n    for i in range(len(recs)):\n        r = recs[i]\n        if r.score > top:\n            top = r.score\n    return top\n\n\ndef main() -> None:\n    recs: list[Rec] = []\n    recs.append(Rec(1, "quote\'single", 1e16, 3))\n    recs.append(Rec(2, \'quote"double\', 0.1 + 0.2, 4))\n    recs.append(Rec(3, "back\\\\slash", -0.0, 5))\n    recs.append(Rec(4, "emoji \\U0001F600 and é 日本", float("inf"), 6))\n    recs.append(Rec(5, "tab\\tnl\\n", float("nan"), -7))\n    print(count_hits(recs), best(recs))\n    for r in recs:\n        print(r.id, r.name, r.score, r.hits)\n        print(repr(r.name), len(r.name))\n\n\nmain()\n',
    'pb1': 'import sys\n\n\ndef main() -> None:\n    toks = sys.stdin.read().split()\n    xs = [int(t) for t in toks]\n    ss = [t for t in toks]\n    fs = [0.1 + 0.2, 1e16, -0.0, float("nan"), float("inf"), -float("inf"), 1e-7, 123456789.125, 5e-324, 1e22]\n    qs = ["a", "it\'s", \'say "hi"\', "back\\\\slash", "tab\\t", "nl\\n", "é", "日本", "\\x00\\x7f", \'both \\\' and "\']\n    print(xs)\n    print(ss)\n    print(fs)\n    print(qs)\n    print(str(xs), str(ss))\n    print(str(fs))\n    print(repr(qs))\n    print(f"{xs}|{ss}|{fs}|{qs}")\n    print(f"{xs!r} {len(xs)}")\n    ys = xs[1:]\n    print(ys, sorted(xs))\n    em1 = xs[:0]\n    print(em1)\n    s = str(xs)\n    print(len(s), s)\n    total = 0\n    for x in xs:\n        total += x\n    print(total)\n\n\nmain()\n',
    'pd1': 'import sys\n\n\ndef main() -> None:\n    xs = [int(t) for t in sys.stdin.read().split()]\n    print(xs)\n    xs.reverse()\n    print(xs)\n    xs.extend(xs)\n    print(xs, len(xs))\n    xs += [7, -7]\n    ys = [x * 2 for x in xs]\n    xs.extend(ys)\n    print(xs)\n    xs.insert(0, 5)\n    xs.insert(-1, 6)\n    xs.insert(100, 8)\n    xs.insert(-100, 9)\n    print(xs)\n    if 5 in xs:\n        xs.remove(5)\n    print(xs)\n    try:\n        xs.remove(1000000000000000003)\n    except ValueError:\n        print("no such")\n    print(xs.pop(0), xs.pop(-1), xs.pop(1))\n    del xs[0]\n    del xs[-1]\n    print(xs)\n    try:\n        del xs[len(xs)]\n    except IndexError:\n        print("del out of range")\n    try:\n        print(xs.pop(len(xs) + 5))\n    except IndexError:\n        print("pop out of range")\n    zs = []\n    try:\n        zs.pop(0)\n    except IndexError:\n        print("empty pop")\n    try:\n        del zs[0]\n    except IndexError:\n        print("empty del")\n    zs.extend(zs)\n    zs.reverse()\n    print(len(zs))\n    ws = xs\n    ws.reverse()\n    ws.extend([1])\n    print(len(ws), xs)\n    acc = 0\n    for x in xs:\n        acc += x\n    print(acc)\n    xs.sort(reverse=True)\n    top = xs[:3]\n    print(top)\n    print(xs.index(xs[0]), xs.count(xs[0]))\n\n\nmain()\n',
}

PB1_INPUTS = ['5 -3 99999999999999999999 9223372036854775807 9223372036854775808 -9223372036854775809 0 -0 007', '', '7']
PD1_INPUTS = ['\n', '5\n', '1 2 3\n', '3 1 2 9223372036854775807 9223372036854775808\n', '99999999999999999999 5 -99999999999999999999 7 7 7 123456789012345678901234567890\n', '4 5 5 5 6 6 6 7 7 7 -1 -2\n']


def compile_default(directory, text, name, force=False):
    source, exe = Path(directory, name + '.py'), Path(directory, name + ('_f' if force else '_x'))
    source.write_text(text, encoding='utf-8')
    env = dict(os.environ, AIL_NO_CACHE='1')
    for key in ('AIL_NO_GENERAL', 'AIL_UNIFIED_FORCE', 'AIL_QUIET_FALLBACK'):
        env.pop(key, None)
    if force:
        env['AIL_UNIFIED_FORCE'] = '1'
    res = subprocess.run([sys.executable, '-B', str(ROOT / 'ail_chatgpt.py'), 'compile', source.name, '-o', exe.name],
                         cwd=directory, capture_output=True, text=True, timeout=900, env=env)
    return res, exe, source


def typed(res):
    return 'built on the general path' not in res.stderr


@unittest.skipUnless(HAVE_CC, 'needs a C compiler')
class RecList(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.mkdtemp(prefix='reclist_')

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp, ignore_errors=True)

    def check(self, name, inputs=('',), expect_typed=None, force=True, loud_force=False):
        text = PROGRAMS[name]
        res, exe, source = compile_default(self.tmp, text, name)
        self.assertEqual(res.returncode, 0, res.stderr[-1500:])
        if expect_typed is not None:
            self.assertEqual(typed(res), expect_typed, res.stderr[-600:])
        built = [exe]
        if force:
            fres, fexe, _ = compile_default(self.tmp, text, name, force=True)
            if loud_force:
                self.assertNotEqual(fres.returncode, 0, 'the forced general build must refuse this program loudly')
                self.assertIn('16-bit', fres.stdout + fres.stderr)
            else:
                self.assertEqual(fres.returncode, 0, fres.stderr[-1500:])
                built.append(fexe)
        for stdin in inputs:
            want = subprocess.run([sys.executable, '-W', 'ignore', str(source)], input=stdin.encode('utf-8'),
                                  capture_output=True, timeout=300)
            for binary in built:
                got = subprocess.run([str(binary)], input=stdin.encode('utf-8'), capture_output=True, timeout=300)
                self.assertEqual(got.stdout, want.stdout, (name, binary.name, stdin))
                self.assertEqual(got.returncode, want.returncode, (name, binary.name, stdin, got.stderr[-200:]))

    # R1
    def test_reproducer_typed_and_equal(self):
        self.check('recs', expect_typed=True)

    # R2
    def test_record_list_probes(self):
        self.check('pa5', expect_typed=True)
        # int fields that can hold more than a small int (literals near 2**63, products, `+= k`): the IR does not take the
        # list, the program keeps the exact general path and prints what CPython prints (no narrowing, no "integer overflow")
        for name in ('pa1', 'pa2', 'pg1', 'pg2'):
            self.check(name, expect_typed=False)

    def test_record_strings_with_emoji_are_loud_in_the_16_bit_runtime(self):
        self.check('pa4', expect_typed=True, loud_force=True)

    # R3
    def test_callee_that_resizes_the_list_stays_exact(self):
        self.check('pa3', expect_typed=False)

    # R4
    def test_list_text(self):
        self.check('pb1', inputs=PB1_INPUTS, expect_typed=True)

    def test_list_text_without_exact_ints_on_the_legacy_typed_path(self):
        self.check('pe1', expect_typed=True)

    # R5
    def test_list_operations_on_exact_int_lists(self):
        self.check('pd1', inputs=PD1_INPUTS, expect_typed=True)


if __name__ == '__main__':
    unittest.main()

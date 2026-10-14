"""sorted(key=...), list.sort(key=...) and sorted(d.items(), ...) match CPython 3.12 exactly.

Random inputs with many ties, negative numbers, non-ASCII text (Python orders str by code point and
lower() is the full Unicode mapping) and both directions of `reverse=` are sorted by the compiled
programs below and by CPython; stdout must agree byte for byte, so stability and tie order are
checked along with the order itself.
"""
import random
import subprocess
import time
import unittest
import test_ail_c_objects as support
from test_ail_map_fields import build


LISTS = r'''struct R { w: str; n: int; f: float; }
fn noisy(w: str) -> int { print("key " + w); return len(w); }
fn show(tag: str, xs: list[str]) -> void { print(tag + ": " + "|".join(xs)); }
fn show_i(tag: str, xs: list[int]) -> void { print(tag + ": " + " ".join([str(x) for x in xs])); }
fn show_f(tag: str, xs: list[float]) -> void { print(tag + ": " + " ".join([str(x) for x in xs])); }
fn show_r(tag: str, rs: list[R]) -> void {
    let out: list[str] = [];
    for r in rs { out.append(r.w + "/" + str(r.n) + "/" + str(r.f)); }
    print(tag + ": " + "|".join(out));
}
fn by_len(ws: list[str]) -> list[str] { return sorted(ws, key=lambda w: len(w)); }
fn main() -> int {
    let text: str = read_bytes(sys.argv[1]).decode("utf-8");
    let ws: list[str] = [];
    let ns: list[int] = [];
    let fs: list[float] = [];
    let rs: list[R] = [];
    for line in text.split("\n") {
        if len(line) == 0 { continue; }
        let parts = line.split("\t");
        let n = int(parts[1]);
        ws.append(parts[0]);
        ns.append(n);
        fs.append(n * 0.25);
        rs.append(R(parts[0], n, n * 0.25));
    }
    show("len", sorted(ws, key=lambda w: len(w)));
    show("lenrev", sorted(ws, key=lambda w: len(w), reverse=True));
    show("neglen", sorted(ws, key=lambda w: (-len(w), w)));
    show("lower", sorted(ws, key=lambda w: w.lower()));
    show("lowerrev", sorted(ws, key=lambda w: w.lower(), reverse=True));
    show("first", sorted(ws, key=lambda w: w[:1]));
    show("lenlower", sorted(ws, key=lambda w: (len(w), w.lower(), w)));
    show("ident", sorted(ws, key=lambda w: w));
    show("identrev", sorted(ws, key=lambda w: w, reverse=True));
    show("three", sorted(ws, key=lambda w: (len(w) % 3, w.upper(), -len(w))));
    show("byfn", by_len(ws));
    show_i("mod", sorted(ns, key=lambda x: x % 3));
    show_i("abs", sorted(ns, key=lambda x: abs(x)));
    show_i("negrev", sorted(ns, key=lambda x: -x, reverse=True));
    show_i("tuple", sorted(ns, key=lambda x: (x % 4, -x)));
    show_i("nident", sorted(ns, key=lambda x: x));
    show_f("fsq", sorted(fs, key=lambda f: f * f));
    show_f("fneg", sorted(fs, key=lambda f: -f));
    show_f("fmix", sorted(fs, key=lambda f: (f * f, f)));
    show_f("fident", sorted(fs, key=lambda f: f, reverse=True));
    show_r("rlen", sorted(rs, key=lambda r: len(r.w)));
    show_r("rtuple", sorted(rs, key=lambda r: (-r.n, r.w)));
    show_r("rlow", sorted(rs, key=lambda r: (r.f * r.f, r.w.lower()), reverse=True));
    show_r("rcomp", sorted(rs, key=lambda r: (len(r.w) + r.n, -r.f)));
    let w2 = ws.copy();
    w2.sort(key=lambda w: len(w), reverse=True);
    show("inplace", w2);
    let r2 = rs.copy();
    r2.sort(key=lambda r: r.n % 5);
    show_r("rinplace", r2);
    let n2 = ns.copy();
    n2.sort(key=lambda x: x % 3, reverse=True);
    show_i("ninplace", n2);
    let f2 = fs.copy();
    f2.sort(key=lambda f: abs(f));
    show_f("finplace", f2);
    show("orig", ws);
    show("noisy", sorted(ws, key=noisy));
    show("bynoisy", sorted(ws, key=lambda w: noisy(w) + 0));
    for i, w in enumerate(sorted(ws, key=lambda w: len(w))) { if i < 3 { print(i, w); } }
    return 0;
}
'''

DICTS = r'''fn show(tag: str, xs: list[str]) -> void { print(tag + ": " + "|".join(xs)); }
fn main() -> int {
    let text: str = read_bytes(sys.argv[1]).decode("utf-8");
    let counts: dict[str, int] = {};
    let sums: dict[str, float] = {};
    let last: dict[str, str] = {};
    for line in text.split("\n") {
        if len(line) == 0 { continue; }
        let parts = line.split("\t");
        let n = int(parts[1]);
        counts[parts[0]] = counts.get(parts[0], 0) + 1;
        sums[parts[0]] = sums.get(parts[0], 0.0) + n * 0.25;
        last[parts[0]] = parts[1];
    }
    let out: list[str] = [];
    for k, v in sorted(counts.items()) { out.append(k + "=" + str(v)); }
    show("items", out);
    out.clear();
    for k, v in sorted(counts.items(), reverse=True) { out.append(k + "=" + str(v)); }
    show("itemsrev", out);
    out.clear();
    for k, v in sorted(counts.items(), key=lambda kv: (-kv[1], kv[0])) { out.append(k + "=" + str(v)); }
    show("topn", out);
    out.clear();
    for k, v in sorted(counts.items(), key=lambda kv: kv[1], reverse=True) { out.append(k + "=" + str(v)); }
    show("byval_rev", out);
    out.clear();
    for k, v in sorted(counts.items(), key=lambda kv: kv[1]) { out.append(k + "=" + str(v)); }
    show("byval", out);
    out.clear();
    for k, v in sorted(counts.items(), key=lambda kv: (len(kv[0]), -kv[1])) { out.append(k + "=" + str(v)); }
    show("bylen", out);
    out.clear();
    for k, v in sorted(counts.items(), key=lambda kv: kv[0].lower() + str(kv[1])) { out.append(k + "=" + str(v)); }
    show("mixed", out);
    out.clear();
    for k, x in sorted(sums.items(), key=lambda kv: (kv[1], kv[0])) { out.append(k + "=" + str(x)); }
    show("floats", out);
    out.clear();
    for k, x in sorted(sums.items(), key=lambda kv: -kv[1]) { out.append(k + "=" + str(x)); }
    show("floatsneg", out);
    out.clear();
    for k, t in sorted(last.items(), key=lambda kv: kv[1]) { out.append(k + "=" + t); }
    show("strvals", out);
    out.clear();
    for k, t in sorted(last.items(), key=lambda kv: (kv[1], kv[0]), reverse=True) { out.append(k + "=" + t); }
    show("strvals2", out);
    out.clear();
    for k, t in sorted(last.items()) { out.append(k + "=" + t); }
    show("stritems", out);
    out.clear();
    for k in sorted(counts) { out.append(k); }
    show("keys", out);
    out.clear();
    for k in sorted(counts.keys(), key=lambda k: counts[k]) { out.append(k); }
    show("keysbyval", out);
    out.clear();
    for k in sorted(counts.keys(), key=lambda k: (-counts[k], k)) { out.append(k); }
    show("keystop", out);
    out.clear();
    for k in sorted(counts, key=lambda k: k.lower(), reverse=True) { out.append(k); }
    show("keyslower", out);
    out.clear();
    for i, k in enumerate(sorted(counts.keys(), key=lambda k: -counts[k])) { out.append(str(i) + k); }
    show("enum", out);
    let ks = sorted(counts.keys(), key=lambda k: (-counts[k], k));
    let m = 0;
    for k in ks { m += counts[k]; if m > 3 { break; } }
    print(len(ks), m);
    return 0;
}
'''

TOP = r'''fn main() -> int {
    let text: str = read_bytes(sys.argv[1]).decode("utf-8");
    let counts: dict[str, int] = {};
    for w in text.split() { counts[w] = counts.get(w, 0) + 1; }
    let shown = 0;
    for k, v in sorted(counts.items(), key=lambda kv: (-kv[1], kv[0])) {
        print(k, v);
        shown += 1;
        if shown >= 10 { break; }
    }
    return 0;
}
'''

POSITIONS = r'''struct R { w: str; n: int; }
fn noisy(w: str) -> int { print("key " + w); return len(w); }
fn by_len(ws: list[str]) -> list[str] { return sorted(ws, key=lambda w: len(w)); }
fn first(ws: list[str]) -> str { let s = sorted(ws, key=lambda w: (-len(w), w.upper())); return s[0]; }
fn total(xs: list[int]) -> int { let t = 0; for x in sorted(xs, key=lambda x: -x) { t = t * 3 + x; } return t; }
fn neg(r: R) -> int { return -r.n; }
fn bestf(xs: list[float]) -> float { let s = sorted(xs, key=lambda x: -x); return s[0]; }
fn shortest(ps: list[R]) -> str { let s = sorted(ps, key=lambda p: (len(p.w), -p.n)); return s[0].w; }
fn main() -> int {
    let ws = ["bb", "a", "ccc", "Dd", "e"];
    let ns = [3, 1, 2, 5, 4];
    for w in by_len(ws) { print(w); }
    print(first(ws), total(ns));
    let s = sorted(ws, key=noisy);
    print("|".join(s));
    for round in range(3) {
        let t = sorted(ws, key=lambda w: w.lower() + str(round));
        print("|".join(t));
    }
    let both = sorted(sorted(ws, key=lambda w: len(w)), key=lambda w: w[:1].lower());
    print("|".join(both));
    if sorted(ws, key=lambda w: len(w))[0] == "a" { print("yes"); }
    let rs = [R("x", 2), R("yy", 1), R("z", 2)];
    print(len(sorted(rs, key=lambda r: noisy(r.w))));
    let k = 0;
    while k < 2 { ws.sort(key=lambda w: -len(w)); k += 1; }
    print("|".join(ws));
    let doubled = [x * 2 for x in ns];
    let by_neg = sorted(doubled, key=lambda x: -x);
    print(by_neg[0], by_neg[4]);
    let by_fn = sorted(rs, key=lambda r: neg(r));
    print(by_fn[0].w, by_fn[1].w, by_fn[2].w);
    let by_name = sorted(rs, key=neg, reverse=True);
    print(by_name[0].w, by_name[1].w, by_name[2].w);
    print(bestf([1.5, 2.5, 0.5]), shortest(rs));
    return 0;
}
'''

POSITIONS_EXPECTED = '''a
e
bb
Dd
ccc
ccc 547
key bb
key a
key ccc
key Dd
key e
a|e|bb|Dd|ccc
a|bb|ccc|Dd|e
a|bb|ccc|Dd|e
a|bb|ccc|Dd|e
a|bb|ccc|Dd|e
yes
key x
key yy
key z
3
ccc|bb|Dd|a|e
10 2
x z yy
yy x z
2.5 x
'''

VOCABULARY = ['a', 'b', 'B', 'bb', 'été', '日本', 'Zeta', 'zeta', 'ß', 'İ', 'ǅ', '😀x', 'x', 'xy',
              'xyz', 'Ünï', 'aa', 'AA', 'ǆ', 'Σς', 'ΑΣ', '\U00010400', 'ź']


def expected_lists(rows):
    ws = [w for w, n in rows]
    ns = [n for w, n in rows]
    fs = [n * 0.25 for n in ns]
    rs = [(w, n, n * 0.25) for w, n in rows]
    out = []

    def show(tag, xs):
        out.append(tag + ': ' + '|'.join(xs))

    def show_i(tag, xs):
        out.append(tag + ': ' + ' '.join(str(x) for x in xs))

    def show_r(tag, xs):
        out.append(tag + ': ' + '|'.join('%s/%d/%s' % (w, n, f) for w, n, f in xs))

    show('len', sorted(ws, key=lambda w: len(w)))
    show('lenrev', sorted(ws, key=lambda w: len(w), reverse=True))
    show('neglen', sorted(ws, key=lambda w: (-len(w), w)))
    show('lower', sorted(ws, key=lambda w: w.lower()))
    show('lowerrev', sorted(ws, key=lambda w: w.lower(), reverse=True))
    show('first', sorted(ws, key=lambda w: w[:1]))
    show('lenlower', sorted(ws, key=lambda w: (len(w), w.lower(), w)))
    show('ident', sorted(ws, key=lambda w: w))
    show('identrev', sorted(ws, key=lambda w: w, reverse=True))
    show('three', sorted(ws, key=lambda w: (len(w) % 3, w.upper(), -len(w))))
    show('byfn', sorted(ws, key=lambda w: len(w)))
    show_i('mod', sorted(ns, key=lambda x: x % 3))
    show_i('abs', sorted(ns, key=lambda x: abs(x)))
    show_i('negrev', sorted(ns, key=lambda x: -x, reverse=True))
    show_i('tuple', sorted(ns, key=lambda x: (x % 4, -x)))
    show_i('nident', sorted(ns, key=lambda x: x))
    out.append('fsq: ' + ' '.join(str(x) for x in sorted(fs, key=lambda f: f * f)))
    out.append('fneg: ' + ' '.join(str(x) for x in sorted(fs, key=lambda f: -f)))
    out.append('fmix: ' + ' '.join(str(x) for x in sorted(fs, key=lambda f: (f * f, f))))
    out.append('fident: ' + ' '.join(str(x) for x in sorted(fs, key=lambda f: f, reverse=True)))
    show_r('rlen', sorted(rs, key=lambda r: len(r[0])))
    show_r('rtuple', sorted(rs, key=lambda r: (-r[1], r[0])))
    show_r('rlow', sorted(rs, key=lambda r: (r[2] * r[2], r[0].lower()), reverse=True))
    show_r('rcomp', sorted(rs, key=lambda r: (len(r[0]) + r[1], -r[2])))
    w2 = list(ws)
    w2.sort(key=lambda w: len(w), reverse=True)
    show('inplace', w2)
    r2 = list(rs)
    r2.sort(key=lambda r: r[1] % 5)
    show_r('rinplace', r2)
    n2 = list(ns)
    n2.sort(key=lambda x: x % 3, reverse=True)
    show_i('ninplace', n2)
    f2 = list(fs)
    f2.sort(key=lambda f: abs(f))
    out.append('finplace: ' + ' '.join(str(x) for x in f2))
    show('orig', ws)
    # the key function runs exactly once per element, in input order, before anything is sorted
    for tag in ('noisy', 'bynoisy'):
        for w in ws:
            out.append('key ' + w)
        show(tag, sorted(ws, key=lambda w: len(w)))
    for i, w in enumerate(sorted(ws, key=lambda w: len(w))):
        if i < 3:
            out.append('%d %s' % (i, w))
    return '\n'.join(out) + '\n'


def expected_dicts(rows):
    counts, sums, last = {}, {}, {}
    for w, n in rows:
        counts[w] = counts.get(w, 0) + 1
        sums[w] = sums.get(w, 0.0) + n * 0.25
        last[w] = str(n)
    out = []

    def show(tag, xs):
        out.append(tag + ': ' + '|'.join(xs))

    pair = lambda items: ['%s=%s' % (k, v) for k, v in items]
    show('items', pair(sorted(counts.items())))
    show('itemsrev', pair(sorted(counts.items(), reverse=True)))
    show('topn', pair(sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))))
    show('byval_rev', pair(sorted(counts.items(), key=lambda kv: kv[1], reverse=True)))
    show('byval', pair(sorted(counts.items(), key=lambda kv: kv[1])))
    show('bylen', pair(sorted(counts.items(), key=lambda kv: (len(kv[0]), -kv[1]))))
    show('mixed', pair(sorted(counts.items(), key=lambda kv: kv[0].lower() + str(kv[1]))))
    show('floats', pair(sorted(sums.items(), key=lambda kv: (kv[1], kv[0]))))
    show('floatsneg', pair(sorted(sums.items(), key=lambda kv: -kv[1])))
    show('strvals', pair(sorted(last.items(), key=lambda kv: kv[1])))
    show('strvals2', pair(sorted(last.items(), key=lambda kv: (kv[1], kv[0]), reverse=True)))
    show('stritems', pair(sorted(last.items())))
    show('keys', sorted(counts))
    show('keysbyval', sorted(counts.keys(), key=lambda k: counts[k]))
    show('keystop', sorted(counts.keys(), key=lambda k: (-counts[k], k)))
    show('keyslower', sorted(counts, key=lambda k: k.lower(), reverse=True))
    show('enum', [str(i) + k for i, k in enumerate(sorted(counts.keys(), key=lambda k: -counts[k]))])
    ks = sorted(counts.keys(), key=lambda k: (-counts[k], k))
    m = 0
    for k in ks:
        m += counts[k]
        if m > 3:
            break
    out.append('%d %d' % (len(ks), m))
    return '\n'.join(out) + '\n'


def random_rows(rng, n, vocabulary, spread):
    return [(rng.choice(vocabulary), rng.randrange(-spread, spread + 1)) for _ in range(n)]


class SortKeyTests(unittest.TestCase):
    setUp = support.CObjectTests.setUp
    write = support.CObjectTests.write
    command = support.CObjectTests.command

    def run_program(self, program, rows, name='input.txt'):
        path = self.root / name
        path.write_bytes(''.join('%s\t%d\n' % row for row in rows).encode('utf-8'))
        result = subprocess.run([str(program), str(path)], capture_output=True, timeout=300)
        self.assertEqual(result.returncode, 0, result.stderr.decode(errors='replace'))
        return result.stdout.decode('utf-8')

    def cases(self):
        rng = random.Random(20261012)
        yield []
        yield [('a', 1)]
        yield [('b', 1), ('a', 1)]
        for n in (3, 7, 8, 9, 15, 16, 17, 33, 100, 257):
            for spread in (0, 2, 9):
                yield random_rows(rng, n, VOCABULARY, spread)
        yield random_rows(rng, 3000, VOCABULARY, 4)
        yield random_rows(rng, 2000, ['same'], 0)
        yield random_rows(rng, 600, ['k%d' % i for i in range(300)], 3)

    def test_lists_match_cpython(self):
        program = build(self, 'sort_lists', LISTS)
        for rows in self.cases():
            self.assertEqual(self.run_program(program, rows), expected_lists(rows), rows[:12])

    def test_dicts_match_cpython(self):
        program = build(self, 'sort_dicts', DICTS)
        for rows in self.cases():
            self.assertEqual(self.run_program(program, rows), expected_dicts(rows), rows[:12])

    def test_statement_positions_and_single_evaluation(self):
        program = build(self, 'sort_positions', POSITIONS)
        result = subprocess.run([str(program)], capture_output=True, timeout=60)
        self.assertEqual(result.returncode, 0, result.stderr.decode(errors='replace'))
        self.assertEqual(result.stdout.decode('utf-8'), POSITIONS_EXPECTED)

    def test_top_words_scale_and_match(self):
        program = build(self, 'sort_top', TOP)
        rng = random.Random(7)
        words = []
        while len(words) < 60000:
            words.append(''.join(rng.choice('abcdefghij') for _ in range(rng.randrange(2, 9))) + str(len(words)))
        weights = [1.0 / (i + 1) ** 0.7 for i in range(len(words))]
        text = ' '.join(rng.choices(words, weights, k=400000))
        path = self.root / 'words.txt'
        path.write_text(text, encoding='utf-8')
        counts = {}
        for word in text.split():
            counts[word] = counts.get(word, 0) + 1
        want = ''.join('%s %d\n' % item for item in sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))[:10])
        started = time.monotonic()
        result = subprocess.run([str(program), str(path)], capture_output=True, timeout=120)
        elapsed = time.monotonic() - started
        self.assertEqual(result.returncode, 0, result.stderr.decode(errors='replace'))
        self.assertEqual(result.stdout.decode('utf-8'), want)
        self.assertLess(elapsed, 20)
        self.assertGreater(len(counts), 30000)

    def refused(self, source, *fragments):
        path = self.write('refused.ail', source)
        result = self.command('compile', path, '-o', self.root / 'refused_out')
        text = result.stderr.decode(errors='replace')
        self.assertNotEqual(result.returncode, 0, source)
        self.assertNotIn('Traceback', text, source)
        for fragment in fragments:
            self.assertIn(fragment, text, source)

    def test_everything_else_is_refused_by_name(self):
        self.refused('fn main() -> int { let ws = ["b", "a"]; let f = True; '
                     'let s = sorted(ws, key=lambda w: len(w), reverse=f); print(s[0]); return 0; }',
                     'reverse=')
        self.refused('fn main() -> int { let ws = ["b", "a"]; '
                     'let s = sorted(ws, key=lambda w: (w, w, w, w, w)); print(s[0]); return 0; }',
                     'tuple')
        self.refused('fn main() -> int { let ws = ["b", "a"]; '
                     'let s = sorted(ws, key=lambda w: len(w), cmp=3); print(s[0]); return 0; }',
                     'cmp')
        self.refused('fn main() -> int { let d: dict[str, int] = {"a": 1}; '
                     'let t = sorted(d.items()); print(len(t)); return 0; }',
                     'items')
        self.refused('fn main() -> int { let d: dict[str, int] = {"a": 1}; '
                     'for kv in sorted(d.items()) { print(kv[0]); } return 0; }',
                     'two names')
        self.refused('fn main() -> int { let d: dict[str, int] = {"a": 1}; '
                     'for k, v in sorted(d.items(), key=lambda kv: kv) { print(k); } return 0; }',
                     'kv[0]')
        self.refused('struct P { n: int; } fn main() -> int { let ps = [P(2), P(1)]; '
                     'let s = sorted(ps, key=lambda p: p); print(len(s)); return 0; }',
                     'sort')
        self.refused('fn main() -> int { let ws = ["b", "a"]; '
                     'let s = sorted(ws, key=lambda w: [w]); print(len(s)); return 0; }')


if __name__ == '__main__':
    unittest.main()

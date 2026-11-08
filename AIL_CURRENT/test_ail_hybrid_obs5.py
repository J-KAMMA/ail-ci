"""obs5 (`ail build --cpython`): more bodies go native, each compared with CPython byte for byte.

Division: `/`, `//` and `%` by a variable are native when the exact-kind pass proves both operands
are int/bool/float (a str `%` formats and stays in CPython).  The typed clone computes CPython's
floor division and modulo for ints and floats and a correctly rounded int `/`; a zero divisor or an
int64 overflow (`INT64_MIN // -1`) abandons the native call and CPython re-runs it, so the exact
ZeroDivisionError (message included) or the big int is what the caller sees.

Local lists: a list the body creates and keeps to itself (only appended to, indexed, stored into,
measured, iterated without being changed in that loop, or aliased by another such local) may be
appended to; a reference never leaves the call, so no caller can see the difference.  Aliases
share the object as in CPython (`b = a; b.append(x)` changes `len(a)`).

Container parameters: `list[str]` (views of each element's UTF-8) and `bytes` (the object's own
buffer) are read in place; a non-exact list/str/bytes runs the original.  `ord` of one character
of a str is accepted.

`int(str)`: only a plain ASCII decimal (`-?[0-9]{1,18}`) is parsed natively; any other text makes
CPython re-run the call, so its value or ValueError is CPython's.

Field stores (opt-in, `AIL_HYBRID_FIELD_STORES=1`): a leaf method returning None that stores one
int field writes the final value back once, through the generic setattr, after the native body.
"""
import json
import os
import shutil
import subprocess
import sys
import sysconfig
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
CLI = str(ROOT / 'ail_chatgpt.py')
HAVE_CC = shutil.which(os.environ.get('PIPE_CC') or 'gcc') is not None
HAVE_HEADERS = (Path(sysconfig.get_paths().get('include', '/nonexistent')) / 'Python.h').is_file()
VECTORCALL = sys.version_info >= (3, 12)

DIVIDE = '''
def probe(table: list[int], keys: list[int], bits: int) -> int:
    hits = 0
    for k in keys:
        a = k % bits
        b = (k // 7 + 13) % bits
        if table[a] == 1 and table[b] == 1:
            hits += 1
    return hits


def mean(xs: list[float]) -> float:
    acc = 0.0
    for x in xs:
        acc += x
    return acc / len(xs)


def variance(xs: list[float]) -> float:
    m = mean(xs)
    acc = 0.0
    for x in xs:
        d = x - m
        acc += d * d
    return acc / len(xs)


def true_div(a: int, b: int) -> float:
    s = 0
    i = 0
    while i < 1:
        s += a
        i += 1
    return s / b


def floor_int(a: int, b: int) -> int:
    q = 0
    i = 0
    while i < 1:
        q += a // b
        i += 1
    return q


def mod_int(a: int, b: int) -> int:
    r = 0
    i = 0
    while i < 1:
        r += a % b
        i += 1
    return r


def floor_float(a: float, b: float) -> float:
    s = 0.0
    i = 0
    while i < 1:
        s += a // b
        i += 1
    return s


def mod_float(a: float, b: float) -> float:
    s = 0.0
    i = 0
    while i < 1:
        s += a % b
        i += 1
    return s


def mixed(a: int, b: float) -> float:
    return a / b + a // b + a % b


def aug(a: int, b: int) -> int:
    x = a
    x %= b
    x //= 1 + b
    return x


def scaled_total(vals: list[int], num: int, den: int) -> int:
    acc = 0
    for v in vals:
        acc += v * num // den
    return acc


def calls_div(a: int, b: int) -> int:
    t = 0
    i = 0
    while i < 3:
        t += floor_int(a + i, b)
        i += 1
    return t


def guarded(a: int, b: int) -> int:
    try:
        return floor_int(a, b)
    except ZeroDivisionError:
        return -1


def fmt(n: int) -> str:
    s = "%d"
    return s % n


def power(a: float, b: float) -> float:
    return a ** b


class Ratio:
    def __init__(self, num: int, den: int):
        self.num = num
        self.den = den

    def floor(self) -> int:
        t = 0
        i = 0
        while i < 2:
            t += self.num // self.den
            i += 1
        return t
'''

DIVIDE_RUNNER = r'''
import divide as m


def show(label, f, *args):
    try:
        r = f(*args)
        print(label, type(r).__name__, repr(r))
    except Exception as e:
        print(label, 'raised', type(e).__name__, str(e))


big = 2 ** 62 + 1
imin = -2 ** 63
show('probe', m.probe, [1, 0, 1, 1, 0, 1, 1], list(range(-50, 400, 3)), 7)
show('probe_neg', m.probe, [1, 0, 1, 1, 0, 1, 1], list(range(-50, 400, 3)), -7)
show('probe_zero', m.probe, [1, 0, 1], [1, 2, 3], 0)
show('probe_big', m.probe, [1, 0, 1], [1, 2, 3], 2 ** 64)
show('mean', m.mean, [1.5, 2.25, -3.0])
show('mean_empty', m.mean, [])
show('variance', m.variance, [1.5, 2.25, -3.0, 7.0])
show('variance_empty', m.variance, [])
for a, b in [(7, 2), (-7, 2), (7, -2), (-7, -2), (big, 3), (2 ** 53 + 1, 1), (big, big - 2),
             (imin, -1), (imin, 1), (1, 0), (0, 5), (True, True), (1, False), (10 ** 20, 3)]:
    show('true_div %r %r' % (a, b), m.true_div, a, b)
    show('floor_int %r %r' % (a, b), m.floor_int, a, b)
    show('mod_int %r %r' % (a, b), m.mod_int, a, b)
    show('aug %r %r' % (a, b), m.aug, a, b)
    show('calls_div %r %r' % (a, b), m.calls_div, a, b)
inf = float('inf')
nan = float('nan')
for a, b in [(7.5, 2.0), (-7.5, 2.0), (7.5, -2.0), (-0.0, 3.0), (0.0, -3.0), (1e308, 1e-308),
             (inf, 2.0), (2.0, inf), (-2.0, inf), (nan, 1.0), (1.0, 0.0), (-1.0, -0.0),
             (5e-324, 3.0), (0.1, 0.01)]:
    show('floor_float %r %r' % (a, b), m.floor_float, a, b)
    show('mod_float %r %r' % (a, b), m.mod_float, a, b)
for a, b in [(7, 2.0), (-7, 0.5), (big, 3.0), (1, 0.0), (3, -0.0)]:
    show('mixed %r %r' % (a, b), m.mixed, a, b)
show('scaled', m.scaled_total, list(range(-20, 30)), 3, 7)
show('scaled_neg', m.scaled_total, list(range(-20, 30)), 3, -7)
show('scaled_zero', m.scaled_total, list(range(-20, 30)), 3, 0)
show('scaled_ovf', m.scaled_total, [2 ** 62], 4, 3)
show('guarded', m.guarded, 5, 2)
show('guarded_zero', m.guarded, 5, 0)
show('fmt', m.fmt, 5)
show('power', m.power, -8.0, 1.0 / 3.0)
r = m.Ratio(17, 5)
show('ratio', r.floor)
r.den = 0
show('ratio_zero', r.floor)
r.den = -4
show('ratio_neg', r.floor)
r.num = imin
r.den = -1
show('ratio_ovf', r.floor)
for _ in range(2000):
    m.floor_int(9, 4)
    m.mod_float(9.0, 4.0)
print('loops-ok')
'''

DIVIDE_NATIVE = ('probe', 'mean', 'variance', 'true_div', 'floor_int', 'mod_int', 'floor_float',
                 'mod_float', 'mixed', 'aug', 'scaled_total', 'calls_div', 'Ratio.floor')
DIVIDE_REFUSED = ('fmt', 'power', 'guarded')


LISTS = '''
def levenshtein(a: str, b: str) -> int:
    n = len(a)
    m = len(b)
    if n == 0:
        return m
    if m == 0:
        return n
    prev = []
    i = 0
    while i <= m:
        prev.append(i)
        i += 1
    j = 1
    while j <= n:
        cur = [j]
        k = 1
        while k <= m:
            if a[j - 1] == b[k - 1]:
                cur.append(prev[k - 1])
            else:
                best = prev[k]
                if prev[k - 1] < best:
                    best = prev[k - 1]
                if cur[k - 1] < best:
                    best = cur[k - 1]
                cur.append(best + 1)
            k += 1
        prev = cur
        j += 1
    return prev[m]


def alias_append(n: int) -> int:
    a = [1]
    b = a
    i = 0
    while i < n:
        b.append(i)
        i += 1
    return len(a) * 100 + a[len(a) - 1]


def alias_store(n: int) -> int:
    a = [0] * 3
    b = a
    b[0] = n
    b[1] += n
    return a[0] + a[1]


def running(xs: list[float]) -> float:
    sums = []
    acc = 0.0
    for x in xs:
        acc += x
        sums.append(acc)
    t = 0.0
    for s in sums:
        t += s
    return t


def prefix(xs: list[int]) -> list[int]:
    tmp = []
    out = []
    for x in xs:
        tmp.append(x * 2)
        out.append(len(tmp) + tmp[len(tmp) - 1])
    return out


def pick(n: int) -> int:
    vals = [10, 20]
    vals.append(n)
    return vals[n]


def grow_while_iter(n: int) -> int:
    vals = [1, 2]
    for v in vals:
        if len(vals) < n:
            vals.append(v)
    return len(vals)


def bools(n: int) -> int:
    flags = [True]
    flags.append(n > 0)
    return len(flags)


def escapes(n: int) -> int:
    vals = [n]
    vals.append(n)
    return sum(vals)
'''

LISTS_RUNNER = r'''
import lists as m


def show(label, f, *args):
    try:
        r = f(*args)
        print(label, type(r).__name__, repr(r))
    except Exception as e:
        print(label, 'raised', type(e).__name__, str(e))


for a, b in [('kitten', 'sitting'), ('', 'abc'), ('abc', ''), ('flaw', 'lawn'),
             ('abcdefghijklmnopqrstuvwxyz', 'bacdefghijklmnopqrstuvwxzz'), ('東京', '東')]:
    show('lev %r %r' % (a, b), m.levenshtein, a, b)
show('lev_bad', m.levenshtein, b'abc', 'abc')
for n in (0, 1, 5, 2 ** 40, 2 ** 70):
    show('alias_append %r' % n, m.alias_append, min(n, 50))
    show('alias_store %r' % n, m.alias_store, n)
show('alias_store_ovf', m.alias_store, 2 ** 62)
show('running', m.running, [0.5, 1.25, -3.0])
show('running_empty', m.running, [])
show('prefix', m.prefix, [3, -1, 2 ** 40])
show('prefix_big', m.prefix, [2 ** 62])
for n in (0, 1, 2, 3, -1, -3, -4):
    show('pick %r' % n, m.pick, n)
show('grow', m.grow_while_iter, 6)
show('bools', m.bools, 3)
show('escapes', m.escapes, 4)
for _ in range(2000):
    m.levenshtein('abc', 'abd')
print('loops-ok')
'''

# (`alias_store` is refused by pymix itself, before the hybrid sees it; it is compared anyway.)
LISTS_NATIVE = ('levenshtein', 'alias_append', 'running', 'prefix', 'pick')
LISTS_REFUSED = ('grow_while_iter', 'bools', 'escapes')


VIEWS = '''
def count_terms(words: list[str], vocab_size: int) -> list[int]:
    counts = [0] * vocab_size
    for w in words:
        idx = 0
        h = 0
        for ch in w:
            h = (h * 31 + ord(ch)) % vocab_size
            idx = h
        counts[idx] += 1
    return counts


def total_len(words: list[str]) -> int:
    n = 0
    for w in words:
        n += len(w)
    return n


def first_chars(words: list[str]) -> int:
    t = 0
    i = 0
    while i < len(words):
        t += ord(words[i][0])
        i += 1
    return t


def fnv1a(data: bytes) -> int:
    h = 2166136261
    for byte in data:
        h ^= byte
        h = (h * 16777619) & 0xFFFFFFFF
    return h


def adler(data: bytes) -> int:
    a = 1
    b = 0
    for byte in data:
        a = (a + byte) % 65521
        b = (b + a) % 65521
    return (b << 16) | a


def at(data: bytes, i: int) -> int:
    t = 0
    k = 0
    while k < 2:
        t += data[i]
        k += 1
    return t


def djb2(text: str) -> int:
    h = 5381
    for ch in text:
        h = ((h * 33) + ord(ch)) & 0x7FFFFFFF
    return h


def ord_param(c: str) -> int:
    return ord(c)
'''

VIEWS_RUNNER = r'''
import views as m


def show(label, f, *args):
    try:
        r = f(*args)
        print(label, type(r).__name__, repr(r))
    except Exception as e:
        print(label, 'raised', type(e).__name__, str(e))


class S(str):
    pass


class L(list):
    pass


words = ['alpha', 'beta', '東京', '', 'x' * 40, 'café', '\U0001f600!']
show('count', m.count_terms, words, 26)
show('count_empty', m.count_terms, [], 5)
show('count_zero', m.count_terms, words, 0)
show('count_bad', m.count_terms, ['a', 3], 26)
show('count_sub', m.count_terms, ['a', S('bc')], 26)
show('count_listsub', m.count_terms, L(['a', 'b']), 26)
show('count_tuple', m.count_terms, ('a', 'b'), 26)
show('total_len', m.total_len, words)
show('first_chars', m.first_chars, words[:3])
show('first_chars_empty_word', m.first_chars, ['a', ''])
data = bytes((i * 37 + 11) % 256 for i in range(3000))
show('fnv1a', m.fnv1a, data)
show('fnv1a_empty', m.fnv1a, b'')
show('fnv1a_bytearray', m.fnv1a, bytearray(data[:10]))
show('fnv1a_memoryview', m.fnv1a, memoryview(data[:10]))
show('fnv1a_list', m.fnv1a, [1, 2, 3])
show('adler', m.adler, data)
for i in (0, 5, -1, -3000, 2999, 3000, -3001, 2 ** 70):
    show('at %r' % i, m.at, data, i)
show('djb2', m.djb2, 'the quick brown fox 東京 \U0001f600')
show('djb2_empty', m.djb2, '')
show('ord_param', m.ord_param, 'ab')
words2 = ['w%d' % i for i in range(5000)]
for _ in range(300):
    m.count_terms(words2[:50], 7)
    m.fnv1a(data[:100])
print('loops-ok')
'''

VIEWS_NATIVE = ('count_terms', 'total_len', 'first_chars', 'fnv1a', 'adler', 'at', 'djb2')
VIEWS_REFUSED = ('ord_param',)


STRINT = '''
COMMA = ","


def sum_column(text: str, col: int) -> int:
    total = 0
    count = 0
    body = ""
    n = len(text)
    i = 0
    while i < n:
        ch = text[i]
        if ch == "\\n":
            if body != "":
                total += int(body)
            body = ""
            count = 0
        elif ch == COMMA:
            if count == col and body != "":
                total += int(body)
            count += 1
            body = ""
        elif count == col:
            body += ch
        i += 1
    if body != "":
        total += int(body)
    return total


def twice(s: str) -> int:
    t = 0
    k = 0
    while k < 2:
        t += int(s)
        k += 1
    return t


def caught(s: str) -> int:
    try:
        return twice(s)
    except ValueError:
        return -1
'''

STRINT_RUNNER = r'''
import strint as m


def show(label, f, *args):
    try:
        r = f(*args)
        print(label, type(r).__name__, repr(r))
    except Exception as e:
        print(label, 'raised', type(e).__name__, str(e))


rows = '\n'.join('%d,%d,x%d' % (i, i * 7 - 300, i) for i in range(200))
show('sum0', m.sum_column, rows, 0)
show('sum1', m.sum_column, rows, 1)
show('sum2', m.sum_column, rows, 2)
show('sum_ws', m.sum_column, '1, 2\n3,4', 1)
show('sum_big', m.sum_column, '1,99999999999999999999\n2,3', 1)
for s in ['12', '-7', '007', '-0', '0', ' 12', '12 ', '+5', '1_000', '١٢', '', 'abc',
          '12a', '9' * 18, '-' + '9' * 18, '9' * 19, '-9223372036854775808', '9' * 30, '\t3\n',
          '0x10', '−5', '²', '-', '--1', '1e3', ' 7', '4 ', '1__0', '_1']:
    show('twice %r' % s, m.twice, s)
    show('caught %r' % s, m.caught, s)
for _ in range(2000):
    m.twice('123')
print('loops-ok')
'''

STRINT_NATIVE = ('sum_column', 'twice')
STRINT_REFUSED = ('caught',)


STORES = '''
class Parser:
    def __init__(self, text: str) -> None:
        self.text = text
        self.pos = 0

    def skip_ws(self) -> None:
        n = len(self.text)
        while self.pos < n and self.text[self.pos] in " \\t\\n\\r":
            self.pos += 1

    def skip_to(self, ch: str) -> None:
        n = len(self.text)
        while self.pos < n:
            if self.text[self.pos] == ch:
                return
            self.pos += 1

    def bump_then_peek(self) -> None:
        k = 0
        while k < 2:
            self.pos += 1
            k += 1
        if self.text[self.pos] == "x":
            self.pos = 0

    def peek(self) -> int:
        n = 0
        i = self.pos
        while i < len(self.text) and self.text[i] == " ":
            n += 1
            i += 1
        return n

    def ws_then_peek(self) -> int:
        self.skip_ws()
        return self.peek()
'''

STORES_RUNNER = r'''
import stores as m


def show(label, f, *args):
    try:
        r = f(*args)
        print(label, type(r).__name__, repr(r))
    except Exception as e:
        print(label, 'raised', type(e).__name__, str(e))


def state(label, p):
    print(label, type(p.pos).__name__, repr(p.pos), sorted(vars(p)))


p = m.Parser('   \t\n abc  d')
show('skip', p.skip_ws)
state('after', p)
show('skip_again', p.skip_ws)
state('again', p)
p.pos = 9
show('skip_to', p.skip_to, 'd')
state('to', p)
show('skip_to_missing', p.skip_to, 'q')
state('missing', p)
q = m.Parser('ab')
show('bump_raise', q.bump_then_peek)
state('bump_raise', q)
q = m.Parser('abx')
show('bump', q.bump_then_peek)
state('bump', q)
r = m.Parser('    z')
show('ws_then_peek', r.ws_then_peek)
state('wtp', r)
for start in (True, 1.0, 2 ** 70, -1, 2 ** 63 - 1):
    s = m.Parser('   x')
    s.pos = start
    show('start %r' % (start,), s.skip_ws)
    state('start %r' % (start,), s)
s = m.Parser('   x')
del s.pos
show('no_pos', s.skip_ws)
s = m.Parser('   x')
s.text = 5
show('bad_text', s.skip_ws)
state('bad_text', s)


class Loud(m.Parser):
    def __setattr__(self, k, v):
        print('set', k, v)
        object.__setattr__(self, k, v)


l = Loud('  x')
show('loud', l.skip_ws)
log = []
def tracer(self, k, v):
    log.append((k, v))
    object.__setattr__(self, k, v)
m.Parser.__setattr__ = tracer
t = m.Parser('   x')
show('traced', t.skip_ws)
print('log', log)
del m.Parser.__setattr__
def pset(self, v):
    log.append(('prop', v))
    self.__dict__['_p'] = v
m.Parser.pos = property(lambda self: self.__dict__.get('_p', 0), pset)
u = m.Parser.__new__(m.Parser)
u.text = '    x'
show('prop', u.skip_ws)
print('log2', log)
del m.Parser.pos
w = m.Parser(' ' * 1000 + 'x')
for _ in range(2000):
    w.pos = 0
    w.skip_ws()
state('loop', w)
print('loops-ok')
'''

STORES_NATIVE = ('Parser.skip_ws', 'Parser.skip_to', 'Parser.bump_then_peek', 'Parser.peek')
STORES_REFUSED = ('Parser.ws_then_peek',)


def run(cmd, cwd=None, env=None):
    return subprocess.run(cmd, cwd=cwd, env=env, capture_output=True, timeout=600)


@unittest.skipUnless(HAVE_CC and HAVE_HEADERS, 'needs a C compiler and the CPython headers')
class Runs(unittest.TestCase):

    def build(self, tmp, name, text, out_name='out', **env):
        src = Path(tmp) / (name + '.py')
        src.write_text(text, encoding='utf-8')
        out = Path(tmp) / out_name
        built = run([sys.executable, '-B', CLI, 'build', '--cpython', str(src), '-o', str(out)],
                    tmp, env=dict(os.environ, AIL_NO_CACHE='1', **env))
        self.assertEqual(built.returncode, 0, built.stderr[-3000:])
        return out, json.loads((out / 'build.json').read_text(encoding='utf-8'))

    def compare(self, tmp, out, runner_text, native, refused, report, module):
        for name in native:
            self.assertIn(name, report['accelerated'], report['rejected'].get(name))
        for name in refused:
            self.assertNotIn(name, report['accelerated'])
        runner = Path(tmp) / 'runner.py'
        runner.write_text(runner_text, encoding='utf-8')
        want = run([sys.executable, str(runner)], tmp, env=dict(os.environ, PYTHONPATH=tmp))
        got = run([sys.executable, str(runner)], tmp, env=dict(os.environ, PYTHONPATH=str(out)))
        self.assertEqual(want.returncode, 0, want.stderr[-2000:])
        self.assertEqual(got.stdout.decode(), want.stdout.decode(), got.stderr[-2000:])
        self.assertEqual(got.returncode, want.returncode)
        self.assertIn(b'loops-ok', got.stdout)
        if VECTORCALL:
            probe = ('import %s as m\nnat = m._ail_hybrid_native\n'
                     'def get(n):\n'
                     '    o = m\n'
                     '    for p in n.split("."):\n'
                     '        o = getattr(o, p)\n'
                     '    return o\n'
                     'print([nat._ail_is_native(get(n)) for n in %r])\n' % (module, native))
            got = run([sys.executable, '-B', '-c', probe], str(out),
                      env=dict(os.environ, PYTHONPATH=str(out)))
            self.assertEqual(got.stdout.strip(), repr([True] * len(native)).encode(),
                             got.stderr[-2000:])

    def test_division_matches_cpython(self):
        with tempfile.TemporaryDirectory(prefix='ail-hybrid-obs5-div-') as tmp:
            out, report = self.build(tmp, 'divide', DIVIDE)
            self.compare(tmp, out, DIVIDE_RUNNER, DIVIDE_NATIVE, DIVIDE_REFUSED, report, 'divide')

    def test_local_lists_match_cpython(self):
        with tempfile.TemporaryDirectory(prefix='ail-hybrid-obs5-lists-') as tmp:
            out, report = self.build(tmp, 'lists', LISTS)
            self.compare(tmp, out, LISTS_RUNNER, LISTS_NATIVE, LISTS_REFUSED, report, 'lists')

    def test_str_list_and_bytes_parameters_match_cpython(self):
        with tempfile.TemporaryDirectory(prefix='ail-hybrid-obs5-views-') as tmp:
            out, report = self.build(tmp, 'views', VIEWS)
            self.compare(tmp, out, VIEWS_RUNNER, VIEWS_NATIVE, VIEWS_REFUSED, report, 'views')

    def test_int_of_str_matches_cpython(self):
        with tempfile.TemporaryDirectory(prefix='ail-hybrid-obs5-strint-') as tmp:
            out, report = self.build(tmp, 'strint', STRINT)
            self.compare(tmp, out, STRINT_RUNNER, STRINT_NATIVE, STRINT_REFUSED, report, 'strint')

    def test_methods_storing_an_int_field_match_cpython(self):
        with tempfile.TemporaryDirectory(prefix='ail-hybrid-obs5-stores-') as tmp:
            # opt-in (measured slower on json_parse); off by default
            _off, plain = self.build(tmp, 'stores', STORES, 'out-default')
            self.assertNotIn('Parser.skip_ws', plain['accelerated'])
            self.assertIn('opt-in', plain['rejected']['Parser.skip_ws'])
            out, report = self.build(tmp, 'stores', STORES, AIL_HYBRID_FIELD_STORES='1')
            self.compare(tmp, out, STORES_RUNNER, STORES_NATIVE, STORES_REFUSED, report, 'stores')


if __name__ == '__main__':
    unittest.main()

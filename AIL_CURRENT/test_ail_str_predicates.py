"""str is*() predicates, find/rfind/index/rindex/count/startswith/endswith with start and end, and
split/rsplit with sep and maxsplit match CPython.

One AIL program reads test lines (every text is passed as hex of its UTF-8, so any code point,
newline and NUL included, can be a receiver) and prints one result per line:

- every code point (surrogates excluded) is tested alone for all nine predicates, then random
  strings built from cased, titlecase, digit, numeric, space and combining characters test the
  multi-character rules of isupper/islower/istitle;
- random find/rfind/index/rindex/count/startswith/endswith calls with start and end that are
  negative, zero, past the end, huge or omitted (None), on ASCII and non-ASCII text;
- random split/rsplit calls with and without sep, maxsplit (positional and keyword), None, and
  empty separators (ValueError).
"""
import random
import subprocess
import unittest
import test_ail_c_objects as support
from test_ail_map_fields import build

PREDICATES = ('isalpha', 'isalnum', 'isdigit', 'isdecimal', 'isnumeric', 'isspace', 'isupper',
              'islower', 'istitle')
SEARCH = ('find', 'rfind', 'index', 'rindex', 'count', 'startswith', 'endswith')
# (positional arguments after sub, as source text)
SEARCH_SHAPES = ('', ', lo', ', lo, hi', ', None, hi', ', lo, None', ', None, None')
SPLIT_SHAPES = ('', 'sep', 'sep, n', 'None, n', 'maxsplit=n', 'sep=sep', 'sep=sep, maxsplit=n',
                'None', 'sep, maxsplit=n')


def source():
    funcs = []
    branches = []
    for method in SEARCH:
        for shape, args in enumerate(SEARCH_SHAPES):
            name = 'm_%s_%d' % (method, shape)
            if method in ('index', 'rindex'):
                body = ('let r = -2; try { r = s.%s(sub%s); } except ValueError { r = -2; } '
                        'return str(r);' % (method, args))
            else:
                body = 'return str(s.%s(sub%s));' % (method, args)
            funcs.append('fn %s(s: str, sub: str, lo: int, hi: int) -> str { %s }' % (name, body))
            branches.append('elif op == "%s:%d" { out.append(%s(unhex(f[1]), unhex(f[2]), int(f[3]), int(f[4]))); }'
                            % (method, shape, name))
    for method in ('split', 'rsplit'):
        for shape, args in enumerate(SPLIT_SHAPES):
            name = 's_%s_%d' % (method, shape)
            funcs.append('fn %s(s: str, sep: str, n: int) -> str { let r = "VE"; '
                         'try { let p = s.%s(%s); r = enc(p); } except ValueError { r = "VE"; } return r; }'
                         % (name, method, args))
            branches.append('elif op == "%s:%d" { out.append(%s(unhex(f[1]), unhex(f[2]), int(f[3]))); }'
                            % (method, shape, name))
    return r'''fn bit(x: int) -> str { if x { return "1"; } return "0"; }
fn unhex(h: str) -> str { return bytes.fromhex(h).decode("utf-8"); }
fn enc(parts: list[str]) -> str {
    let hs: list[str] = [];
    for p in parts { hs.append(p.encode().hex()); }
    return str(len(parts)) + ":" + ",".join(hs);
}
fn preds(t: str) -> str {
    return bit(t.isalpha()) + bit(t.isalnum()) + bit(t.isdigit()) + bit(t.isdecimal())
        + bit(t.isnumeric()) + bit(t.isspace()) + bit(t.isupper()) + bit(t.islower()) + bit(t.istitle());
}
''' + '\n'.join(funcs) + r'''
fn main() -> int {
    let text: str = read_bytes(sys.argv[1]).decode("utf-8");
    let out: list[str] = [];
    for line in text.split("\n") {
        let f = line.split("\t");
        let op = f[0];
        if op == "pred" { out.append(preds(unhex(f[1]))); }
        ''' + '\n        '.join(branches) + r'''
        else { out.append("BAD OP"); }
    }
    write_stdout_bytes("\n".join(out).encode("utf-8"));
    return 0;
}'''


def pred_bits(t):
    return ''.join('1' if getattr(t, p)() else '0' for p in PREDICATES)


def search_call(method, s, sub, shape, lo, hi):
    args = {0: (), 1: (lo,), 2: (lo, hi), 3: (None, hi), 4: (lo, None), 5: (None, None)}[shape]
    try:
        r = getattr(s, method)(sub, *args)
    except ValueError:
        return '-2'
    return str(r)


def split_call(method, s, sep, n, shape):
    call = getattr(s, method)
    try:
        r = [lambda: call(), lambda: call(sep), lambda: call(sep, n), lambda: call(None, n),
             lambda: call(maxsplit=n), lambda: call(sep=sep), lambda: call(sep=sep, maxsplit=n),
             lambda: call(None), lambda: call(sep, maxsplit=n)][shape]()
    except ValueError:
        return 'VE'
    return '%d:%s' % (len(r), ','.join(p.encode('utf-8').hex() for p in r))


PIECES = ['a', 'b', 'aa', 'A', 'Z', 'x', '1', '7', ' ', '  ', '\t', '\n', ',', ', ', '=', 'é', 'É', 'ö',
          'ß', 'İ', 'Σ', 'σ', 'ς', 'ǅ', 'ǆ', 'Ǆ', 'ᾈ', '日', '本', '\U0001f600', '\U00010400',
          '\U00010428', ' ', ' ', '\x85', '　', ' ', '٣', '²', '½', 'Ⅷ', 'ʰ',
          '́', 'ͅ', 'ª', 'ǂ', '௱', '\U0001d7ce']
ASCII_PIECES = ['a', 'b', 'aa', 'ab', 'A', 'Z', 'x', '1', '7', ' ', '  ', '\t', '\n', ',', ', ', '=']
SEPS = [',', ', ', 'aa', 'a', 'é', ' ', '日', 'ab', '=', 'aaa', ' ', '\n', '\U0001f600', 'bé']


def random_text(rng, ascii_only=False):
    pieces = ASCII_PIECES if ascii_only else PIECES
    return ''.join(rng.choice(pieces) for _ in range(rng.randrange(0, 14)))


def random_index(rng, size):
    kind = rng.randrange(10)
    if kind == 0:
        return rng.choice([0, 1, -1, size, -size, size + 1, -size - 1])
    if kind == 1:
        return rng.choice([2 ** 62, -2 ** 62, 2 ** 63 - 1, -2 ** 63 + 1, 10 ** 9, -10 ** 9])
    return rng.randrange(-size - 3, size + 4)


def random_sub(rng, s, ascii_only):
    kind = rng.randrange(8)
    if kind in (0, 6, 7) and s:
        i = rng.randrange(len(s))
        return s[i:i + rng.randrange(0, 4)]
    if kind == 1:
        return ''
    return random_text(rng, ascii_only)[:rng.randrange(0, 4)] if kind < 5 else rng.choice(SEPS)


def hexed(s):
    return s.encode('utf-8').hex()


class StrPredicateTests(unittest.TestCase):
    setUp = support.CObjectTests.setUp
    write = support.CObjectTests.write
    command = support.CObjectTests.command

    def run_lines(self, program, lines):
        path = self.root / 'cases.txt'
        path.write_bytes('\n'.join(lines).encode('utf-8'))
        result = subprocess.run([str(program), str(path)], capture_output=True, timeout=900)
        self.assertEqual(result.returncode, 0, result.stderr.decode(errors='replace'))
        got = result.stdout.decode('utf-8').split('\n')
        self.assertEqual(len(got), len(lines))
        return got

    def compare(self, program, cases):
        """cases: [(line, expected)]"""
        got = self.run_lines(program, [line for line, _ in cases])
        bad = [(cases[i][0], got[i], cases[i][1]) for i in range(len(cases)) if got[i] != cases[i][1]]
        self.assertFalse(bad, 'program, expected: %r' % bad[:8])

    def test_matches_cpython(self):
        program = build(self, 'str_predicates', source())
        rng = random.Random(20261012)

        # (a) every code point, then multi-character predicate rules
        singles = [chr(cp) for cp in range(0x110000) if not 0xD800 <= cp <= 0xDFFF]
        self.compare(program, [('pred\t' + hexed(c), pred_bits(c)) for c in singles])
        texts = ['', 'A', 'a', 'Ab', 'aB', 'AB', 'Ab Cd', 'Ab cd', 'ab Cd', "They're Bill's", 'ǅ', 'ǅa', 'aǅ',
                 'ǄǄ', 'ǅǅ', 'ΑΣ', '١٢٣', '123', '12a', '²', '½', 'Ⅷ', ' \t\n', '\x85 ']
        texts += [''.join(rng.choice(PIECES) for _ in range(rng.randrange(1, 9))) for _ in range(30000)]
        self.compare(program, [('pred\t' + hexed(t), pred_bits(t)) for t in texts])

        # (b) windowed search
        cases = []
        for _ in range(40000):
            ascii_only = rng.randrange(3) == 0
            s = random_text(rng, ascii_only)
            sub = random_sub(rng, s, ascii_only)
            method, shape = rng.choice(SEARCH), rng.randrange(len(SEARCH_SHAPES))
            lo, hi = random_index(rng, len(s)), random_index(rng, len(s))
            cases.append(('%s:%d\t%s\t%s\t%d\t%d' % (method, shape, hexed(s), hexed(sub), lo, hi),
                          search_call(method, s, sub, shape, lo, hi)))
        self.compare(program, cases)

        # (c) split / rsplit
        cases = []
        for _ in range(40000):
            ascii_only = rng.randrange(3) == 0
            s = random_text(rng, ascii_only)
            sep = '' if rng.randrange(25) == 0 else rng.choice(SEPS + [random_sub(rng, s, ascii_only)])
            n = rng.choice([-1, -3, 0, 1, 2, 3, 5, 100, 2 ** 62])
            method, shape = rng.choice(('split', 'rsplit')), rng.randrange(len(SPLIT_SHAPES))
            cases.append(('%s:%d\t%s\t%s\t%d' % (method, shape, hexed(s), hexed(sep), n),
                          split_call(method, s, sep, n, shape)))
        # whitespace splitting with maxsplit on texts that start/end with (Unicode) whitespace
        for _ in range(20000):
            s = ''.join(rng.choice([' ', '\t', ' ', ' ', '\x85', 'a', 'é', 'bc', '日', '\n'])
                        for _ in range(rng.randrange(0, 12)))
            n = rng.randrange(-1, 6)
            for method in ('split', 'rsplit'):
                cases.append(('%s:3\t%s\t%s\t%d' % (method, hexed(s), '', n), split_call(method, s, '', n, 3)))
        self.compare(program, cases)


if __name__ == '__main__':
    unittest.main()

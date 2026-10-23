"""fuzz64: Counter.__eq__ treats a missing key as a count of zero.

CPython compares Counters with `self[e] == c` / `other[e] == c`, where a missing key reads
as 0, so `Counter({"a": 1}) == Counter({"a": 1, "z": 0})` is True.  The general runtime
compared the two dicts exactly (same keys) and printed False.  The typed path already used
the zero-aware helper.  Each program below is built twice (default build and
AIL_UNIFIED_FORCE=1 general path) and must print what CPython prints.
"""
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent

COUNTER_EQ = r'''from collections import Counter

class Box:
    pass

def same(x, y):
    return x == y

def main() -> int:
    empty = Counter()
    zero = Counter()
    zero["k"] += 0
    print(empty == zero, zero == empty, empty != zero)
    neg = Counter()
    neg["k"] -= 3
    print(neg == empty, empty == neg, neg != empty)
    other = Counter()
    other["k"] -= 3
    print(neg == other, other == neg)
    other["k"] -= 1
    print(neg == other, neg != other)
    big = Counter()
    big["k"] = 9223372036854775807
    big2 = Counter()
    big2["k"] = 9223372036854775807
    print(big == big2)
    big2["k"] -= 1
    print(big == big2, big != big2)
    a = Counter(["a", "a", "b"])
    b = Counter()
    for x in ["a", "a", "b"]:
        b[x] += 1
    b["gone"] += 0
    print(a == b, same(a, b))
    box = [a, b]
    table = {"a": a, "b": b}
    print(box[0] == box[1], table["a"] == table["b"], same(table["a"], table["b"]))
    p = Box()
    q = Box()
    p.c = zero
    q.c = empty
    print(p.c == q.c, q.c == p.c)
    alias = a
    print(alias == b)
    alias["z"] += 0
    print(a == b, alias == b)
    alias["z"] += 1
    print(a == b, a != b)
    return 0

main()
'''

COUNTER_EQ_TYPED = r'''from collections import Counter

def same(x: Counter[str], y: Counter[str]) -> bool:
    return x == y

def main() -> int:
    a: Counter[str] = Counter(["a", "a", "b"])
    b: Counter[str] = Counter(["a", "a", "b"])
    b["gone"] += 0
    print(a == b, same(a, b), a != b)
    c: Counter[str] = Counter()
    d: Counter[str] = Counter()
    d["k"] += 0
    print(c == d, d == c, c != d)
    d["k"] -= 2
    print(c == d, c != d)
    e: Counter[str] = Counter()
    e["k"] -= 2
    print(d == e)
    big: Counter[str] = Counter()
    big["k"] = 9223372036854775807
    big2: Counter[str] = Counter()
    big2["k"] = 9223372036854775807
    print(big == big2)
    big2["k"] -= 1
    print(big == big2, big != big2)
    return 0

main()
'''


COUNTER_EQ_NAN = r'''from collections import Counter

def main() -> int:
    nan = float('nan')
    a = Counter()
    a["k"] = nan
    b = Counter()
    b["k"] = nan
    b["z"] = 0
    print(a == b, b == a, a != b, b != a)
    c = Counter()
    c["k"] = float('nan')
    print(a == c, c == a, a != c, c != a)
    d = Counter()
    d["k"] = 1
    d["z"] = 0
    e = Counter()
    e["k"] = 1
    print(d == e, e == d, d != e)
    return 0

main()
'''


def _cpython(directory, name, text):
    src = Path(directory) / (name + '_cpython.py')
    src.write_text(text, encoding='utf-8')
    done = subprocess.run([sys.executable, '-B', str(src)], capture_output=True, timeout=120,
                          env=dict(os.environ, PYTHONUTF8='1'))
    return done.stdout.replace(b'\r\n', b'\n'), done.returncode, done.stderr


def _build_and_run(directory, name, text, general):
    src = Path(directory) / (name + '.ail')
    src.write_text(text, encoding='utf-8')
    exe = Path(directory) / ('exe_' + name + ('_g' if general else '_d'))
    env = dict(os.environ, AIL_NO_CACHE='1', AIL_QUIET_FALLBACK='1')
    env.pop('AIL_NO_GENERAL', None)
    if general:
        env['AIL_UNIFIED_FORCE'] = '1'
    else:
        env.pop('AIL_UNIFIED_FORCE', None)
    built = subprocess.run([sys.executable, '-B', str(ROOT / 'ail_chatgpt.py'), 'compile', src.name,
                            '--syntax', 'python', '-o', exe.name], cwd=directory,
                           capture_output=True, text=True, timeout=900, env=env)
    if built.returncode != 0:
        return None, (built.stdout + built.stderr)[-3000:]
    got = subprocess.run([str(exe)], capture_output=True, timeout=120, cwd=directory)
    return (got.stdout.replace(b'\r\n', b'\n'), got.returncode), got.stderr.decode('utf-8', 'replace')[-1500:]


class Fuzz64Tests(unittest.TestCase):
    def check(self, slug, text):
        with tempfile.TemporaryDirectory(prefix='ail-fuzz64-') as directory:
            want, rc, err = _cpython(directory, slug, text)
            self.assertEqual(rc, 0, err)
            for general in (True, False):
                got, build_err = _build_and_run(directory, '%s_%s' % (slug, 'g' if general else 'd'), text, general)
                self.assertIsNotNone(got, '%s (general=%s)\n%s' % (text[:2000], general, build_err))
                self.assertEqual(got, (want, 0), '%s (general=%s)\n%s' % (text[:2000], general, build_err))

    def test_counter_eq_zero_counts(self):
        self.check('counter_eq', COUNTER_EQ)

    def test_counter_eq_zero_counts_typed(self):
        self.check('counter_eq_typed', COUNTER_EQ_TYPED)

    def test_counter_eq_nan_shared_count(self):
        self.check('counter_eq_nan', COUNTER_EQ_NAN)


if __name__ == '__main__':
    unittest.main()

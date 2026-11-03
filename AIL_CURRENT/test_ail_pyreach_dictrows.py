"""Python-syntax reach, s5: dicts of record lists and dicts of sets.

R1  `d[k] = [name, balance, open]` lowers to a key -> slot dict plus one typed list per
    position; a `get` alias and `d[k][i] += x` both change the stored row, and a bool position
    still prints `True` / `False`.
R2  `d.values()` keeps insertion order, so `sum(a[1] for a in d.values() if a[2])` is exact.
R3  `sorted(d.items(), key=lambda kv: (-kv[1][1], kv[0]))` and
    `for k, (a, b, s) in d.items()` read the record rows.
R4  a balance beyond int64 read from input is loud on the default build (OverflowError), and
    with `--exact-int` it is exact or refused by name -- never wrapped.
R5  an alias kept after `del d[k]` still points at the row (the field lists keep it alive).
R6  a one-argument `d.get(k)` whose result is tested with `is None` is still refused until s8.
"""
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent
CLI = ROOT / 'ail_chatgpt.py'
HAVE_CC = shutil.which('gcc') is not None


RECORD_ALIAS = '''def main():
    d = {}
    d[7] = ["alice", 100, True]
    d[9] = ["bob", 40, False]
    r = d.get(7)
    r[1] += 5
    d[9][1] += 2
    print(d[7][0], d[7][1], d[7][2])
    print(d[9][0], d[9][1], d[9][2])


main()
'''

VALUES_SUM = '''def main():
    d = {}
    d[1] = [10, 2, True]
    d[2] = [20, 3, False]
    d[3] = [30, 4, True]
    print(sum(a[1] for a in d.values() if a[2]))
    for a in d.values():
        print(a[0], a[2])


main()
'''

ITEMS_SORTED = '''def main():
    d = {}
    d[5] = ["a", 3, True]
    d[2] = ["b", 9, False]
    d[7] = ["c", 1, True]
    order = sorted(d.items(), key=lambda kv: (-kv[1][1], kv[0]))
    for key, row in order:
        print(key, row[0], row[1], row[2])
    for key, (name, bal, opn) in d.items():
        print(key, name, bal, opn)


main()
'''



BIG_BALANCE = '''import sys

def main():
    d = {}
    n = int(sys.argv[1])
    d[1] = ["big", n, True]
    print(d[1][1])
    print(d[1][1] + 1)


main()
'''

DEL_ALIAS = '''def main():
    d = {}
    d[1] = ["a", 1, True]
    r = d.get(1)
    del d[1]
    r[1] += 5
    print(r[0], r[1], r[2], len(d))


main()
'''

GET_WITHOUT_PROOF = '''def main():
    d = {}
    d[1] = [10, 20, 30]
    x = d.get(2)
    if x is None:
        print("missing")
    else:
        print(x[0])


main()
'''


def build_source(tmp, name, source, *flags):
    exe = Path(tmp) / name
    env = dict(os.environ, AIL_NO_GENERAL='1', AIL_NO_CACHE='1')
    env.pop('AIL_STRICT', None)
    result = subprocess.run([sys.executable, '-B', str(CLI), 'compile', str(source),
                             '--syntax', 'python', '--strict', *flags, '-o', str(exe)],
                            capture_output=True, text=True, timeout=600, env=env)
    return result, exe


def build_probe(tmp, name, source, unified):
    exe = Path(tmp) / (name + ('_unified' if unified else '_default'))
    env = dict(os.environ, AIL_NO_CACHE='1')
    env.pop('AIL_STRICT', None)
    env.pop('AIL_NO_GENERAL', None)
    if unified:
        env['AIL_UNIFIED_FORCE'] = '1'
    else:
        env.pop('AIL_UNIFIED_FORCE', None)
    result = subprocess.run([sys.executable, '-B', str(CLI), 'compile', str(source),
                             '--syntax', 'python', '-o', str(exe)],
                            capture_output=True, text=True, timeout=600, env=env)
    return result, exe


def run(exe, *args):
    return subprocess.run([str(exe), *args], capture_output=True, text=True, timeout=120)


@unittest.skipUnless(HAVE_CC, 'needs gcc')
class PyreachDictRows(unittest.TestCase):
    def _typed(self, name, text, expected, *args):
        with tempfile.TemporaryDirectory(prefix='ail-s5-') as tmp:
            source = Path(tmp) / (name + '.py')
            source.write_text(text, encoding='utf8')
            reference = subprocess.run([sys.executable, str(source), *args], capture_output=True,
                                       text=True, timeout=120)
            self.assertEqual(reference.stdout, expected, name)
            result, exe = build_source(tmp, name, source)
            self.assertEqual(result.returncode, 0, (name, result.stderr[-3000:]))
            got = run(exe, *args)
            self.assertEqual(got.returncode, reference.returncode, name)
            self.assertEqual(got.stdout, expected, name)

    def _both(self, name, text, expected, *args):
        with tempfile.TemporaryDirectory(prefix='ail-s5-') as tmp:
            source = Path(tmp) / (name + '.py')
            source.write_text(text, encoding='utf8')
            for unified in (False, True):
                result, exe = build_probe(tmp, name, source, unified)
                self.assertEqual(result.returncode, 0, (name, unified, result.stderr[-3000:]))
                got = run(exe, *args)
                self.assertEqual(got.stdout, expected, (name, unified))

    def test_record_alias_and_subscript_update(self):
        self._typed('record_alias', RECORD_ALIAS, 'alice 105 True\nbob 42 False\n')
        self._both('record_alias', RECORD_ALIAS, 'alice 105 True\nbob 42 False\n')

    def test_values_sum_in_insertion_order(self):
        self._typed('values_sum', VALUES_SUM, '6\n10 True\n20 False\n30 True\n')

    def test_items_sorted_and_tuple_unpack(self):
        self._typed('items_sorted', ITEMS_SORTED,
                    '2 b 9 False\n5 a 3 True\n7 c 1 True\n'
                    '5 a 3 True\n2 b 9 False\n7 c 1 True\n')

    def test_big_balance_is_loud_or_exact(self):
        huge = '9223372036854775808123'
        with tempfile.TemporaryDirectory(prefix='ail-s5-') as tmp:
            source = Path(tmp) / 'big_balance.py'
            source.write_text(BIG_BALANCE, encoding='utf8')
            reference = subprocess.run([sys.executable, str(source), huge], capture_output=True,
                                       text=True, timeout=120)
            self.assertEqual(reference.returncode, 0)
            result, exe = build_source(tmp, 'big_default', source)
            self.assertEqual(result.returncode, 0, result.stderr[-3000:])
            got = run(exe, huge)
            self.assertNotEqual(got.returncode, 0)
            self.assertIn('OverflowError', got.stderr)

            result, exe = build_source(tmp, 'big_exact', source, '--exact-int')
            if result.returncode == 0:
                got = run(exe, huge)
                self.assertEqual(got.returncode, reference.returncode)
                self.assertEqual(got.stdout, reference.stdout)
            else:
                self.assertIn('dict of containers', result.stderr)
                self.assertNotIn('wrapped', result.stderr)

    def test_alias_survives_del(self):
        self._typed('del_alias', DEL_ALIAS, 'a 6 True 0\n')
        self._both('del_alias', DEL_ALIAS, 'a 6 True 0\n')

    def test_one_argument_get_without_proof_still_refuses(self):
        with tempfile.TemporaryDirectory(prefix='ail-s5-') as tmp:
            source = Path(tmp) / 'get_without_proof.py'
            source.write_text(GET_WITHOUT_PROOF, encoding='utf8')
            result, _ = build_source(tmp, 'get_without_proof', source)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn('one argument', result.stderr)
            self.assertIn('Optional', result.stderr)


if __name__ == '__main__':
    unittest.main()

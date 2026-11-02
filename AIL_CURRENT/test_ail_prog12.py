"""The hot functions of the eight prog12 programs on the typed path, against CPython 3.12.

Batch prog12 fixes the variable-length tuple local found in `t338`:

- `last: tuple[int, ...] = ()`, assigned an `itertools.permutations` item and then only
  iterated or joined, kept the local tuple annotation and was refused by the tuple pass.
  An empty tuple local whose uses are all list-compatible is now typed as `list[int]`.
- The itertools tuple check follows a plain alias assignment (`last = perm`) so that its
  uses are checked as the same list, instead of treating the assignment itself as escape.

T1  `t338` takes the typed path (no "built on the general path" note)
T2  stdout and exit code equal CPython on the three task inputs
T3  boundaries: empty and non-empty permutation tuples, indexing/iteration/len/sum/sorted/
    any/all/join, an alias without a local annotation, and a float tuple local that must
    stay refused by name (CPython's `sum(())` is int 0, the typed `list[float]` sum is 0.0)
T4  unsafe tuple uses (print, equality, a slice) still run correctly through the general path
"""
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parent
HAVE_CC = shutil.which('gcc') is not None or shutil.which('cc') is not None

IT_ALIAS = '''import itertools


def main() -> None:
    total = 0
    for perm in itertools.permutations(range(1, 5)):
        alias = perm
        total += len(alias) + alias[0]
    print(total)


main()
'''

SAFE_PERM = '''import itertools


def run(m: int) -> None:
    count = 0
    last: tuple[int, ...] = ()
    for perm in itertools.permutations(range(1, m + 1)):
        count += 1
        last = perm
    total = 0
    for x in last:
        total += x
    print(count, len(last), total, sum(last), sorted(last), any(last), all(last), last[0], last[-1])
    print(" ".join(str(x) for x in last))


def main() -> None:
    for m in (1, 2, 3, 4, 6):
        run(m)


main()
'''

FLOAT_LOCAL = '''def main() -> None:
    xs: tuple[float, ...] = ()
    print(len(xs), sum(xs))


main()
'''

UNSAFE = '''import itertools


def main() -> None:
    for perm in itertools.permutations(range(1, 4)):
        last: tuple[int, ...] = ()
        last = perm
        print(last)
        print(last == (1, 2, 3))
        print(last[1:])


main()
'''


def compile_program(directory, text, name, typed_only=False):
    source, exe = Path(directory, name + '.py'), Path(directory, name + '_x')
    source.write_text(text, encoding='utf-8')
    env = dict(os.environ, AIL_NO_CACHE='1')
    for key in ('AIL_NO_GENERAL', 'AIL_UNIFIED_FORCE', 'AIL_QUIET_FALLBACK'):
        env.pop(key, None)
    if typed_only:
        env['AIL_NO_GENERAL'] = '1'
    res = subprocess.run([sys.executable, '-B', str(ROOT / 'ail_chatgpt.py'), 'compile', source.name,
                          '-o', exe.name], cwd=directory, capture_output=True, text=True, timeout=900, env=env)
    return res, exe, source


def typed(res):
    return 'built on the general path' not in res.stderr


@unittest.skipUnless(HAVE_CC, 'needs a C compiler')
class Prog12(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.mkdtemp(prefix='prog12_')

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp, ignore_errors=True)

    def build(self, text, name, expect_typed=True, typed_only=False):
        res, exe, source = compile_program(self.tmp, text, name, typed_only)
        self.assertEqual(res.returncode, 0, res.stderr[-1800:])
        if expect_typed is not None:
            self.assertEqual(typed(res), expect_typed, res.stderr[-900:])
        return exe, source

    def same(self, exe, source, stdin=''):
        want = subprocess.run([sys.executable, str(source)], input=stdin.encode('utf-8'),
                              capture_output=True, timeout=300)
        got = subprocess.run([str(exe)], input=stdin.encode('utf-8'), capture_output=True, timeout=300)
        self.assertEqual(got.stdout, want.stdout, repr(stdin))
        self.assertEqual(got.returncode, want.returncode, repr(stdin))

    def lab(self, *parts):
        return REPO.joinpath('lab', *parts)

    def test_t338_whole_program_typed(self):
        path = self.lab('census', 'programs', 'dev', 't338.py')
        if not path.exists():
            self.skipTest('lab census program is not in this tree')
        text = path.read_text(encoding='utf-8')
        exe, source = self.build(text, 't338', typed_only=True)
        for i in range(3):
            self.same(exe, source, self.lab('corpus', 'tasks', 't338', 'in%d.txt' % i).read_text())

    def test_itertools_tuple_local_typed(self):
        exe, source = self.build(SAFE_PERM, 'safe_perm', typed_only=True)
        self.same(exe, source)

    def test_itertools_tuple_alias_typed(self):
        exe, source = self.build(IT_ALIAS, 'it_alias', typed_only=True)
        self.same(exe, source)

    def test_float_tuple_local_stays_named(self):
        res, _, _ = compile_program(self.tmp, FLOAT_LOCAL, 'float_local', typed_only=True)
        self.assertEqual(res.returncode, 3, res.stdout + res.stderr)
        self.assertIn('tuple[float, ...]', res.stderr)
        exe, source = self.build(FLOAT_LOCAL, 'float_local_default', expect_typed=False)
        self.same(exe, source)

    def test_unsafe_tuple_uses_match_cpython(self):
        exe, source = self.build(UNSAFE, 'unsafe', expect_typed=False)
        self.same(exe, source)


if __name__ == '__main__':
    unittest.main()

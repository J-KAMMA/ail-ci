"""Real programs that use the CPython stdlib module `functools`, compared with CPython 3.12.

The programs are the nine in `lab/stdlib/functools/` that build (the other three are recorded in
`lab/stdlib/functools/RESULTS.md` as follow-ups).  Every program is ordinary Python: CPython runs it as the
oracle, and the compiled program prints the same bytes and exits with the same status.  Both the default
build and the unified (`AIL_UNIFIED_FORCE=1`) build are checked.  `REGRESSIONS` holds small programs for
the review findings: an unbounded `@cache`, default/keyword argument keys, a run-time `maxsize`, nested
unhashable arguments, `CacheInfo`'s type name, and `partialmethod` keyword vs positional binding.

Covered: functools.reduce (both forms, the empty TypeError), functools.partial (positional and keyword
binding, as a sort key and as a map function), functools.lru_cache / cache (cache_info / cache_clear,
maxsize, typed=True, the unhashable-argument TypeError, the lone int/str fast-path keys), a custom
@functools.total_ordering class, functools.cmp_to_key with a function and a lambda comparator in sorted /
list.sort / min / max, and functools.partialmethod with keyword-bound arguments.
"""
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent
LAB = ROOT.parent / 'lab' / 'stdlib' / 'functools'

PROGRAMS = (
    'reduce_orders',
    'partial_pipeline',
    'lru_fib',
    'cache_collatz',
    'lru_typed',
    'cmp_key',
    'total_order',
    'functools_errors',
    'partial_method',
)

REGRESSIONS = {
    'lru_review': '''\
from functools import cache, lru_cache

@cache
def sq(n):
    return n * n

for i in range(20000):
    sq(i)
i = sq.cache_info()
print(i.maxsize, i.currsize, i.misses, i.hits)
print(sq(0), sq(19999))
print(sq.cache_info().hits, sq.cache_info().misses, sq.cache_info().currsize)

@lru_cache(maxsize=8)
def f(n=1, m=2):
    return n * 10 + m

print(f())
print(f(1))
print(f(1, 2))
print(f(m=2))
print(f(n=1))
print(f(2, 2))
print(f.cache_info().hits, f.cache_info().misses, f.cache_info().currsize)

M = 2

@lru_cache(maxsize=M)
def g(n):
    return n

for x in range(5):
    g(x)
print(g.cache_info())
print(g(0))
print(g.cache_info().currsize)

@lru_cache(maxsize=4)
def k(x):
    return len(x)

for value in ((1, [2]), (1, {'a': 1}), (1, {2})):
    try:
        print(k(value))
    except TypeError as e:
        print("err", e)
print(k.cache_info().misses, k.cache_info().currsize)
print(type(f.cache_info()).__name__)
''',
    'partialmethod_review': '''\
from functools import partialmethod

class F:
    def render(self, value, precision=2, prefix=""):
        return "%s%.*f" % (prefix, precision, value)
    money = partialmethod(render, precision=2, prefix="$")
    plain = partialmethod(render, prefix="#")

f = F()
print(f.money(12.345))
try:
    print(f.money(12.345, 1))
except TypeError as e:
    print("err", e)
print(f.money(precision=1, value=2.5))
print(f.plain(2.5))
print(f.render(2.5, 3, "!"))
''',
}

MODES = (('default', None), ('unified', '1'))


def run_program(argv, cwd, timeout):
    return subprocess.run(argv, cwd=cwd, capture_output=True, text=True, timeout=timeout,
                          encoding='utf-8')


class StdFunctoolsTest(unittest.TestCase):
    def _check_source(self, name, source_text):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory, name + '.py')
            source.write_text(source_text, encoding='utf-8')
            oracle = run_program([sys.executable, str(source)], directory, 300)
            for label, force in MODES:
                exe = Path(directory, '%s_%s' % (name, label))
                env = dict(os.environ, AIL_NO_CACHE='1')
                for key in ('AIL_NO_GENERAL', 'AIL_GENERAL', 'AIL_UNIFIED_FORCE', 'AIL_STRICT'):
                    env.pop(key, None)
                if force is not None:
                    env['AIL_UNIFIED_FORCE'] = force
                built = subprocess.run(
                    [sys.executable, '-B', str(ROOT / 'ail_chatgpt.py'), 'compile', source.name,
                     '--syntax', 'python', '-o', exe.name],
                    cwd=directory, capture_output=True, text=True, timeout=900, env=env)
                self.assertEqual(
                    built.returncode, 0,
                    '%s (%s build) did not compile:\n%s\n%s'
                    % (name, label, built.stdout[-2000:], built.stderr[-2000:]))
                got = run_program([str(exe)], directory, 300)
                self.assertEqual(
                    got.stdout, oracle.stdout,
                    '%s (%s build) stdout differs from CPython\nCPython:\n%s\nprogram:\n%s\nstderr:\n%s'
                    % (name, label, oracle.stdout, got.stdout, got.stderr[-2000:]))
                self.assertEqual(got.returncode, oracle.returncode,
                                 '%s (%s build) exit %d, CPython %d\nstderr:\n%s'
                                 % (name, label, got.returncode, oracle.returncode,
                                    got.stderr[-2000:]))

    def test_programs_match_cpython(self):
        if not LAB.is_dir():
            self.skipTest('lab/stdlib/functools is not part of this tree')
        for name in PROGRAMS:
            with self.subTest(program=name):
                self._check_source(name, (LAB / (name + '.py')).read_text(encoding='utf-8'))

    def test_review_regressions(self):
        for name, text in REGRESSIONS.items():
            with self.subTest(program=name):
                self._check_source(name, text)


if __name__ == '__main__':
    unittest.main()

"""Differential fuzz round 95: dict/list comprehensions and sorting with a NaN.

The normal case covers comprehensions over ``dict.items()`` with conditions, nested
comprehensions building a dict of lists, and sorting the results in both builds.

CPython's Timsort gives NaN a specific, input-dependent order; the stable merge sorts used
by the typed and boxed runtimes gave a different permutation with no error (silent fuzz95).
The sorts that can see a NaN now run a port of CPython's Timsort, in both builds, so the order
matches exactly; a key that contains no NaN keeps the cheaper merge sort.
"""
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent

NORMAL = r'''def main() -> None:
    d = {"a": 3, "b": 1, "c": 2, "d": 4}
    pairs = [(k, v) for k, v in d.items() if v % 2 == 0]
    print(pairs)
    out = {k: [i for i in range(v) if i % 2 == 0] for k, v in d.items() if v > 1}
    print(out)
    print(sorted(out.items()))
    print(sorted(out.items(), key=lambda kv: (len(kv[1]), kv[0])))
    print(sorted(d.items(), key=lambda kv: kv[1], reverse=True))
    nested = {k: [i * j for i in range(2) for j in range(v)] for k, v in d.items() if k != "c"}
    print(nested)
    print(sorted(nested.items(), key=lambda kv: sum(kv[1])))
    nan = float("nan")
    print(sorted([3.0, nan, 1.0], key=lambda x: 0))
    print(sorted([nan]))
    print(sorted([nan], reverse=True))


main()
'''

NAN_SORT = r'''def sift(vals: list[float]) -> list[float]:
    return sorted(vals)


def main() -> None:
    nan = float("nan")
    print(sorted([3.0, nan, 1.0]))
    print(sorted([1.0, nan, 3.0]))
    print(sorted([nan, 3.0, 1.0]))
    print(sorted([1.0, 3.0, nan]))
    print(sorted([3.0, 1.0, nan]))
    print(sorted([1.0, nan, nan, 3.0]))
    print(sorted([nan, nan]))
    print(sorted([3.0, nan, 1.0], reverse=True))
    print(sorted([1.0, nan, 2.0], key=lambda x: 0))
    print(sorted([nan]))
    xs = [(1.0, nan), (2.0, 0.0), (1.0, 0.0)]
    print(sorted(xs))
    print(sorted([5, 3, 4], key=lambda x: (x, nan)))
    print(sorted([(0, nan), (1, 2.0)], key=lambda kv: kv[1]))
    print(sorted([[1.0, nan], [2.0, 0.0], [1.0, 0.0]]))
    # The first tuple component is a NaN: distinct objects stop the tuple comparison, while
    # the same shared object carries on to the next component (CPython checks identity first).
    print(sorted([5, 3, 4, 1, 2], key=lambda x: (float("nan"), x)))
    print(sorted([5, 3, 4, 1, 2], key=lambda x: (nan, x)))
    print(sorted([5, 3, 4, 1, 2], key=lambda x: (float("nan"), x), reverse=True))
    ns = [float("nan") for _ in range(5)]
    print(sorted([2, 0, 1, 4, 3], key=lambda i: (ns[i], i)))
    shared_ns = [nan, nan, nan, 1.0, 2.0]
    print(sorted([2, 0, 1, 4, 3], key=lambda i: (shared_ns[i], i)))
    ys = [nan, 1.0, 2.0]
    ys.sort()
    print(ys)
    print(sift([2.0, nan, 1.0]))
    d = {"a": [1.0, nan], "b": [2.0, 0.0]}
    print({k: sorted(v) for k, v in d.items()})


main()
'''

CYCLE = r'''def attempt(tag, a):
    try:
        a.sort()
        print(tag, "ok")
    except Exception as e:
        print(tag, type(e).__name__)


a = [1.0, 2.0]
a.append(a)
attempt("selfref", a)

b = [float("nan")]
b.append(b)
attempt("selfref_nan", b)

inner = []
outer = [inner]
inner.append(outer)
attempt("nested", outer)

single = []
single.append(single)
attempt("single", single)


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


class Fuzz95Tests(unittest.TestCase):
    def check(self, slug, text, rc=0):
        with tempfile.TemporaryDirectory(prefix='ail-fuzz95-') as directory:
            want, got_rc, err = _cpython(directory, slug, text)
            self.assertEqual(got_rc, rc, err)
            for general in (True, False):
                got, build_err = _build_and_run(directory, '%s_%s' % (slug, 'g' if general else 'd'),
                                                text, general)
                self.assertIsNotNone(got, '%s (general=%s)\n%s' % (text[:2000], general, build_err))
                self.assertEqual(got, (want, rc), '%s (general=%s)\n%s' % (text[:2000], general, build_err))

    def test_items_comprehensions_and_sorting(self):
        self.check('items_comp', NORMAL)

    def test_nan_sort_matches_cpython(self):
        self.check('nan_sort', NAN_SORT)

    def test_self_referential_list_sort_raises(self):
        self.check('cycle_sort', CYCLE)


if __name__ == '__main__':
    unittest.main()

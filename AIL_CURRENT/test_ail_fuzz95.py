"""Differential fuzz round 95: dict/list comprehensions and sorting with a NaN.

The normal case covers comprehensions over ``dict.items()`` with conditions, nested
comprehensions building a dict of lists, and sorting the results in both builds.

CPython's Timsort gives NaN a specific, input-dependent order; the boxed runtime's stable
merge sort gave a different permutation with no error (silent fuzz95).  A NaN in the values
being sorted, or in a tuple/list sort key, is now refused with a named ``ValueError`` in both
the v1 and v2 boxed sort paths.  A key that contains no NaN is still allowed: the elements
are never compared, so CPython's order is reproducible.
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

NAN_SORT = r'''def main() -> None:
    nan = float("nan")
    try:
        print(sorted([3.0, nan, 1.0]))
    except ValueError as e:
        print("direct", type(e).__name__, str(e))
    try:
        print(sorted([(0, 3.0), (1, nan)], key=lambda kv: (kv[1], kv[0])))
    except ValueError as e:
        print("keyed", type(e).__name__, str(e))


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

    def test_nan_sort_refused_by_name(self):
        with tempfile.TemporaryDirectory(prefix='ail-fuzz95-nan-') as directory:
            for general in (True, False):
                got, build_err = _build_and_run(directory, 'nan_sort_%s' % ('g' if general else 'd'),
                                                NAN_SORT, general)
                self.assertIsNotNone(got, '%s (general=%s)\n%s' % (NAN_SORT[:2000], general, build_err))
                out, rc = got
                self.assertEqual(rc, 0, build_err)
                text = out.decode('utf-8', 'replace')
                self.assertIn('direct ValueError sorting NaN', text)
                self.assertIn('keyed ValueError sorting NaN', text)


if __name__ == '__main__':
    unittest.main()

"""Differential round 40: sorting a key that is or contains NaN is refused, never silently reordered.

Found with small sorting programs against CPython 3.12 on both builds: the general path sorted a
list holding NaN (a literal, arithmetic, an argument, a list item, an attribute, a dict value or a
tuple field) into a merge-sort permutation, while CPython's TimSort left the order its own way. The
typed path already raises ValueError (FLISTSORT / KEYSORT / the IR record sort); the general path's
`ail_list_sort` now scans its decorated keys (recursing through tuples/lists and dict entries) and
raises the same ValueError before sorting. The normal sorting cases below stay CPython-identical.
"""
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent

STABLE = r'''from operator import itemgetter


def main():
    rows = [("b", 2, 1), ("a", 2, 2), ("b", 1, 3), ("a", 1, 4), ("c", 2, 5), ("b", 2, 0)]
    print(sorted(rows))
    print(sorted(rows, reverse=True))
    print(sorted(rows, key=lambda r: (r[0], r[1])))
    print(sorted(rows, key=lambda r: (r[0], -r[2])))
    print(sorted(rows, key=lambda r: (r[0], r[1]), reverse=True))
    print(sorted([r[1] for r in rows]))
    words = ["banana", "Apple", "cherry", "apple", "Banana"]
    print(sorted(words, key=str.lower))
    print(sorted(words, key=str.lower, reverse=True))
    print(sorted(words, key=len))
    d = {"pear": 3, "apple": 3, "fig": 1, "kiwi": 2}
    print(sorted(d.items(), key=lambda kv: (-kv[1], kv[0])))
    print(sorted(d.items(), key=itemgetter(1)))
    print(sorted(d.items(), key=itemgetter(0), reverse=True))
    print(sorted([], key=str.lower), sorted([], reverse=True))


main()
'''

NAN_CAUGHT = r'''class Box:
    pass


def sorter(items):
    return sorted(items)


def main():
    m = (1e308 * 10.0) - (1e308 * 10.0)
    box = Box()
    box.rows = [m, 2.0, 1.0]
    d = {"a": m, "b": 3.0, "c": 1.0}
    try:
        print(sorted([3.0, float("nan"), 1.0]))
    except ValueError:
        print("refused literal")
    try:
        print(sorted([3.0, m, 1.0]))
    except ValueError:
        print("refused arithmetic")
    try:
        print(sorter([3.0, m, 1.0]))
    except ValueError:
        print("refused argument")
    try:
        xs = [3.0, 1.0]
        xs.append(m)
        print(sorted(xs))
    except ValueError:
        print("refused list item")
    try:
        print(sorted(box.rows))
    except ValueError:
        print("refused attribute")
    try:
        print(sorted(d.values()))
    except ValueError:
        print("refused dict value")
    try:
        print(sorted([(2.0, 1.0), (m, 2.0)]))
    except ValueError:
        print("refused tuple")
    try:
        print(sorted([(2.0, 1.0), (m, 2.0)], key=lambda r: r[0]))
    except ValueError:
        print("refused tuple key")
    try:
        print(sorted([3.0, m, 1.0], reverse=True))
    except ValueError:
        print("refused reverse")
    try:
        ys = [3.0, m, 1.0]
        ys.sort()
        print(ys)
    except ValueError:
        print("refused sort method")


main()
'''

NAN_UNCAUGHT = r'''def main():
    m = (1e308 * 10.0) - (1e308 * 10.0)
    print(sorted([2.0, m, 1.0]))


main()
'''

NAN_EXPECTED = b''.join(name + b'\n' for name in (
    b'refused literal', b'refused arithmetic', b'refused argument', b'refused list item',
    b'refused attribute', b'refused dict value', b'refused tuple', b'refused tuple key',
    b'refused reverse', b'refused sort method'))


def _cpython(directory, name, text):
    src = Path(directory) / (name + '_cpython.py')
    src.write_text(text, encoding='utf-8')
    done = subprocess.run([sys.executable, '-B', str(src)], capture_output=True, timeout=120,
                          env=dict(os.environ, PYTHONUTF8='1'))
    return done.stdout.replace(b'\r\n', b'\n'), done.returncode, done.stderr


def _build_and_run(directory, name, text, general):
    src = Path(directory) / (name + '.ail')
    src.write_text(text, encoding='utf-8')
    exe = Path(directory) / ('exe_' + name)
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
    return (got.stdout.replace(b'\r\n', b'\n'), got.returncode), got.stderr.decode('utf-8', 'replace')[-2000:]


class Fuzz40Tests(unittest.TestCase):
    def check_same(self, slug, text):
        with tempfile.TemporaryDirectory(prefix='ail-fuzz40-') as directory:
            want, rc, err = _cpython(directory, slug, text)
            self.assertEqual(rc, 0, err)
            for general in (True, False):
                got, build_err = _build_and_run(directory, '%s_%s' % (slug, 'g' if general else 'd'),
                                                text, general)
                self.assertIsNotNone(got, '%s (general=%s)\n%s' % (slug, general, build_err))
                self.assertEqual(got, (want, 0), '%s (general=%s)\n%s' % (slug, general, build_err))

    def test_stability_and_key_functions(self):
        self.check_same('stable', STABLE)

    def test_nan_refused_through_every_source(self):
        with tempfile.TemporaryDirectory(prefix='ail-fuzz40-') as directory:
            for general in (True, False):
                got, err = _build_and_run(directory, 'nan_%s' % ('g' if general else 'd'),
                                          NAN_CAUGHT, general)
                self.assertIsNotNone(got, err)
                self.assertEqual(got, (NAN_EXPECTED, 0), err)

    def test_uncaught_nan_names_valueerror(self):
        with tempfile.TemporaryDirectory(prefix='ail-fuzz40-') as directory:
            for general in (True, False):
                got, err = _build_and_run(directory, 'nan_uncaught_%s' % ('g' if general else 'd'),
                                          NAN_UNCAUGHT, general)
                self.assertIsNotNone(got, err)
                self.assertEqual(got, (b'', 1), err)
                self.assertIn('ValueError', err)


if __name__ == '__main__':
    unittest.main()

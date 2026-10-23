"""Differential round 85: `zip(*rows)` is a lazy iterator over one iterator per row.

Found with small matrix programs compared against CPython on both builds:

`z = zip(*grid)` used to be materialised when it was made, so changing a row after the
zip object existed was invisible: `z = zip(*g); g[0][0] = 9; print(list(z))` printed
the old first value, and appending to both rows before consuming the zip dropped the new
element.  CPython's zip() calls iter() on every row argument when it is made and advances
those iterators later, so both changes are seen (and a row appended to the OUTER list
afterwards is not).  `next(z)` also raised an internal error because the result was a
list.  The general path now builds one iterator per row and advances them together; the
2-argument zip and every eager comprehension are unchanged.
"""
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent

ZIP_LAZY = r'''def main() -> None:
    g = [[1, 2], [3, 4]]
    z = zip(*g)
    g[0][0] = 9
    g[1][1] = 8
    print(list(z))
    h = [[1, 2], [3, 4]]
    w = zip(*h)
    h[0].append(5)
    h[1].append(6)
    print(list(w))
    k = [[1, 2], [3, 4]]
    v = zip(*k)
    k.append([7, 8])
    print(list(v))
    a = [[1, 2], [3, 4]]
    b = zip(*a)
    a[0].pop()
    print(list(b))


main()
'''

ZIP_PARTIAL = r'''def main() -> None:
    g = [[1, 2, 3], [4, 5, 6]]
    z = zip(*g)
    print(next(z))
    g[0][0] = 9
    g[1].append(7)
    print(list(z))
    h = [[1, 2], [3, 4]]
    w = zip(*h)
    print(next(w), next(w))
    try:
        print(next(w))
    except StopIteration:
        print("stop")
    print(next(w, "done"))
    print(list(w))


main()
'''

ZIP_EDGE = r'''def main() -> None:
    print(list(zip(*[])))
    print(list(zip(*[[]])))
    print(list(zip(*[[1, 2, 3]])))
    print(list(zip(*[[1], [2], [3]])))
    print(list(zip(*[[1, 2], [3, 4, 5], [6]])))
    print(list(zip(*["ab", "cd"])))
    rows = [[1, 2], [3, 4]]
    z = zip(*rows)
    rows[0].append(0)
    print(list(z))
    try:
        list(zip(*[[1, 2], 3]))
    except TypeError:
        print("TypeError")
    try:
        list(zip(*[None]))
    except TypeError:
        print("TypeError None")
    print(list(zip(*((x for x in [1, 2]), [3, 4]))))


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


class Fuzz85Tests(unittest.TestCase):
    def check(self, slug, text, rc=0):
        with tempfile.TemporaryDirectory(prefix='ail-fuzz85-') as directory:
            want, got_rc, err = _cpython(directory, slug, text)
            self.assertEqual(got_rc, rc, err)
            for general in (True, False):
                got, build_err = _build_and_run(directory, '%s_%s' % (slug, 'g' if general else 'd'), text, general)
                self.assertIsNotNone(got, '%s (general=%s)\n%s' % (text[:2000], general, build_err))
                self.assertEqual(got, (want, rc), '%s (general=%s)\n%s' % (text[:2000], general, build_err))

    def test_zip_star_is_lazy(self):
        self.check('zip_lazy', ZIP_LAZY)

    def test_zip_star_after_next(self):
        self.check('zip_partial', ZIP_PARTIAL)

    def test_zip_star_edges(self):
        self.check('zip_edge', ZIP_EDGE)


if __name__ == '__main__':
    unittest.main()

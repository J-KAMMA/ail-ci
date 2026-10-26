"""Differential fuzz round 35: the shape of the tuples going into a dynamic container.

A `list` / `dict` whose element type was still unknown took the tuple shape of its first insertion
and reused that class for everything added later: `d = {}; d[(1, 2)] = "a"; d[()] = "e"` then
`d[()]` returned `"a"` (the reversed order made the empty tuple match every key, and a lookup of
`()` after a non-empty key raised `IndexError: tuple index out of range`) instead of CPython's
`"e"`. The same happened with `xs = []; xs.append((1, 2)); xs.append(())`, and for dict values.
The tuple pass now refuses a second tuple shape in one container by name, so the default build
falls back to the general path; both builds print what CPython prints.
"""
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent

MIXED = r'''def main():
    d = {}
    d[(1, 2)] = "a"
    d[()] = "e"
    d[(3, (4, 5))] = "n"
    print(d[(3, (4, 5))], d[(1, 2)], d[()], len(d))
    print((3, (4, 5)) in d, () in d, (9, 9) in d)

    e = {}
    e[()] = 0
    e[(1, 2)] = 1
    print(e[()], e[(1, 2)], len(e))

    xs = []
    xs.append((1, 2))
    xs.append(())
    print(xs, xs[0], xs[1], len(xs))

    ys = []
    ys.append(())
    ys.append((3, 4))
    print(ys)

    vals = {}
    vals["a"] = (1, 2)
    vals["b"] = ()
    print(vals["a"], vals["b"], vals)
main()
'''

SAME_SHAPE = r'''def main():
    d = {}
    d[(1, 2)] = "a"
    d[(3, 4)] = "b"
    print(d[(1, 2)], d[(3, 4)], len(d))
    xs = []
    xs.append((1, 2))
    xs.append((5, 6))
    print(xs, len(xs))
    vals = {}
    vals["a"] = (1, 2)
    vals["b"] = (3, 4)
    print(vals["a"], vals["b"])
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


def _build_typed_only(directory, name, text):
    src = Path(directory) / (name + '.ail')
    src.write_text(text, encoding='utf-8')
    exe = Path(directory) / ('exe_' + name + '_strict')
    env = dict(os.environ, AIL_NO_CACHE='1', AIL_NO_GENERAL='1')
    env.pop('AIL_UNIFIED_FORCE', None)
    return subprocess.run([sys.executable, '-B', str(ROOT / 'ail_chatgpt.py'), 'compile', src.name,
                           '--syntax', 'python', '-o', exe.name], cwd=directory,
                          capture_output=True, text=True, timeout=900, env=env)


class Fuzz35Tests(unittest.TestCase):
    def check(self, slug, text, rc=0):
        with tempfile.TemporaryDirectory(prefix='ail-fuzz35-') as directory:
            want, got_rc, err = _cpython(directory, slug, text)
            self.assertEqual(got_rc, rc, err)
            for general in (True, False):
                got, build_err = _build_and_run(directory, '%s_%s' % (slug, 'g' if general else 'd'),
                                                text, general)
                self.assertIsNotNone(got, '%s (general=%s)\n%s' % (text[:2000], general, build_err))
                self.assertEqual(got, (want, rc), '%s (general=%s)\n%s' % (text[:2000], general, build_err))

    def test_dynamic_container_mixed_tuple_shapes(self):
        self.check('mixed_shapes', MIXED)

    def test_dynamic_container_same_tuple_shape_still_typed(self):
        self.check('same_shape', SAME_SHAPE)

    def test_mixed_shapes_refused_by_name_on_the_typed_path(self):
        with tempfile.TemporaryDirectory(prefix='ail-fuzz35-strict-') as directory:
            built = _build_typed_only(directory, 'mixed_shapes', MIXED)
            self.assertNotEqual(built.returncode, 0, built.stdout + built.stderr)
            self.assertIn('different shapes', built.stdout + built.stderr)


if __name__ == '__main__':
    unittest.main()

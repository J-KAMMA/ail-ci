"""Pre-existing difference from job fuzz95: heapq.nlargest/nsmallest with NaN.

CPython's heapq is not `sorted(xs, reverse=...)[:n]` when the ordering is non-transitive:
it builds a decorated heap, replaces the root, then sorts only the selected decorations.
With NaN in the input that changes which values are selected and in what order. Both
builds are compared with CPython here, including small inputs, the n>=len shortcut, key
functions, tuples containing NaN, and a larger case that exercises Timsort's merge path.
"""
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent

NAN_SELECT = r'''import heapq
nan = float('nan')


def keyfirst(p):
    return p[0]


def top_arg(n, data):
    return heapq.nlargest(n, data)


def low_arg(n, data):
    return heapq.nsmallest(n, data)


def main() -> None:
    xs = [2.0, nan, 3.0]
    print(heapq.nlargest(3, xs))
    print(heapq.nsmallest(3, xs))
    print(heapq.nlargest(2, xs))
    print(heapq.nsmallest(2, xs))
    print(heapq.nlargest(0, xs), heapq.nsmallest(-1, xs), heapq.nlargest(9, xs))

    ys = [5.0, 1.0, nan, 3.0, 2.0]
    print(heapq.nlargest(3, ys), heapq.nsmallest(3, ys))
    zs = [1.0, 2.0, nan, 4.0]
    print(heapq.nlargest(3, zs), heapq.nsmallest(3, zs))

    pairs = [(2.0, "a"), (nan, "b"), (3.0, "c")]
    print(heapq.nlargest(3, pairs, key=keyfirst))
    print(heapq.nsmallest(3, pairs, key=keyfirst))
    print(heapq.nlargest(2, pairs), heapq.nsmallest(2, pairs))

    before = xs + ys
    print(top_arg(2, xs), low_arg(2, ys))
    print(before == xs + ys, xs, ys)
    box = [xs]
    print(heapq.nlargest(3, box[0]))
    d = {"x": ys}
    print(heapq.nsmallest(3, d["x"]))

    data = []
    for i in range(200):
        if i % 11 == 0:
            data.append((nan, i))
        else:
            data.append((float((i * 17) % 53), i))
    print(heapq.nlargest(20, data, key=keyfirst))
    print(heapq.nsmallest(20, data, key=keyfirst))
    print(heapq.nlargest(40, [x[0] for x in data]))
    print(heapq.nsmallest(40, [x[0] for x in data]))


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


class Pre95Tests(unittest.TestCase):
    def check(self, slug, text):
        with tempfile.TemporaryDirectory(prefix='ail-pre95-') as directory:
            want, rc, err = _cpython(directory, slug, text)
            self.assertEqual(rc, 0, err)
            for general in (True, False):
                got, build_err = _build_and_run(directory, '%s_%s' % (slug, 'g' if general else 'd'),
                                                text, general)
                self.assertIsNotNone(got, 'general=%s\n%s' % (general, build_err))
                self.assertEqual(got, (want, 0), 'general=%s\n%s' % (general, build_err))

    def test_nan_nlargest_nsmallest(self):
        self.check('nan_select', NAN_SELECT)


if __name__ == '__main__':
    unittest.main()

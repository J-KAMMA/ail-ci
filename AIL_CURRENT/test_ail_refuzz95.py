"""refuzz95: a sort over a NaN key is refused by name, never silently different from CPython.

An old job (fuzz95) found that ``sorted()`` / ``.sort()`` over floats (or keys) that contain a
NaN returns a different permutation from CPython 3.12 with no error: CPython's Timsort keeps a
specific, input-dependent order because every comparison with a NaN is false, while the runtime's
stable merge sort produces another.  The typed path already stops by name for a plain float list
(``ail_flist_sort`` / the KEYSORT float column check raise ``ValueError``); the boxed path
(``ail_list_sort``, python/pkg-v12/cruntime.py) did not.  It now scans the decorate keys -- a key
function's result, and a tuple/list key item by item -- and raises a named ``ValueError``
(DIFFERENCES C?-job-refuzz95-10300605-1) instead of returning the wrong order.  NaN-free keys keep
the same stable merge sort and the same order as before (compared here against CPython).

The boxed refusal carries the "refuzz95" name in its message; the typed KEYSORT/flist stop is a
bare ``ValueError`` (by name only), so the message is only required for the cases that stay boxed.
"""
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent
CHATGPT = str(ROOT / 'ail_chatgpt.py')


def cpython(directory, name, text):
    src = Path(directory) / (name + '_cpython.py')
    src.write_text(text, encoding='utf-8')
    done = subprocess.run([sys.executable, '-B', str(src)], capture_output=True, timeout=120,
                          env=dict(os.environ, PYTHONUTF8='1', PYTHONWARNINGS='ignore'))
    return done.stdout.replace(b'\r\n', b'\n'), done.returncode


def build(directory, name, text, general):
    src = Path(directory) / (name + '.py')
    src.write_text(text, encoding='utf-8')
    exe = Path(directory) / ('exe_' + name + ('_g' if general else '_d'))
    env = dict(os.environ, AIL_NO_CACHE='1', AIL_QUIET_FALLBACK='1')
    env.pop('AIL_NO_GENERAL', None)
    if general:
        env['AIL_UNIFIED_FORCE'] = '1'
    else:
        env.pop('AIL_UNIFIED_FORCE', None)
    return exe, subprocess.run([sys.executable, '-B', CHATGPT, 'compile', src.name,
                                '--syntax', 'python', '-o', exe.name], cwd=directory,
                               capture_output=True, text=True, timeout=900, env=env)


# NaN-free sorts: must build, run, and match CPython on both builds (not refused).
MATCHING = {
    'm_ints': 'print(sorted([3, 1, 2]))\n',
    'm_floats': 'print(sorted([3.5, -1.25, 2.0]))\n',
    'm_reverse': 'print(sorted([3.0, 1.0, 2.0], reverse=True))\n',
    'm_tuples': 'print(sorted([(1.0, "a"), (0.5, "c"), (2.0, "b")]))\n',
    'm_reverse_tuples': 'print(sorted([(1.0, "a"), (0.5, "c"), (2.0, "b")], reverse=True))\n',
    'm_key': 'print(sorted([2.0, 1.0, 1.0], key=lambda v: -v))\n',
    'm_stable': 'pairs = [(1, "x"), (0, "y"), (1, "z"), (0, "w")]\n'
                'print(sorted(pairs, key=lambda t: t[0]))\n',
    'm_stable_reverse': 'pairs = [(1, "x"), (0, "y"), (1, "z"), (0, "w")]\n'
                        'print(sorted(pairs, key=lambda t: t[0], reverse=True))\n',
    'm_empty': 'print(sorted([]))\n',
    'm_inf': 'print(sorted([-float("inf"), 1.0, float("inf"), 0.0]))\n',
    'm_method': 'xs = [2.5, -1.5, 3.5, 0.0]\nxs.sort()\nprint(xs)\n',
    # a NaN used elsewhere must not make an unrelated NaN-free sort refuse
    'm_nan_elsewhere': 'import math\nnan = float("nan")\nprint(math.isnan(nan))\n'
                       'print(sorted([3.0, 1.0, 2.0]))\nprint(sorted([3, 1, 2], reverse=True))\n',
}

# NaN inside the keys: must build and then stop by name (non-zero exit, ValueError).
REFUSED = {
    'r_direct': 'nan = float("nan")\nprint(sorted([3.0, nan, 1.0, 2.0]))\n',
    'r_reverse': 'nan = float("nan")\nprint(sorted([nan, 2.0, 1.0, nan, 0.0], reverse=True))\n',
    'r_tuple': 'nan = float("nan")\nprint(sorted([(1.0, "a"), (nan, "b"), (0.5, "c")]))\n',
    'r_listkey': 'nan = float("nan")\nprint(sorted([[1.0], [nan], [0.5]]))\n',
    'r_allnan': 'nan = float("nan")\nprint(sorted([nan, nan, nan]))\n',
    'r_keyfn': 'nan = float("nan")\nxs = [2.0, nan, 1.0]\nxs.sort(key=lambda v: v)\nprint(xs)\n',
    'r_method': 'nan = float("nan")\nxs = [2.0, 1.0, 0.0]\nxs[1] = nan\nxs.sort()\nprint(xs)\n',
    'r_arg': 'nan = float("nan")\ndef f(xs):\n    xs.sort()\n    return xs\nprint(f([3.0, nan, 1.0]))\n',
    'r_listitem': 'nan = float("nan")\nouter = [[3.0, nan, 1.0]]\nprint(sorted(outer[0]))\n',
    'r_attribute': 'nan = float("nan")\nclass Box:\n    def __init__(self):\n'
                   '        self.xs = [2.0, nan, 1.0]\nbox = Box()\nprint(sorted(box.xs))\n',
    'r_dictvalue': 'nan = float("nan")\nd = {"k": [9.0, nan, 0.0]}\nprint(sorted(d["k"]))\n',
}

# Of those, the ones the boxed runtime refuses (both builds) and whose message names the issue.
# r_keyfn / r_method may lower to the typed KEYSORT/flist stop on the default build, a bare
# ValueError, so they are only required to be refused by name (ValueError), not by message.
NAMED = ('r_direct', 'r_reverse', 'r_tuple', 'r_listkey', 'r_allnan', 'r_arg',
         'r_listitem', 'r_attribute', 'r_dictvalue')


class Refuzz95Tests(unittest.TestCase):
    def test_nan_free_sorts_match_cpython(self):
        with tempfile.TemporaryDirectory(prefix='ail-refuzz95-') as directory:
            for slug, text in MATCHING.items():
                want = cpython(directory, slug, text)
                for general in (True, False):
                    exe, built = build(directory, '%s_%s' % (slug, 'g' if general else 'd'), text, general)
                    self.assertEqual(built.returncode, 0, (slug, general, built.stdout + built.stderr))
                    got = subprocess.run([str(exe)], capture_output=True, timeout=120, cwd=directory)
                    self.assertEqual(got.stdout.replace(b'\r\n', b'\n'), want[0],
                                     (slug, general, got.stderr[-800:]))
                    self.assertEqual(got.returncode, want[1], (slug, general, got.stderr[-800:]))

    def test_nan_sorts_are_refused_by_name(self):
        with tempfile.TemporaryDirectory(prefix='ail-refuzz95-') as directory:
            for slug, text in REFUSED.items():
                for general in (True, False):
                    exe, built = build(directory, '%s_%s' % (slug, 'g' if general else 'd'), text, general)
                    self.assertEqual(built.returncode, 0, (slug, general, built.stdout + built.stderr))
                    got = subprocess.run([str(exe)], capture_output=True, timeout=120, cwd=directory)
                    self.assertNotEqual(got.returncode, 0, (slug, general, got.stdout[-400:]))
                    self.assertIn(b'ValueError', got.stderr, (slug, general, got.stderr[-800:]))
                    if slug in NAMED:
                        self.assertIn(b'refuzz95', got.stderr, (slug, general, got.stderr[-800:]))


if __name__ == '__main__':
    unittest.main()

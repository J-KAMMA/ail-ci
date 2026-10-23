"""List mutation methods used as values (fuzz round 44), against CPython 3.12.

`xs.append(v)`, `xs.extend(it)`, `xs.reverse()`, `xs.sort()` and `xs.clear()` return None in Python.
The typed path has no None value: using one of these calls inside an expression emitted a void C call
into a temporary (`v_x = ail_list_push(...)`), so the default build failed in the C compiler even
though the general path was right.  The typed path now refuses the value form by name, so the
default build takes the general path and prints CPython's answer.  A plain statement call stays on
the typed path (checked with --strict), so the normal mutation forms keep their fast emitter.
"""
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent
CHATGPT = str(ROOT / 'ail_chatgpt.py')
HAVE_CC = shutil.which('gcc') is not None

VALUE_RETURNS = '''
def main():
    xs = [3, 1, 2]
    print(xs.sort())
    print(xs[0], xs[-1])
    print(xs.append(4))
    print(len(xs), xs[-1])
    print(xs.extend([5, 6]))
    print(len(xs), xs[-1])
    print(xs.reverse())
    print(xs[0], xs[-1])
    print(xs.clear())
    print(len(xs))
    ys = [1]
    r = ys.append(2)
    print(r is None, len(ys))
    zs: list[str] = ["b", "a"]
    print(zs.reverse())
    print(zs[0], zs[1])
    fs: list[float] = [2.5, 1.5]
    print(fs.reverse())
    print(fs[0], fs[1])
    e: list[int] = []
    print(e.reverse(), e.clear(), e.extend([]))
    print(e.append(1) is None, len(e))


main()
'''

MUTATE_AND_COMPARE = '''
def main():
    xs = [1, 2, 1, 3, 1]
    xs.remove(1)
    print(len(xs), xs[0], xs[1], xs[2])
    ys = xs.copy()
    zs = xs[:]
    ws = xs
    xs.reverse()
    print(xs[0], xs[2], ys[0], zs[0], ws[0])
    ys.extend([9])
    zs.clear()
    print(len(xs), len(ys), len(zs), xs == ws, ys == [2, 1, 3, 9])
    inner = [1]
    g = [inner]
    h = g.copy()
    inner.append(2)
    print(len(g[0]), len(h[0]))
    big = list(range(1000))
    big.reverse()
    print(len(big), big[0], big[999])
    big.remove(500)
    print(len(big), big[499])


main()
'''

PATHS = '''
class C:
    def __init__(self):
        self.xs = [1, 2]
        self.fs = [1.5]
        self.ss = ["a"]


def f(xs):
    return xs.append(2)


def main():
    xs = [1]
    print(f(xs), len(xs), xs[1])
    g = [[1], [2]]
    print(g[0].append(3), len(g[0]), len(g[1]))
    print(g[1].extend([4]), len(g[1]))
    c = C()
    print(c.xs.append(3), len(c.xs))
    print(c.fs.reverse(), c.fs[0])
    print(c.ss.extend(["b"]), len(c.ss))
    d = {"k": [1, 2]}
    print(d["k"].append(3), len(d["k"]))
    print(d["k"].reverse(), d["k"][0], d["k"][-1])
    ys = [1]
    ws = ys
    print(ws.append(2) is None, len(ys), ys[1])


main()
'''

STATEMENTS = '''
def main():
    xs: list[int] = [3, 1, 2]
    xs.append(4)
    xs.extend([5, 6])
    xs.reverse()
    xs.sort()
    xs.clear()
    fs: list[float] = [2.5, 1.5]
    fs.append(0.5)
    fs.reverse()
    fs.sort()
    ss: list[str] = ["b"]
    ss.append("a")
    ss.reverse()
    ss.sort()
    g: list[list[int]] = []
    g.append([1])
    print(len(xs), len(fs), len(ss), len(g), fs[0], ss[0], g[0][0])


main()
'''


def _run(directory, name, text, general, strict=False):
    src = Path(directory) / (name + '.ail')
    src.write_text(text, encoding='utf-8')
    exe = Path(directory) / ('exe_' + name + ('_g' if general else '_d'))
    env = dict(os.environ, AIL_NO_CACHE='1', AIL_QUIET_FALLBACK='1')
    env.pop('AIL_NO_GENERAL', None)
    if general:
        env['AIL_UNIFIED_FORCE'] = '1'
    cmd = [sys.executable, '-B', CHATGPT, 'compile', src.name, '--syntax', 'python', '-o', exe.name]
    if strict:
        cmd.append('--strict')
    built = subprocess.run(cmd, cwd=directory, capture_output=True, text=True, timeout=900, env=env)
    if built.returncode != 0:
        return None, (built.stdout + built.stderr)[-2000:]
    got = subprocess.run([str(exe)], capture_output=True, timeout=120, cwd=directory)
    return (got.stdout.replace(b'\r\n', b'\n'), got.returncode), got.stderr.decode('utf-8', 'replace')[-800:]


@unittest.skipUnless(HAVE_CC, 'gcc is required')
class ListMutationValues(unittest.TestCase):
    def check(self, name, text):
        with tempfile.TemporaryDirectory(prefix='ail-fuzz44-') as directory:
            src = Path(directory) / (name + '_cpython.py')
            src.write_text(text, encoding='utf-8')
            want = subprocess.run([sys.executable, '-B', str(src)], capture_output=True, timeout=120)
            expected = (want.stdout.replace(b'\r\n', b'\n'), want.returncode)
            for general in (True, False):
                got, err = _run(directory, name, text, general)
                self.assertIsNotNone(got, '%s (general=%s)\n%s' % (name, general, err))
                self.assertEqual(got, expected, '%s (general=%s)\n%s' % (name, general, err))

    def test_list_method_values_are_none(self):
        self.check('value_returns', VALUE_RETURNS)

    def test_remove_copy_slice_equality_and_reverse(self):
        self.check('mutate_compare', MUTATE_AND_COMPARE)

    def test_value_form_through_argument_item_attribute_and_dict(self):
        self.check('paths', PATHS)

    def test_plain_statement_mutations_stay_typed(self):
        with tempfile.TemporaryDirectory(prefix='ail-fuzz44-') as directory:
            got, err = _run(directory, 'statements', STATEMENTS, False, strict=True)
        self.assertIsNotNone(got, err)

    def test_value_form_is_refused_by_name(self):
        with tempfile.TemporaryDirectory(prefix='ail-fuzz44-') as directory:
            got, err = _run(directory, 'refused', VALUE_RETURNS, False, strict=True)
        self.assertIsNone(got)
        self.assertIn('list.append() returns None', err)
        self.assertIn('use it as a statement', err)


if __name__ == '__main__':
    unittest.main()

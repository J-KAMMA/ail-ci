"""Fold a constant index expression that reduces to an in-range int (job pre276).

The reviewer of job rbpre47 recorded a pre-existing difference: the index
``[1, 2, 3][(-2 ** 63) // (2 ** 63)]`` was refused as
``int64 index out of range: 9223372036854775808`` on both builds, although the
expression is -1 and CPython indexes the last item.  The per-step int64 check ran
before the enclosing division, so a wider operand that cancels back into int64 was
rejected.  The index check now folds the whole expression exactly (with the code
generator's budget) when the per-step check overflows, and keeps refusing an index
whose final value leaves int64 by name.
"""
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent

INDEX_FOLDED = r'''class Box:
    def __init__(self, xs) -> None:
        self.xs = xs


def pick(xs):
    return xs[(-2 ** 63) // (2 ** 63)]


def show(label, fn) -> None:
    try:
        print(label, fn())
    except Exception as e:
        print(label, type(e).__name__, e)


def main() -> None:
    box = Box([1, 2, 3])
    print([1, 2, 3][(-2 ** 63) // (2 ** 63)])
    print((4, 5, 6)[(-2 ** 63) // (2 ** 63)])
    print("abc"[(-2 ** 63) // (2 ** 63)])
    print(b"abc"[(-2 ** 63) // (2 ** 63)])
    print({-1: "minus", 0: "zero"}[(-2 ** 63) // (2 ** 63)])
    print(pick([7, 8, 9]))
    print([[10, 11, 12]][0][(-2 ** 63) // (2 ** 63)])
    print({"k": [13, 14, 15]}["k"][(-2 ** 63) // (2 ** 63)])
    print(box.xs[(-2 ** 63) // (2 ** 63)])

    d = {0: "zero", 1: "one", 2: "two", 3: "three", -1: "minus", -2: "minus2"}
    print(d[((1 << 63) + (1 << 63) - 1) // (1 << 63)])
    print(d[(2 ** 63) // (2 ** 63)])
    print(d[((2 ** 63) + (2 ** 63)) // (2 ** 63)])
    print(d[(-2 ** 63) // (2 ** 63)])
    print(d[(-2 ** 63) // (2 ** 63) + 1])
    print(d[(-2 ** 63) // (2 ** 63) + 3])
    print(d[(2 ** 63 - 1) // (2 ** 63)])

    e = {-(1 << 63): "min", (1 << 63) - 1: "max"}
    print(e[(-2 ** 63) // 1])
    print(e[(1 << 63) - 1])

    print(d[(-2 ** 63) // (-2 ** 63)])
    print(d[(2 ** 63) // (-2 ** 63)])
    print(d[((-(2 ** 63) - 1) // (2 ** 63))])
    print(d[((-(2 ** 63) - 1) // (2 ** 63)) + 1])
    print(d[(-(2 ** 63) + 1) // (2 ** 63)])
    print(d[((2 ** 63) - 1) // (-(2 ** 63))])
    print(d[(-2 ** 63) // ((2 ** 63) - 1)])

    w = {0: "zero", 1: "one", 2: "two", 3: "three", 4: "four", 10: "ten"}
    print(w[((1 << 5000) >> 4998)])
    print(w[((10 ** 64) // (10 ** 63))])
    print(w[((1 << 200) - (1 << 199)) // (1 << 199)])
    print(w[(2 ** 100) // (2 ** 90) // (2 ** 10)])
    print(w[((-1 << 63) - 1) // (1 << 63) + 3])

    xs = ys = [1, 2, 3]
    xs[(-2 ** 63) // (2 ** 63)] = 9
    print(xs, ys)
    ys[(-2 ** 63) // (2 ** 63)] += 10
    print(xs, ys)
    print(ys[(-2 ** 63) // (2 ** 63)])

    show("empty-list", lambda: [][(-2 ** 63) // (2 ** 63)])
    show("empty-tuple", lambda: ()[(-2 ** 63) // (2 ** 63)])
    print("done")


main()
'''

INDEX_REFUSED = {
    'positive_shift': 'xs = [1]\nprint(xs[(1 << 63) + (1 << 63)])\n',
    'below_min': 'd = {}\nprint(d[-(1 << 63) - 1])\n',
    'power': 'xs = [1]\nprint(xs[10 ** 20])\n',
}


def _cpython(directory, name, text):
    src = Path(directory) / (name + '_cpython.py')
    src.write_text(text, encoding='utf-8')
    done = subprocess.run([sys.executable, '-B', str(src)], capture_output=True, timeout=120,
                          env=dict(os.environ, PYTHONUTF8='1'))
    return done.stdout.replace(b'\r\n', b'\n'), done.returncode, done.stderr


def _build(directory, name, text, general):
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
    return built, exe


class Pre276Tests(unittest.TestCase):
    def test_in_range_index_is_folded(self):
        with tempfile.TemporaryDirectory(prefix='ail-pre276-') as directory:
            want, want_rc, err = _cpython(directory, 'folded', INDEX_FOLDED)
            self.assertEqual(want_rc, 0, err)
            for general in (True, False):
                with self.subTest(general=general):
                    built, exe = _build(directory, 'folded_%s' % ('g' if general else 'd'),
                                        INDEX_FOLDED, general)
                    output = built.stdout + built.stderr
                    self.assertEqual(built.returncode, 0, output[-4000:])
                    got = subprocess.run([str(exe)], capture_output=True, timeout=120, cwd=directory)
                    self.assertEqual(got.stdout.replace(b'\r\n', b'\n'), want, output[-4000:])
                    self.assertEqual(got.returncode, want_rc, output[-4000:])

    def test_out_of_int64_index_is_refused_by_name(self):
        with tempfile.TemporaryDirectory(prefix='ail-pre276-') as directory:
            for slug, text in INDEX_REFUSED.items():
                for general in (True, False):
                    with self.subTest(slug=slug, general=general):
                        built, exe = _build(directory, '%s_%s' % (slug, 'g' if general else 'd'),
                                            text, general)
                        output = built.stdout + built.stderr
                        self.assertEqual(built.returncode, 2, '%s\n%s' % (slug, output[-4000:]))
                        self.assertFalse(exe.exists(), '%s built an executable' % slug)
                        self.assertIn('int64 index out of range', output, output[-4000:])


if __name__ == '__main__':
    unittest.main()

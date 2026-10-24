"""pre143: an int expression over module constants is folded exactly.

`E = 63` followed by `2 ** E - 1` inside a function body used to overflow at
run time: `2 ** 63` does not fit int64 even though the answer does.  The source
pass now evaluates an all-int expression built from literals and module
constants with Python's unbounded ints (shadowed names excluded), and emits the
one in-range literal.  A result that does not itself fit int64 is left to the
runtime's overflow stop, and a function that binds the name keeps its own value.
Each program is built on both builds and compared with CPython.
"""
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent

MODULE_EXPONENT = r'''E = 63


def main():
    print(2 ** E - 1)
    print(2 ** E - 2 ** E)
    print((1 << E) - 1)
    print(0 - 2 ** E + 1)


main()
print(2 ** E - 1)
'''

MODULE_CONTEXTS = r'''E = 63


class Box:
    def __init__(self):
        self.v = 0


def identity(v):
    return v


def main():
    print(identity(2 ** E - 1))
    xs = [2 ** E - 1, 2 ** E - 1]
    print(xs[0], xs[1])
    box = Box()
    box.v = 2 ** E - 1
    print(box.v)
    d = {"k": 2 ** E - 1}
    print(d["k"])


main()
'''

SHADOWING = r'''E = 63


def parameter(E):
    return 2 ** E - 1


def local():
    E = 3
    return 2 ** E - 1


def nested():
    E = 4

    def inner():
        nonlocal E
        return 2 ** E - 1

    return inner()


def read_global():
    global E
    return 2 ** E - 1


def write_global():
    global E
    E = 5
    return 2 ** E - 1


def plain():
    return 2 ** E - 1


def main():
    print(parameter(4), local(), nested(), read_global(), write_global(), plain())
    print(2 ** E - 1)


main()
'''

BOUNDARIES = r'''E = 63


def main():
    print(2 ** E * 2 // 2 - 1)
    print((1 << (E - 1)) * 2 - 1)
    print(0 - 2 ** (E - 1))
    print((2 ** (E + 1) - 1) % 7)
    print(2 ** E // 3)
    print(E * 0)
    print(-(2 ** E - 1))
    print((E - E) ** (E - E))


main()
'''

OTHER_TYPES = r'''F = 2.5
S = "ab"


def main():
    print(F + 1.0)
    print(S * 3)
    print(F * 2 == 5.0)


main()
'''

MODES = (('default', False), ('general', True))


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
    for key in ('AIL_UNIFIED_FORCE', 'AIL_UNIFIED', 'AIL_IR', 'AIL_NO_GENERAL'):
        env.pop(key, None)
    if general:
        env['AIL_UNIFIED_FORCE'] = '1'
    built = subprocess.run([sys.executable, '-B', str(ROOT / 'ail_chatgpt.py'), 'compile', src.name,
                            '--syntax', 'python', '-o', exe.name], cwd=directory,
                           capture_output=True, text=True, timeout=900, env=env)
    if built.returncode != 0:
        return None, (built.stdout + built.stderr)[-3000:]
    got = subprocess.run([str(exe)], capture_output=True, timeout=120, cwd=directory)
    return (got.stdout.replace(b'\r\n', b'\n'), got.returncode), got.stderr.decode('utf-8', 'replace')[-1500:]


class Pre143Tests(unittest.TestCase):
    def check(self, slug, text, rc=0):
        with tempfile.TemporaryDirectory(prefix='ail-pre143-') as directory:
            want, got_rc, err = _cpython(directory, slug, text)
            self.assertEqual(got_rc, rc, err)
            for mode, general in MODES:
                got, build_err = _build_and_run(directory, '%s_%s' % (slug, mode), text, general)
                self.assertIsNotNone(got, '%s (%s)\n%s' % (text[:2000], mode, build_err))
                self.assertEqual(got, (want, rc), '%s (%s)\n%s' % (text[:2000], mode, build_err))

    def test_module_constant_exponent(self):
        self.check('module_exponent', MODULE_EXPONENT)

    def test_module_constant_contexts(self):
        self.check('module_contexts', MODULE_CONTEXTS)

    def test_shadowing(self):
        self.check('shadowing', SHADOWING)

    def test_int64_boundaries(self):
        self.check('int64_boundaries', BOUNDARIES)

    def test_other_constant_types(self):
        self.check('other_types', OTHER_TYPES)


if __name__ == '__main__':
    unittest.main()

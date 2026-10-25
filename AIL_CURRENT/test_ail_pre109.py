"""pre109: a negative shift count is CPython's ValueError on both builds.

The typed shift guards raised the right exception code with an empty message, and a
mixed-mode typed clone of a helper using ``<<``/``>>`` (or ``<<=``/``>>=``) escaped the
caller's boxed ``try``.  Both guards now carry CPython's ``negative shift count`` text,
and the mixed-mode selector treats a shift with a count that is not a non-negative
literal as a ValueError trap, so the caller keeps its handler.  The cases below cover
the message, both operators, constant/argument/list/attribute/dict counts, zero and
valid shifts, augmented assignment and an uncaught typed failure.
"""
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent


SHIFT_MESSAGE = r'''class Box:
    def __init__(self, n):
        self.n = n


box = Box(-2)
xs = [4, -3]
d = {"a": 6, "b": -1}


def report(tag, value):
    print(tag, value)


try:
    report("left-const", 1 << -1)
except ValueError as e:
    report("left-const", (type(e).__name__, str(e), e.args))
try:
    report("right-const", 8 >> -1)
except ValueError as e:
    report("right-const", (type(e).__name__, str(e), e.args))
try:
    report("left-list", xs[0] << xs[1])
except ValueError as e:
    report("left-list", (type(e).__name__, str(e), e.args))
try:
    report("right-list", xs[0] >> xs[1])
except ValueError as e:
    report("right-list", (type(e).__name__, str(e), e.args))
try:
    report("left-attr", d["a"] << box.n)
except ValueError as e:
    report("left-attr", (type(e).__name__, str(e), e.args))
try:
    report("right-dict", d["a"] >> d["b"])
except ValueError as e:
    report("right-dict", (type(e).__name__, str(e), e.args))
try:
    report("left-zero", 0 << -9)
except ValueError as e:
    report("left-zero", (type(e).__name__, str(e), e.args))
print("done")
'''

SHIFT_ARGUMENT = r'''class Box:
    def __init__(self, n):
        self.n = n


def by_argument(a, b):
    return a << b


def by_argument_right(a, b):
    return a >> b


def main():
    box = Box(-2)
    xs = [4, -3]
    d = {"a": 6, "b": -1}
    try:
        print("left-arg", by_argument(3, -4))
    except ValueError as e:
        print("left-arg", type(e).__name__, repr(str(e)), repr(e.args))
    try:
        print("right-arg", by_argument_right(16, -4))
    except ValueError as e:
        print("right-arg", type(e).__name__, repr(str(e)), repr(e.args))
    try:
        print("left-list", by_argument(xs[0], xs[1]))
    except ValueError as e:
        print("left-list", type(e).__name__, repr(str(e)), repr(e.args))
    try:
        print("right-attr", by_argument_right(d["a"], box.n))
    except ValueError as e:
        print("right-attr", type(e).__name__, repr(str(e)), repr(e.args))
    try:
        print("left-dict", by_argument(d["a"], d["b"]))
    except ValueError as e:
        print("left-dict", type(e).__name__, repr(str(e)), repr(e.args))
    print("done")


main()
'''

SHIFT_VALID = r'''class Box:
    def __init__(self, n):
        self.n = n


def shift(a, b):
    return a << b, a >> b


def shr(a, b):
    return a >> b


def main():
    box = Box(3)
    xs = [5, 2]
    d = {"a": 7, "b": 1}
    print(shift(1, 0), shift(1, 1), shift(1, 62))
    print(shift(-1, 1), shift(-1, 62))
    print(shr(8, 63), shr(-8, 63), shr(8, 64), shr(-8, 64), shr(8, 1000), shr(-8, 1000))
    print(xs[0] << xs[1], xs[0] >> xs[1])
    print(d["a"] << box.n, d["a"] >> box.n)
    print(0 << 64, 0 << 1000)
    print("done")


main()
'''

AUG_SHIFT_MIXED = r'''def aug_shl(a, b):
    a <<= b
    return a


def aug_shr(a, b):
    a >>= b
    return a


mixed = [1, "two", 3.0]
print(mixed)


def main():
    try:
        print("l", aug_shl(1, -1))
    except ValueError as e:
        print("l caught", type(e).__name__, repr(str(e)), repr(e.args))
    try:
        print("r", aug_shr(8, -1))
    except ValueError as e:
        print("r caught", type(e).__name__, repr(str(e)), repr(e.args))
    print("done")


main()
'''

UNCAUGHT = r'''print(1 << -1)
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


class Pre109Tests(unittest.TestCase):
    def check(self, slug, text, rc=0, stderr_last=None):
        with tempfile.TemporaryDirectory(prefix='ail-pre109-') as directory:
            want, got_rc, err = _cpython(directory, slug, text)
            self.assertEqual(got_rc, rc, err)
            if stderr_last is not None:
                lines = [line for line in err.decode('utf-8', 'replace').splitlines() if line.strip()]
                self.assertEqual(lines[-1], stderr_last)
            for general in (True, False):
                got, build_err = _build_and_run(directory, '%s_%s' % (slug, 'g' if general else 'd'), text, general)
                self.assertIsNotNone(got, '%s (general=%s)\n%s' % (text[:2000], general, build_err))
                self.assertEqual(got, (want, rc), '%s (general=%s)\n%s' % (text[:2000], general, build_err))
                if stderr_last is not None:
                    lines = [line for line in build_err.splitlines() if line.strip()]
                    self.assertEqual(lines[-1], stderr_last, '%s (general=%s)' % (slug, general))

    def test_negative_shift_message(self):
        self.check('shift_message', SHIFT_MESSAGE)

    def test_negative_shift_through_calls(self):
        self.check('shift_argument', SHIFT_ARGUMENT)

    def test_valid_shifts(self):
        self.check('shift_valid', SHIFT_VALID)

    def test_augmented_shift_in_mixed_mode(self):
        self.check('shift_aug_mixed', AUG_SHIFT_MIXED)

    def test_uncaught_negative_shift_names_the_value_error(self):
        self.check('shift_uncaught', UNCAUGHT, rc=1, stderr_last='ValueError: negative shift count')


if __name__ == '__main__':
    unittest.main()

"""pre229: constant shifts with a bool operand fold exactly, like CPython.

The review of job pre201 left this pre-existing difference: ``(True << 64) >> 64`` traps with
``integer overflow`` on both builds although the whole expression fits int64 and CPython prints
``1``.  The constant folder did not treat ``True``/``False`` as ints, so the expression was never
folded.  It now accepts bool constants: an in-range whole expression is emitted as one literal, and
a final value outside int64 is refused by name (as every other out-of-int64 constant expression
is).  A shift whose intermediate needs more than the folder's 4096-bit cap is refused by name too.

The remaining name-bound form (``b = True; (b << 64) >> 64``) keeps the pre-existing runtime trap;
it is a separate, non-constant cause.

A later review found that folding bool constants as 0/1 also folded ``&``, ``|`` and ``^`` of two
bools, which CPython evaluates to a bool (``True ^ False`` printed ``1`` and ``type`` ``int``).
Those three operators are now left unfolded when both operands are bool constants, so the runtime
keeps the bool result.
"""
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent
CLI = str(ROOT / "ail_chatgpt.py")

FOLD = r'''print((True << 64) >> 64)
print((True << 63) >> 63)
print((False << 64) >> 64)
print(True >> 64)
print((True << 64) - (1 << 64))
print((-1 << 64) >> 64)
print((-1 << 64) >> 63)
print((True << 64) % 3)
print((True << 64) // (1 << 63))
print((True * 2) << 64 >> 64)
print(True << 0, True >> 0, True ** 0)
print(True + True, True * 3, -True, ~True)
print((1 << 64) >> 64, (2 ** 63) >> 62, (1 << 60) << 2)
'''

CONTAINERS = r'''class Box:
    pass


def show(label, v):
    print(label, v)


def make():
    return (True << 64) >> 64


show("arg", (True << 64) >> 64)
print("list", [(True << 64) >> 64][0])
box = Box()
box.x = (True << 64) >> 64
print("attr", box.x)
print("dict", {"k": (True << 64) >> 64}["k"])
print("return", make())
x = (True << 64) >> 64
y = x
print("alias", x, y)
'''

BOOL_BITS = r'''class Box:
    pass


def show(label, v):
    print(label, v)


def make(flag):
    if flag:
        return True ^ False
    return True & False


print(True ^ False)
print(True | False)
print(True & True)
print(True & False)
print(False | False)
print(type(True ^ False).__name__, type(True | False).__name__, type(True & True).__name__)
print(True ^ 1, 1 ^ True, True | 0, 0 & False, False | 0)
print((True & False) | True, (True ^ True) ^ True)
print((True & False) + 1, (True & False) << 3)
show("arg", True ^ False)
print("list", [(True ^ False), (True | True)][-1])
box = Box()
box.x = True | False
show("attr", box.x)
print("dict", {"k": True & True}["k"])
show("call", make(True))
show("call2", make(False))
'''

NEGATIVE = r'''def out(label, fn):
    try:
        print(label, fn())
    except ValueError as e:
        print(label, type(e).__name__, e)


out("left", lambda: True << -1)
out("right", lambda: True >> -1)
out("zero", lambda: True << 0)
out("false", lambda: False << 100000)
'''

REFUSED = (
    'print(True << 64)\n',
    'print(True << 100000)\n',
    'print((True << 100000) >> 100000)\n',
    'print(-(True << 64))\n',
    'print(True << 64, 1)\n',
    'xs = [1, 2]\nprint(xs[True << 64])\n',
)
REFUSAL = 'an integer constant expression here is outside the signed 64-bit range'


def _run(directory, name, text, general):
    src = Path(directory) / (name + '.py')
    src.write_text(text, encoding='utf-8')
    exe = Path(directory) / ('exe_' + name + ('_g' if general else '_d'))
    env = dict(os.environ, AIL_NO_CACHE='1', AIL_QUIET_FALLBACK='1')
    env.pop('AIL_UNIFIED_FORCE', None)
    if general:
        env['AIL_UNIFIED_FORCE'] = '1'
    built = subprocess.run([sys.executable, '-B', CLI, 'compile', src.name,
                            '--syntax', 'python', '-o', exe.name], cwd=directory,
                           capture_output=True, text=True, timeout=900, env=env)
    if built.returncode != 0:
        return None, built.stdout + built.stderr
    done = subprocess.run([str(exe)], cwd=directory, capture_output=True, text=True, timeout=120)
    return done, ''


def _cpython(directory, name, text):
    src = Path(directory) / (name + '_cpython.py')
    src.write_text(text, encoding='utf-8')
    return subprocess.run([sys.executable, '-B', str(src)], cwd=directory,
                          capture_output=True, text=True, timeout=120,
                          env=dict(os.environ, PYTHONUTF8='1'))


class Pre229Tests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix='ail-pre229-')
        self.dir = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def _same_as_cpython(self, name, text):
        want = _cpython(self.dir, name, text)
        self.assertEqual(want.returncode, 0, want.stderr)
        for general in (False, True):
            got, err = _run(self.dir, name + ('_g' if general else '_d'), text, general)
            self.assertIsNotNone(got, err)
            self.assertEqual((got.returncode, got.stdout), (0, want.stdout),
                             'general=%s\n%s' % (general, got.stderr))

    def test_bool_shift_folds(self):
        self._same_as_cpython('fold', FOLD)
        want = _cpython(self.dir, 'fold_want', FOLD)
        self.assertTrue(want.stdout.startswith(
            '1\n1\n0\n0\n0\n-1\n-2\n1\n2\n2\n1 1 1\n2 3 -1 -2\n1 2 4611686018427387904\n'),
            want.stdout)

    def test_bool_shift_through_containers(self):
        self._same_as_cpython('containers', CONTAINERS)
        want = _cpython(self.dir, 'containers_want', CONTAINERS)
        self.assertIn('arg 1\nlist 1\nattr 1\ndict 1\nreturn 1\nalias 1 1\n', want.stdout)

    def test_bool_bitwise_constants_stay_bool(self):
        self._same_as_cpython('boolbits', BOOL_BITS)
        want = _cpython(self.dir, 'boolbits_want', BOOL_BITS)
        self.assertIn('True\nTrue\nTrue\nFalse\nFalse\nbool bool bool\n', want.stdout)
        self.assertIn('arg True\nlist True\nattr True\ndict True\ncall True\ncall2 False\n',
                      want.stdout)

    def test_bool_negative_shift_count(self):
        self._same_as_cpython('negative', NEGATIVE)
        want = _cpython(self.dir, 'negative_want', NEGATIVE)
        self.assertIn('left ValueError negative shift count', want.stdout)
        self.assertIn('right ValueError negative shift count', want.stdout)

    def test_out_of_range_constant_is_refused_by_name(self):
        for index, text in enumerate(REFUSED):
            for general in (False, True):
                got, err = _run(self.dir, 'refused_%d_%s' % (index, 'g' if general else 'd'),
                                text, general)
                self.assertIsNone(got, 'general=%s compiled:\n%s' % (general, text))
                self.assertIn(REFUSAL, err, 'general=%s\n%s' % (general, err))


if __name__ == '__main__':
    unittest.main()

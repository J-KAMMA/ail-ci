"""pre379: sequence repeat takes a non-int count through __index__, as CPython does.

The pre313 reviewer recorded as pre-existing that ``c *= Idx()`` (a bytearray and a
custom ``__index__`` operand) stopped with TypeError on both builds where CPython
prints ``bytearray(b'xyxy')``.  The general-path runtime's ``ail_op_mul`` /
``ail_op_imul`` now convert a sequence's count through ``__index__`` before the
list/tuple/str branches and before bytes/bytearray/deque reach their own
``__mul__``/``__imul__``.  A count that also defines ``__rmul__`` keeps CPython's
precedence (the reflected method wins), and a left operand with its own
``__mul__`` is not converted.  A plain object without ``__index__`` still raises
the old TypeError, and a non-int result raises ``__index__ returned non-int``.
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
    return subprocess.run([sys.executable, '-B', str(src)], capture_output=True, timeout=120,
                          env=dict(os.environ, PYTHONUTF8='1', PYTHONWARNINGS='ignore'))


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
    return exe, subprocess.run([sys.executable, '-B', CHATGPT, 'compile', src.name, '--syntax', 'python',
                                '-o', exe.name], cwd=directory, capture_output=True, text=True, timeout=900, env=env)


class Pre379Tests(unittest.TestCase):
    def check(self, name, text):
        with tempfile.TemporaryDirectory(prefix='ail-pre379-') as directory:
            want = cpython(directory, name, text)
            for general in (True, False):
                exe, built = build(directory, name, text, general)
                self.assertEqual(built.returncode, 0, (name, general, built.stdout + built.stderr))
                got = subprocess.run([str(exe)], capture_output=True, timeout=120, cwd=directory)
                self.assertEqual(got.stdout, want.stdout, (name, general, got.stderr[-800:]))
                self.assertEqual(got.returncode, want.returncode, (name, general, got.stderr[-800:]))

    def test_index_count_operator(self):
        self.check('operator', '''
from collections import deque


class Idx:
    def __index__(self):
        return 2


class Neg:
    def __index__(self):
        return -1


c = bytearray(b'xy')
alias = c
c *= Idx()
print(c)
print(alias is c)
print(bytearray(b'xy') * Idx())
print(Idx() * bytearray(b'xy'))
print(bytes(b'xy') * Idx())
print(Idx() * bytes(b'xy'))
xs = [1, 2]
xs *= Idx()
print(xs)
print([3] * Idx())
print(Idx() * [4])
s = 'ab'
s *= Idx()
print(s)
print('cd' * Idx())
print(Idx() * 'ef')
t = (1, 2)
t *= Idx()
print(t)
print((3,) * Idx())
q = deque([1, 2])
q *= Idx()
print(q)
print(deque([3]) * Idx())
print(Idx() * deque([4]))

for seq in (bytearray(b'xy'), b'xy', [1, 2], 'ab', (1, 2), bytearray(), b'', [], '', ()):
    print(repr(seq * Neg()))
''')

    def test_index_count_routes(self):
        self.check('routes', '''
class Idx:
    def __index__(self):
        return 2


def scale(v):
    c = bytearray(b'xy')
    c *= v
    return c


class Box:
    pass


class Base:
    def __index__(self):
        return 2


class Child(Base):
    pass


class Override(Base):
    def __index__(self):
        return 3


class Bad:
    def __index__(self):
        return 'nope'


class Plain:
    pass


def main():
    box = Box()
    box.n = Idx()
    d = {'k': Idx()}
    print(scale(Idx()))
    print(scale([Idx()][0]))
    print(scale(box.n))
    print(scale(d['k']))
    print('ab' * box.n)
    print(b'xy' * d['k'])
    print(bytearray(b'xy') * Child())
    print([1] * Child())
    print('ab' * Override())

    for obj in (Bad(), Plain(), 2.5, 'x', None):
        try:
            print(bytearray(b'xy') * obj)
        except TypeError as e:
            print('TypeError', e)
    for seq in ([1, 2], 'ab', b'xy', (1, 2)):
        try:
            print(repr(seq * Bad()))
        except TypeError as e:
            print('TypeError', e)


main()
''')

    def test_index_count_precedence(self):
        self.check('precedence', '''
class Idx:
    def __index__(self):
        return 2


class BothRM:
    def __index__(self):
        return 2

    def __rmul__(self, other):
        return 'RMUL'


class Both:
    def __index__(self):
        return 2

    def __mul__(self, other):
        return 'MUL'


class MulOnly:
    def __mul__(self, other):
        return 'MUL'


class Cust:
    def __mul__(self, other):
        return 'cust'


def main():
    print([1] * BothRM())
    print('ab' * BothRM())
    print(bytearray(b'xy') * BothRM())
    print(Both() * [1])
    print(Both() * bytearray(b'x'))
    print([1] * Both())
    print(bytearray(b'xy') * Both())
    print(MulOnly() * [1])
    print(MulOnly() * bytearray(b'x'))
    print([1] * Idx())
    print(Idx() * [1])
    print(Cust() * Idx())
    try:
        print(Idx() * Cust())
    except TypeError as e:
        print('TypeError', e)


main()
''')


if __name__ == '__main__':
    unittest.main()

"""pre428: multiplication names exception and instance operands by their class.

The pre416 review recorded as pre-existing that ``E() * F()`` printed
``unsupported operand type(s) for *: 'exception' and 'exception'`` on both builds,
where CPython 3.12 names the classes (``'E' and 'F'``).  The general runtime's
multiplication error now uses the object-to-name helper for both operands, copies
each name into its own buffer and caps it at 100 characters as CPython does.
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
    return exe, subprocess.run([sys.executable, '-B', CHATGPT, 'compile', src.name,
                                '--syntax', 'python', '-o', exe.name], cwd=directory,
                               capture_output=True, text=True, timeout=900, env=env)


class Pre428Tests(unittest.TestCase):
    def check(self, name, text):
        with tempfile.TemporaryDirectory(prefix='ail-pre428-') as directory:
            want = cpython(directory, name, text)
            for general in (True, False):
                exe, built = build(directory, name, text, general)
                self.assertEqual(built.returncode, 0, (name, general, built.stdout + built.stderr))
                got = subprocess.run([str(exe)], capture_output=True, timeout=120, cwd=directory)
                self.assertEqual(got.stdout, want.stdout, (name, general, got.stderr[-800:]))
                self.assertEqual(got.returncode, want.returncode, (name, general, got.stderr[-800:]))

    def test_exception_operands_name_their_classes(self):
        self.check('direct', '''
class E(Exception):
    pass


class F(Exception):
    pass


class G(E):
    pass


for label, fn in [('E*F', lambda: E() * F()), ('F*E', lambda: F() * E()),
                  ('E*E', lambda e=E(): e * e), ('G*E', lambda: G() * E()),
                  ('E*G', lambda: E() * G()), ('G*G', lambda: G() * G())]:
    try:
        print(label, fn())
    except Exception as e:
        print(label, type(e).__name__, e)
''')

    def test_routes_to_exception_values(self):
        self.check('routes', '''
class E(Exception):
    pass


class F(Exception):
    pass


class Holder:
    pass


def mul(a, b):
    return a * b


def pick_f():
    return F()


holder = Holder()
holder.f = F()
items = [E(), F()]
mapping = {'f': F()}
alias = E()
for label, fn in [('direct', lambda: alias * F()), ('arg', lambda: mul(E(), F())),
                  ('arg_rev', lambda: mul(F(), E())), ('item', lambda: items[0] * items[1]),
                  ('item_rev', lambda: items[1] * items[0]), ('dict', lambda: mapping['f'] * E()),
                  ('attr', lambda: holder.f * E()), ('return', lambda: E() * pick_f())]:
    try:
        print(label, fn())
    except Exception as e:
        print(label, type(e).__name__, e)
''')

    def test_mixed_operands(self):
        self.check('mixed', '''
class E(Exception):
    pass


class F(Exception):
    pass


for label, fn in [('E*int', lambda: E() * 1), ('int*E', lambda: 1 * E()),
                  ('E*float', lambda: E() * 2.5), ('float*E', lambda: 2.5 * E()),
                  ('E*bool', lambda: E() * True), ('bool*E', lambda: True * E()),
                  ('E*None', lambda: E() * None), ('None*E', lambda: None * E()),
                  ('E*set', lambda: E() * {1}), ('set*E', lambda: {1} * E()),
                  ('E*dict', lambda: E() * {'a': 1}), ('dict*E', lambda: {'a': 1} * E()),
                  ('E*str', lambda: E() * 'x'), ('str*E', lambda: 'x' * E()),
                  ('E*list', lambda: E() * [1]), ('list*E', lambda: [1] * E()),
                  ('E*tuple', lambda: E() * (1,)), ('tuple*E', lambda: (1,) * E()),
                  ('E*bytes', lambda: E() * b'x'), ('bytes*E', lambda: b'x' * E()),
                  ('E*E', lambda: E() * F())]:
    try:
        print(label, fn())
    except Exception as e:
        print(label, type(e).__name__, e)
''')

    def test_long_class_names_are_capped_like_cpython(self):
        for length in (99, 100, 101, 150, 300):
            name = 'K' + 'a' * (length - 1)
            text = ('class %s(Exception):\n    pass\n'
                    'try:\n    %s() * E()\nexcept Exception as e:\n'
                    '    s = str(e)\n'
                    '    print(%d, type(e).__name__, len(s), s[:8], s[-12:])\n'
                    % (name, name, length))
            text = 'class E(Exception):\n    pass\n\n\n' + text
            self.check('long_%d' % length, text)

    def test_ordinary_instances_name_their_classes(self):
        self.check('instances', '''
class A:
    pass


class B(A):
    pass


class Holder:
    pass


def mul(x, y):
    return x * y


holder = Holder()
holder.b = B()
items = [A(), B()]
mapping = {'a': A()}
for label, fn in [('A*B', lambda: A() * B()), ('B*A', lambda: B() * A()),
                  ('A*A', lambda: items[0] * items[0]), ('A*B_item', lambda: items[0] * items[1]),
                  ('B*int', lambda: holder.b * 1), ('int*B', lambda: 1 * holder.b),
                  ('A*dict', lambda: mapping['a'] * {'a': 1}), ('arg', lambda: mul(A(), B()))]:
    try:
        print(label, fn())
    except Exception as e:
        print(label, type(e).__name__, e)
''')

    def test_multiplication_controls_are_unchanged(self):
        self.check('controls', '''
class A:
    pass


class M:
    def __mul__(self, other):
        return 42

    def __rmul__(self, other):
        return 43


class Holder:
    pass


holder = Holder()
holder.x = 5
for left, right in [(2, 3), (True, 4), (2.5, 4), (-2, 5), ('ab', 3), (3, 'ab'),
                    ([1, 2], 2), (2, [1, 2]), ((1, 2), 2), (2, (1, 2)),
                    (holder.x, 3), ([1, 2][0], 4), ({'k': 6}['k'], 7)]:
    print(repr(left * right))
print(M() * 2, 2 * M(), 'ok')
''')
        self.check('no_exception', '''
print(3 * 4, 'ab' * 2, [1] * 2, (1, 2) * 2)
''')

    def test_uncaught_error_exits_one(self):
        text = '''
class E(Exception):
    pass


class F(Exception):
    pass


print('before')
print(E() * F())
print('after')
'''
        with tempfile.TemporaryDirectory(prefix='ail-pre428-') as directory:
            want = cpython(directory, 'uncaught', text)
            for general in (True, False):
                exe, built = build(directory, 'uncaught', text, general)
                self.assertEqual(built.returncode, 0, (general, built.stdout + built.stderr))
                got = subprocess.run([str(exe)], capture_output=True, timeout=120, cwd=directory)
                self.assertEqual(got.stdout, want.stdout, (general, got.stderr[-800:]))
                self.assertEqual(got.returncode, want.returncode, (general, got.stderr[-800:]))


if __name__ == '__main__':
    unittest.main()

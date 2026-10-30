"""A run-time error text that prints a type name names the user's class, as CPython does.

Reported on integ: comparing instances of a class with no ``__lt__`` raised
``TypeError: '<' not supported between instances of 'instance' and 'instance'``; CPython names the
class (``'P' and 'P'``).  A program that prints ``str(e)`` differed silently.  The same held for every
other operand/argument error that quotes a type: unsupported operand types of the binary and unary
operators, ``len()``, ``in``, iteration, ``reversed()``, ``next()``, ``abs()``, ``int()``/``float()``/
``ord()``/``chr()``/``round()``/``divmod()``/``range()``, unhashable types, ``__format__`` and the
``str.join``/``startswith`` argument errors.  The int()/float() texts also took CPython 3.12's wording,
``**`` says ``** or pow()``, and ``x in obj`` says ``argument of type 'P' is not iterable``.

Every statement below runs inside ``try/except Exception`` and prints ``type(e).__name__, e``; the
expected output is CPython's own.  A subclass names the subclass, an instance against an int/str/float/
None/list names both sides in the order CPython does, and two different classes in one message keep their
own names.  Class names of any length (CPython caps some at 100/200 characters; none here are that long)
print whole (the runtime is ASCII-only, so a non-ASCII class name is not a case).  A class defined inside a function is not in the compiler's subset
(``a nested class definition``), so ``__qualname__`` never differs from ``__name__`` in the programs that
build; CPython's tp_name is the ``__name__`` in these texts in any case.

Built the default way and with AIL_UNIFIED_FORCE=1 (the same general-path binary today).  The typed-only
build (AIL_NO_GENERAL=1) refuses these programs (comparing / adding class instances is not in the typed
subset, and TypeError cannot be caught there), so there is nothing to print; the test checks that it
either refuses or prints CPython's text.
"""
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent

STATEMENTS = [
    'p < p',
    'p <= p',
    'p > p',
    'p >= p',
    'p < 1',
    '1 < p',
    "p > 'a'",
    'p <= None',
    'q < p',
    'p >= q',
    '1.5 < p',
    '[1] < p',
    'p + p',
    'p + 1',
    '1 + p',
    'p - 1',
    '1 - p',
    'p * 2',
    '2 * p',
    'p / 1',
    '1 / p',
    'p // 1',
    'p % 1',
    'p ** 2',
    'p & 1',
    'p | 1',
    'p ^ 1',
    'p << 1',
    'p >> 1',
    '1 << p',
    'q + p',
    "'a' + p",
    "p + 'a'",
    '[1] + p',
    '(1,) + p',
    "'a' * p",
    '[1] * p',
    '-p',
    '+p',
    '~p',
    'abs(p)',
    'len(p)',
    'iter(p)',
    'list(p)',
    'tuple(p)',
    'set(p)',
    'sorted(p)',
    'sum(p)',
    'dict(p)',
    'enumerate(p)',
    'reversed(p)',
    'next(p)',
    '1 in p',
    "'a' in 'abc' + str(0) if False else p in 'abc'",
    'p[1]',
    'p[1:2]',
    "p['k'] = 1",
    'p[1] = 2',
    'del p[1]',
    'p()',
    'q()',
    'for _ in p: pass',
    'a, b = p',
    'max(p, p)',
    'min(p, p)',
    'max(p)',
    'sorted([p, p])',
    '[p, p].sort()',
    '{p2: 1}',
    '{p2}',
    'hash(p2)',
    'set([p2])',
    'd = {}; d[p2] = 1',
    'int(p)',
    'float(p)',
    'int(p, 2)',
    "int('5', p)",
    'ord(p)',
    'chr(p)',
    'round(p)',
    'round(1.5, p)',
    'divmod(p, 1)',
    'divmod(1, p)',
    'range(p)',
    '[1, 2][p]',
    "'abc'[p]",
    '(1, 2)[p]',
    "'%d' % p",
    "'{:d}'.format(p)",
    "'{:>5}'.format(p)",
    "format(p, 'x')",
    "f'{p:d}'",
    "''.join([p])",
    "'a'.startswith(p)",
    "'a'.split(p)",
    "'abc'.find(p)",
    "'abc'.replace(p, 'x')",
    "p in 'abc'",
    'p.x',
    'q.x',
    'p.x = 1 if False else q.nope',
    'bool(p) + p',
    '[1, 2][p:]',
    '[1, 2].extend(p)',
    '[1, 2] * p',
    '(1, 2) * p',
    "'a' % p + p",
    'bytes(p)',
    'str(p) + p',
    'len(q)',
    'q < q',
    'q < 1',
    'abs(q)',
    'callable(p) + p',
    'sum([p, p])',
    'sum([1, p])',
    'sum([p], 1)',
    'all(p)',
    'any(p)',
    'map(len, p)',
    'filter(None, p)',
    'getattr(p, p)',
    'setattr(p, 1, 2)',
    'hasattr(p, 1)',
    "'abc'.center(p)",
    "'abc'.zfill(p)",
    "'a' < p",
    "p < 'a'",
    '(1, 2) < p',
    'p == p < p',
    'dict(a=1).get(p2)',
    '{1: 2}[p2]',
    '{1: 2}.get(p2)',
    'sorted([3, 1], key=p)',
    "'abc'.encode(p)",
    "chr(p) + 'x'",
    'hex(p)',
    'bin(p)',
    'oct(p)',
    'pow(p, 2)',
    'pow(2, p)',
    'list(range(3))[p]',
    "'abc'.strip(p)",
    "'abc'.count(p)",
    "'abc' in p",
    "'abc'.index(p)",
    "'abc'.endswith(p)",
    "'%d %d' % (1, p)",
    "'%x' % p",
    "'%f' % p",
    "'%c' % p",
    "'{}'.format(p) + p",
    "'{:5.2f}'.format(p)",
    "'{:,}'.format(p)",
    "'{:s}'.format(p)",
    "'{:^3}'.format(p)",
    'format(1, p)',
    'format(p, p)',
    "'abc'.ljust(p)",
    "'abc'[::p]",
    '[1,2,3][::p]',
    '[1,2,3][p::]',
    '[1,2,3][:p]',
    "'abc'[p:]",
    "'abc'[:p]",
    'range(1, p)',
    'range(1, 2, p)',
    "'abc' * 1.5",
    '[0] * 1.5',
    'list(p) + [1]',
    "'a'.join([1, p])",
    "'a'.join(['a', p])",
    "'a'.join([p, 'a'])",
    "'a'.join((1,))",
    "'abc'.split('b', p)",
    "'abc'.ljust(2, p)",
    'dict([(1, 2, 3)])',
    'list(map(p, [1]))',
    'list(filter(p, [1]))',
    'frozenset(p)',
    'frozenset([p2])',
    "'abc'.partition(p)",
    "'{0}{1}'.format(p)",
    'min(p, 1)',
    'max(1, p)',
    'max([p, 1])',
    'min([1, p])',
    'min([p, p], key=len)',]

MAIN_PRELUDE = '''
class P:
    pass


class Q(P):
    pass


class P2:
    def __eq__(self, o):
        return True


def main():
    p = P()
    q = Q()
    p2 = P2()
'''


def tryblock(i, stmt):
    lines = []
    lines.append('    try:')
    for part in stmt.split('; '):
        lines.append('        ' + part)
    lines.append('        print(%d, "no error")' % i)
    lines.append('    except Exception as e:')
    lines.append('        print(%d, type(e).__name__, e)' % i)
    return lines


def wrap(prelude, stmts):
    out = [prelude.rstrip('\n')]
    for i, s in enumerate(stmts):
        out.extend(tryblock(i, s))
    out.append('')
    out.append('main()')
    return '\n'.join(out) + '\n'


CASES = {}
CASES['operands_and_calls'] = wrap(MAIN_PRELUDE, STATEMENTS)

# a class that defines a special method makes the compiler patch the operator runtime (dunderrt): the texts
# for the operands that class does not handle must still name the classes
CASES['with_dunders'] = wrap('''
class A:
    def __add__(self, other):
        return 1

    def __neg__(self):
        return 2


class B:
    pass


class C(A):
    pass


class Seq:
    def __len__(self):
        return 3


def main():
    a = A()
    b = B()
    c = C()
    s = Seq()
''', [
    'a < b', 'b < a', 'b < b', 'c < a', 'a + b', 'b + a', 'b + 1', '1 + b', 'a - b', 'c - 1', '1 - c', 'a * b',
    'b * c', 'c / 1', 'a ** 2', '-b', '+a', '~a', 'abs(c)', 'len(b)', 'len(a)', 'iter(s)', 'for _ in b: pass',
    'int(b)', 'float(c)', 'ord(b)', '1 in b', 'b in s', 'b[0]', 'b()', 'divmod(b, 1)', 'round(b)', 'hash([b])',
    '{b: 1, [1]: 2}', "'%d' % b", "'{:d}'.format(b)", "''.join([b])", "'abc'.startswith((b,))",
])

# an exception subclass is a class instance as well
CASES['exception_class'] = wrap('''
class Boom(Exception):
    pass


class Bang(Boom):
    pass


def main():
    e1 = Boom('x')
    e2 = Bang('y')
''', ['e1 < e2', 'e2 > e1', 'e1 + 1', '1 + e2', 'e1 * e2', '-e1', 'len(e1)', 'int(e2)', 'e1 < 1', 'e2 <= None'])

LONG = 'L' * 40
LONG2 = 'M' * 70
CASES['long_names'] = wrap('''
class %(a)s:
    pass


class %(b)s(%(a)s):
    pass


def main():
    p = %(a)s()
    q = %(b)s()
''' % {'a': LONG, 'b': LONG2}, ['p < q', 'q + p', 'p + 1', '1 - q', '-p', 'len(q)', 'iter(p)', 'int(q)', 'ord(p)',
                                 'abs(q)', 'p()', 'p[0]', '1 in q', 'next(p)', 'reversed(q)', 'float(p)'])

UNCAUGHT = {
    'uncaught_lt': 'class P:\n    pass\n\nprint(P() < P())\n',
    'uncaught_add': 'class P:\n    pass\n\nclass Q:\n    pass\n\nprint(P() + Q())\n',
    'uncaught_len': 'class Widget:\n    pass\n\nprint(len(Widget()))\n',
}


def compile_source(directory, name, source, mode):
    path = Path(directory) / (name + '.py')
    path.write_text(source, encoding='utf-8')
    env = dict(os.environ, AIL_NO_CACHE='1', AIL_QUIET_FALLBACK='1')
    for key in ('AIL_UNIFIED_FORCE', 'AIL_NO_GENERAL'):
        env.pop(key, None)
    if mode == 'force':
        env['AIL_UNIFIED_FORCE'] = '1'
    elif mode == 'typed':
        env['AIL_NO_GENERAL'] = '1'
    exe = Path(directory) / (name + '_' + mode)
    built = subprocess.run([sys.executable, '-B', str(ROOT / 'ail_chatgpt.py'), 'compile', path.name,
                            '--syntax', 'python', '-o', exe.name], cwd=directory,
                           capture_output=True, text=True, timeout=900, env=env)
    return built, exe


def run_cpython(directory, name, source):
    path = Path(directory) / (name + '_cpython.py')
    path.write_text(source, encoding='utf-8')
    ran = subprocess.run([sys.executable, '-B', path.name], cwd=directory, capture_output=True,
                         text=True, timeout=120, encoding='utf-8')
    return ran.stdout.replace('\r\n', '\n'), ran.stderr.replace('\r\n', '\n'), ran.returncode


def last_line(text):
    lines = [line for line in text.splitlines() if line.strip()]
    return lines[-1] if lines else ''


class CmpClassName(unittest.TestCase):
    def test_errors_name_the_class(self):
        for slug, source in CASES.items():
            with tempfile.TemporaryDirectory(prefix='ail-cmpcls-') as directory:
                expected, _, status = run_cpython(directory, slug, source)
            self.assertIn('TypeError', expected)
            for mode in ('default', 'force'):
                with self.subTest(slug=slug, mode=mode), \
                        tempfile.TemporaryDirectory(prefix='ail-cmpcls-') as directory:
                    built, exe = compile_source(directory, slug, source, mode)
                    self.assertEqual(built.returncode, 0, (slug, mode, built.stdout + built.stderr))
                    ran = subprocess.run([str(exe)], cwd=directory, capture_output=True, text=True,
                                         timeout=120, encoding='utf-8')
                    self.assertEqual(ran.returncode, status, ran.stdout + ran.stderr)
                    self.assertEqual(ran.stdout.replace('\r\n', '\n'), expected, ran.stderr)

    def test_uncaught_stderr_names_the_class(self):
        for slug, source in UNCAUGHT.items():
            with tempfile.TemporaryDirectory(prefix='ail-cmpcls-') as directory:
                _, cpython_err, status = run_cpython(directory, slug, source)
            for mode in ('default', 'force'):
                with self.subTest(slug=slug, mode=mode), \
                        tempfile.TemporaryDirectory(prefix='ail-cmpcls-') as directory:
                    built, exe = compile_source(directory, slug, source, mode)
                    self.assertEqual(built.returncode, 0, (slug, mode, built.stdout + built.stderr))
                    ran = subprocess.run([str(exe)], cwd=directory, capture_output=True, text=True,
                                         timeout=120, encoding='utf-8')
                    self.assertEqual(ran.returncode, status, ran.stdout + ran.stderr)
                    self.assertEqual(last_line(ran.stderr), last_line(cpython_err), ran.stderr)

    def test_typed_only_refuses_or_agrees(self):
        slug, source = 'uncaught_lt', UNCAUGHT['uncaught_lt']
        with tempfile.TemporaryDirectory(prefix='ail-cmpcls-') as directory:
            _, cpython_err, status = run_cpython(directory, slug, source)
        with tempfile.TemporaryDirectory(prefix='ail-cmpcls-') as directory:
            built, exe = compile_source(directory, slug, source, 'typed')
            if built.returncode != 0 or not exe.exists():
                return                     # not in the typed subset: nothing to print
            ran = subprocess.run([str(exe)], cwd=directory, capture_output=True, text=True,
                                 timeout=120, encoding='utf-8')
            self.assertEqual(ran.returncode, status, ran.stdout + ran.stderr)
            self.assertEqual(last_line(ran.stderr), last_line(cpython_err), ran.stderr)


if __name__ == '__main__':
    unittest.main()

"""Class-hierarchy reach: mixed isinstance tuples and static issubclass (docs/design/CLASS_REACH.md).

The 30 measurement programs of CLASS_REACH.md are summarised there; this module pins the two
constructs that were refused on the typed path before the change:

R1  `isinstance(x, (B, int))` / `(int, B)` / `(D, B)` on a class of a hierarchy: the typed path
    and the general path print CPython's answers, including a value reaching the test through a
    parameter, a list item, an attribute and a dict value, an unrelated class, an object target
    and a subclass two levels down.
R2  `issubclass(C, A)` / `(C, B)` / `(D, object)` / builtin types: the typed path folds the
    statically known answer and prints True/False; the general path refuses by name (it has no
    issubclass), which is a named refusal, not a wrong answer.
R3  the boundaries: a class value in a variable and an unknown class name are refused by name on
    the typed path (not folded to a wrong bool), and a user-defined `issubclass` is not touched.
"""
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent
HAVE_CC = shutil.which('gcc') is not None

MIXED = '''class A:
    def __init__(self, x: int) -> None:
        self.x = x


class B(A):
    pass


class C(B):
    pass


class D:
    def __init__(self) -> None:
        self.d = 1


class Holder:
    def __init__(self, n: A) -> None:
        self.n = n


def check(x: A) -> None:
    print(isinstance(x, (B, int)), isinstance(x, (int, B)))
    print(isinstance(x, (B, str)), isinstance(x, (D, B)))


def main() -> None:
    xs: list[A] = [A(1), B(2), C(3)]
    for x in xs:
        check(x)
    y = xs[1]
    x0 = xs[0]
    print(isinstance(y, (C, int)), isinstance(x0, (C, int)))
    holder = B(4)
    print(isinstance(holder, (C, str)))
    h = Holder(C(6))
    print(isinstance(h.n, (C, str)))
    d0 = D()
    print(isinstance(d0, (B, int)), isinstance(d0, (B, D)))


main()
'''

ISSUB = '''class A:
    def __init__(self, x: int) -> None:
        self.x = x


class B(A):
    pass


class C(B):
    pass


class D:
    def __init__(self) -> None:
        self.d = 1


def main() -> None:
    print(issubclass(C, A), issubclass(C, B), issubclass(C, C), issubclass(A, C))
    print(issubclass(C, D), issubclass(D, A), issubclass(C, object), issubclass(D, object))
    print(issubclass(C, (D, B)), issubclass(C, (D, int)), issubclass(C, (A, int)))
    print(issubclass(bool, int), issubclass(int, object), issubclass(list, (A, list)))
    print(issubclass(int, A), issubclass(A, int), issubclass(D, (int, object)))
    b = issubclass(B, A)
    print(b, not b, issubclass(C, A) and issubclass(C, B))


main()
'''

DYNAMIC = '''class A:
    def __init__(self, x: int) -> None:
        self.x = x


class B(A):
    pass


def main() -> None:
    cls = B
    print(issubclass(cls, A))


main()
'''

SHADOW = '''class A:
    def __init__(self, x: int) -> None:
        self.x = x


class B(A):
    pass


def issubclass(a: int, b: int) -> int:
    return a + b


def main() -> None:
    print(issubclass(1, 2))


main()
'''

OBJECT = '''class A:
    def __init__(self, x: int) -> None:
        self.x = x


class B(A):
    pass


def main() -> None:
    a = A(1)
    b = B(2)
    print(isinstance(a, (B, object)), isinstance(b, (B, object)))


main()
'''

UNKNOWN = '''class A:
    def __init__(self, x: int) -> None:
        self.x = x


class B(A):
    pass


def main() -> None:
    print(issubclass(B, Nope))


main()
'''


def run_cpython(directory, text, name):
    source = Path(directory, name + '.py')
    source.write_text(text, encoding='utf-8')
    return subprocess.run([sys.executable, str(source)], capture_output=True, text=True,
                          timeout=300, encoding='utf-8')


def build(directory, text, name, typed):
    source, exe = Path(directory, name + ('.py' if typed else '_g.py')), Path(directory, name + ('_t' if typed else '_g'))
    source.write_text(text, encoding='utf-8')
    env = dict(__import__('os').environ, AIL_NO_CACHE='1', AIL_IR='0')
    if typed:
        env['AIL_NO_GENERAL'] = '1'
        cmd = [sys.executable, '-B', str(ROOT / 'ail_chatgpt.py'), 'compile', source.name, '--syntax', 'python',
               '-o', exe.name]
    else:
        env.pop('AIL_NO_GENERAL', None)
        cmd = [sys.executable, '-B', str(ROOT / 'python' / 'pkg-v12' / 'pyc.py'), exe.name, '--file', source.name,
               '--general-only']
    return subprocess.run(cmd, cwd=directory, capture_output=True, text=True, timeout=900, env=env), exe


def run_exe(exe):
    return subprocess.run([str(exe)], capture_output=True, text=True, timeout=300, encoding='utf-8')


@unittest.skipUnless(HAVE_CC, 'no C compiler')
class ClassReachTests(unittest.TestCase):
    def three_way(self, text, name):
        with tempfile.TemporaryDirectory(prefix='ail-clsreach-') as d:
            ref = run_cpython(d, text, name + '_cp')
            self.assertEqual(ref.returncode, 0, ref.stderr)
            for typed in (True, False):
                build_res, exe = build(d, text, name, typed)
                self.assertEqual(build_res.returncode, 0, name + (': ' if typed else ' (general): ')
                                 + build_res.stdout + build_res.stderr)
                out = run_exe(exe)
                self.assertEqual((out.returncode, out.stdout), (0, ref.stdout), name)

    def test_mixed_isinstance_tuple(self):
        self.three_way(MIXED, 'mixed')

    def test_static_issubclass_is_typed(self):
        with tempfile.TemporaryDirectory(prefix='ail-clsreach-') as d:
            ref = run_cpython(d, ISSUB, 'issub_cp')
            self.assertEqual(ref.returncode, 0, ref.stderr)
            res, exe = build(d, ISSUB, 'issub', True)
            self.assertEqual(res.returncode, 0, res.stdout + res.stderr)
            self.assertNotIn('general path', res.stderr)
            out = run_exe(exe)
            self.assertEqual((out.returncode, out.stdout), (0, ref.stdout))
            gres, _ = build(d, ISSUB, 'issub', False)
            self.assertNotEqual(gres.returncode, 0)
            self.assertIn('issubclass', gres.stdout + gres.stderr)

    def test_issubclass_boundaries(self):
        for name, text, words in (
                ('dynamic', DYNAMIC, 'read before it is assigned'),
                ('unknown', UNKNOWN, 'issubclass')):
            with self.subTest(case=name), tempfile.TemporaryDirectory(prefix='ail-clsreach-') as d:
                res, exe = build(d, text, name, True)
                self.assertNotEqual(res.returncode, 0)
                self.assertIn(words, res.stdout + res.stderr)
                self.assertFalse(exe.exists())

    def test_object_in_a_mixed_tuple_is_typed(self):
        with tempfile.TemporaryDirectory(prefix='ail-clsreach-') as d:
            ref = run_cpython(d, OBJECT, 'object_cp')
            self.assertEqual(ref.returncode, 0, ref.stderr)
            res, exe = build(d, OBJECT, 'object', True)
            self.assertEqual(res.returncode, 0, res.stdout + res.stderr)
            out = run_exe(exe)
            self.assertEqual((out.returncode, out.stdout), (0, ref.stdout))
            gres, _ = build(d, OBJECT, 'object', False)
            self.assertNotEqual(gres.returncode, 0)
            self.assertIn('isinstance', gres.stdout + gres.stderr)

    def test_user_issubclass_is_not_folded(self):
        self.three_way(SHADOW, 'shadow')


if __name__ == '__main__':
    unittest.main()

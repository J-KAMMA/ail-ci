"""Differences from CPython 3.12 that printed a different answer without a diagnostic (DIFFERENCES C39-C42, t426).

S1  C39: an int handed to a float-annotated parameter, constructor parameter (dataclass fields and defaults
    included), method parameter or field store is refused by name on the typed path (the typed build would show
    3.0 where CPython keeps the int and shows 3); the default build falls back to the general path and prints
    what CPython prints.  Floats, and ints converted by float(), still build on the typed path.
S2  C40: a class instance added to a set is refused by name on the typed path (its table keyed the instance by
    address without a reference, so freed addresses were reused and 1000 instances became 2 elements); the default
    build prints what CPython prints.  Sets of ints are untouched.
S3  C41: str.format evaluates its arguments left to right, once each, before any field (typed path, both IR modes);
    an argument that cannot be staged is refused by name.
S4  C42: on the general path `==` / `!=` call the user's __eq__ / __ne__ whatever the other operand is (None
    included), `!=` inverts __eq__ when there is no __ne__, an exception raised by __eq__ propagates out of `==`,
    `!=` and `in`, sets and dicts keyed by instances with __hash__ / __eq__ work, and a slice through __getitem__
    is refused by name.
S5  corpus3 t426: `except ParseError` no longer catches RangeError (user exception codes 30 and 31 were taken for
    URLError and HTTPError, with the urllib classes absent).
"""
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path[:0] = [str(ROOT / 'python' / 'pkg-v12'), str(ROOT)]
CLI = str(ROOT / 'ail_chatgpt.py')


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix='ail-silent5-')
        self.dir = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def cpython(self, source, stdin=''):
        path = self.dir / 'cpython_main.py'
        path.write_text(source, encoding='utf-8')
        return subprocess.run([sys.executable, '-B', str(path)], input=stdin.encode(), capture_output=True, timeout=120)

    def build(self, source, ir='0', typed=False, out='out'):
        entry = self.dir / 'main.py'
        entry.write_text(source, encoding='utf-8')
        exe = self.dir / ('%s_ir%s_%s' % (out, ir, 'typed' if typed else 'default'))
        if exe.exists():
            exe.unlink()
        env = dict(os.environ, AIL_IR=ir)
        env.pop('AIL_NO_GENERAL', None)
        if typed:
            env['AIL_NO_GENERAL'] = '1'
        built = subprocess.run([sys.executable, '-B', CLI, 'compile', str(entry), '--syntax', 'python', '-o', str(exe)],
                               cwd=self.dir, capture_output=True, text=True, timeout=900, env=env)
        return built, exe

    def same(self, source, typed=False, irs=('0', '1'), stdin=''):
        """Built (on the typed path alone, or by default), the program prints what CPython prints and exits alike."""
        expected = self.cpython(source, stdin)
        for ir in irs:
            built, exe = self.build(source, ir, typed)
            self.assertEqual(built.returncode, 0, 'AIL_IR=%s: %s' % (ir, built.stderr))
            ran = subprocess.run([str(exe)], input=stdin.encode(), capture_output=True, timeout=120)
            self.assertEqual(ran.stdout.decode(), expected.stdout.decode(), 'AIL_IR=%s' % ir)
            self.assertEqual(ran.returncode, expected.returncode, 'AIL_IR=%s' % ir)
            if expected.returncode:
                last = expected.stderr.decode().strip().splitlines()[-1].split(':')[0]
                self.assertIn(last, ran.stderr.decode(), 'AIL_IR=%s' % ir)
        return expected.stdout.decode()

    def refused(self, source, *needles, irs=('0', '1')):
        """The typed path refuses by name (exit 3, no traceback)."""
        for ir in irs:
            built, _ = self.build(source, ir, typed=True)
            self.assertEqual(built.returncode, 3, 'AIL_IR=%s: %s' % (ir, built.stdout + built.stderr))
            self.assertNotIn('Traceback', built.stderr)
            for needle in needles:
                self.assertIn(needle, built.stderr)

    def both(self, source, *needles):
        """Refused on the typed path, and the default build prints what CPython prints."""
        self.refused(source, *needles)
        return self.same(source)


FLOAT_PARAM = '''
def f(x: float) -> None:
    print(x)

def main() -> None:
    f(3)
    f(3.5)
    n = len("abc")
    f(float(n))
    f(n / 2)

main()
'''

FLOAT_CTOR = '''
from dataclasses import dataclass

@dataclass
class D:
    x: float
    y: float = 2

class P:
    def __init__(self, x: float) -> None:
        self.x = x

    def show(self, k: float) -> None:
        print(k, self.x)

def main() -> None:
    d = D(4)
    print(d)
    print(D(1.5, 3))
    p = P(5)
    p.show(6)
    p.x = 7
    print(p.x)

main()
'''


class FloatSlotTests(Base):
    def test_int_argument_of_float_parameter(self):
        out = self.both(FLOAT_PARAM.replace('    f(3.5)\n', '    f(3.5)\n    f(3)\n'), 'annotated float')
        self.assertEqual(out.splitlines()[:3], ['3', '3.5', '3'])

    def test_float_arguments_build_on_the_typed_path(self):
        source = FLOAT_PARAM.replace('    f(3)\n', '    f(3.0)\n')
        self.assertEqual(self.same(source, typed=True).splitlines(), ['3.0', '3.5', '3.0', '1.5'])

    def test_constructors_methods_and_field_stores(self):
        out = self.both(FLOAT_CTOR, 'annotated float')
        self.assertEqual(out.splitlines()[0], 'D(x=4, y=2)')

    def test_each_float_slot_is_refused(self):
        for name, source in (
                ('constructor parameter', 'class P:\n    def __init__(self, x: float) -> None:\n        self.x = x\n\n'
                 'def main() -> None:\n    p = P(4)\n    print(p.x)\n\nmain()\n'),
                ('default value', 'def f(a: float, b: float = 3) -> None:\n    print(a, b)\n\n'
                 'def main() -> None:\n    f(1.5)\n\nmain()\n'),
                ('field store', 'class P:\n    def __init__(self, x: float) -> None:\n        self.x = x\n\n'
                 'def main() -> None:\n    p = P(4.5)\n    p.x = 6\n    print(p.x)\n\nmain()\n'),
                ('dataclass field store', 'from dataclasses import dataclass\n\n@dataclass\nclass D:\n    x: float\n\n'
                 'def main() -> None:\n    d = D(4.5)\n    d.x = 7\n    print(d.x)\n\nmain()\n'),
                ('int variable', 'def f(a: float) -> None:\n    print(a)\n\n'
                 'def main() -> None:\n    n = len("abc")\n    f(n)\n\nmain()\n')):
            with self.subTest(name):
                self.both(source, 'annotated float')

    def test_the_brace_surface_keeps_its_conversion(self):
        source = 'fn take(value:float)->float {return value;}\nfn main()->int {if take(2)!=2.0 {return 1;} print(1);return 0;}\n'
        entry = self.dir / 'main.ail'
        entry.write_text(source, encoding='utf-8')
        exe = self.dir / 'brace'
        built = subprocess.run([sys.executable, '-B', CLI, 'compile', str(entry), '-o', str(exe)],
                               cwd=self.dir, capture_output=True, text=True, timeout=900)
        self.assertEqual(built.returncode, 0, built.stderr)
        self.assertEqual(subprocess.run([str(exe)], capture_output=True, timeout=60).stdout.decode(), '1\n')


SET_OF_INSTANCES = '''
class P:
    def __init__(self, i: int) -> None:
        self.i = i

def main() -> None:
    s = set()
    for i in range(1000):
        s.add(P(i))
    print(len(s))
    t = set()
    keep = []
    for i in range(10):
        p = P(i)
        keep.append(p)
        t.add(p)
        t.add(p)
    print(len(t), keep[3] in t, P(3) in t)

main()
'''


class InstanceSetTests(Base):
    def test_set_of_instances(self):
        out = self.both(SET_OF_INSTANCES, 'class instance as a set element')
        self.assertEqual(out.splitlines(), ['1000', '10 True False'])

    def test_discard_and_membership_of_instances(self):
        source = ('class P:\n    def __init__(self, i: int) -> None:\n        self.i = i\n\n'
                  'def main() -> None:\n    s = set()\n    p = P(1)\n    s.add(p)\n    print(p in s, P(1) in s)\n'
                  '    s.discard(p)\n    print(len(s))\n\nmain()\n')
        self.assertEqual(self.both(source, 'set element').splitlines(), ['True False', '0'])

    def test_dict_keys_of_instances_stay_refused(self):
        source = ('class P:\n    def __init__(self, i: int) -> None:\n        self.i = i\n\n'
                  'def main() -> None:\n    d = {}\n    for i in range(1000):\n        d[P(i)] = i\n    print(len(d))\n\nmain()\n')
        self.assertEqual(self.both(source, 'dict key').splitlines(), ['1000'])

    def test_sets_of_ints_still_build_on_the_typed_path(self):
        source = ('def main() -> None:\n    s = set()\n    for i in range(100):\n        s.add(i % 7)\n'
                  '    print(len(s), 3 in s, 9 in s)\n\nmain()\n')
        self.assertEqual(self.same(source, typed=True), '7 True False\n')


FORMAT_ORDER = '''
def f(x: int) -> int:
    print("f", x)
    return x

def g(s: str) -> str:
    print("g", s)
    return s

def main() -> None:
    print("{1} {0}".format(f(1), f(2)))
    print("{0}{0}{1}".format(f(3), f(4)))
    print("{1:>3}|{0:<3}|".format(f(5), f(6)))
    print("{1}".format(f(7), f(8)))
    print("{} {}".format(f(9), f(10)))
    print("%d %d" % (f(11), f(12)))
    print(f"{f(13)} {f(14):>4}")
    print("{1}-{0}".format(g("a"), g("b")))
    print("{1!r} {0}".format(g("c"), g("d")))
    a = "{2} {0} {1}".format(f(15), g("e"), f(16))
    print(a)
    x = 5
    print("{1} {0}".format(x, x + 1))
    print("{0} {0}".format(len("abc")))

main()
'''


class FormatOrderTests(Base):
    def test_arguments_are_evaluated_left_to_right_once(self):
        out = self.same(FORMAT_ORDER, typed=True)
        self.assertEqual(out.splitlines()[:5], ['f 1', 'f 2', '2 1', 'f 3', 'f 4'])

    def test_default_build_agrees(self):
        self.same(FORMAT_ORDER)

    def test_a_bool_argument_is_refused_when_it_would_be_staged(self):
        source = ('def b(x: int) -> bool:\n    print("b", x)\n    return x > 0\n\n'
                  'def main() -> None:\n    print("{1} {0}".format(b(1), b(2)))\n\nmain()\n')
        built, _ = self.build(source, '0', typed=True)
        if built.returncode == 0:
            self.same(source, typed=True)
        else:
            self.assertEqual(built.returncode, 3)
            self.assertIn('out of order', built.stderr)


EQ_NONE = '''
class P:
    def __init__(self, x: int) -> None:
        self.x = x

    def __eq__(self, other):
        return self.x == other.x

class G:
    def __init__(self, x: int) -> None:
        self.x = x

    def __eq__(self, other):
        if other is None:
            return False
        return self.x == other.x

class Q:
    def __init__(self, x: int) -> None:
        self.x = x

    def __eq__(self, other):
        print("eq called", other)
        return True

def f(p, q):
    if p == None:
        return 1
    return 2

def main() -> None:
    a = P(1)
    try:
        print("eq", a == None)
    except AttributeError as e:
        print("eq", "AttributeError", e)
    try:
        print("ne", a != None)
    except AttributeError as e:
        print("ne", "AttributeError", e)
    try:
        print("rev", None == a)
    except AttributeError as e:
        print("rev", "AttributeError", e)
    try:
        print("revne", None != a)
    except AttributeError as e:
        print("revne", "AttributeError", e)
    try:
        print("int", a == 3)
    except AttributeError as e:
        print("int", "AttributeError", e)
    try:
        print("str", a == "s")
    except AttributeError as e:
        print("str", "AttributeError", e)
    try:
        print("call", f(P(1), None))
    except AttributeError as e:
        print("call", "AttributeError", e)
    try:
        print("list", [a] == [None])
    except AttributeError as e:
        print("list", "AttributeError", e)
    try:
        print("in", None in [a])
    except AttributeError as e:
        print("in", "AttributeError", e)
    g = G(1)
    print(g == None, g != None, None == g, g == G(1), g != G(1), g != G(2))
    q = Q(2)
    print(q == None)
    print(q != None)
    print(None == q)
    print(q != 5)

main()
'''

NE_RULES = '''
class P:
    def __init__(self, x: int) -> None:
        self.x = x

    def __eq__(self, other):
        return self.x == other.x

class N:
    def __init__(self, x: int) -> None:
        self.x = x

    def __eq__(self, other):
        return self.x == other.x

    def __ne__(self, other):
        print("ne called")
        return self.x != other.x

class S(P):
    pass

def main() -> None:
    a = P(1)
    b = P(1)
    print(a != b, a == b, not (a == b))
    c = N(1)
    d = N(2)
    print(c != d, c == d)
    e = S(1)
    print(e != a, a != e)
    xs = [P(1), P(2)]
    print(xs[0] != xs[1], xs[0] != P(1), xs[0] == xs[1])
    print(xs == [P(1), P(2)], xs != [P(1), P(2)], xs != [P(1), P(3)])

main()
'''

HASHED = '''
class H:
    def __init__(self, x: int) -> None:
        self.x = x

    def __hash__(self):
        return hash(self.x % 3)

class E:
    def __init__(self, x: int) -> None:
        self.x = x

    def __eq__(self, other):
        return self.x == other.x

class HE:
    def __init__(self, x: int) -> None:
        self.x = x

    def __eq__(self, other):
        return isinstance(other, HE) and self.x == other.x

    def __hash__(self):
        return hash(self.x)

def main() -> None:
    s = set()
    for i in range(10):
        s.add(H(i))
    print(len(s))
    h = H(1)
    s2 = {h}
    print(h in s2, H(1) in s2)
    try:
        t = {E(1)}
        print("no error", len(t))
    except TypeError as e:
        print("TypeError", e)
    try:
        d = {E(1): 2}
        print("no error", len(d))
    except TypeError as e:
        print("TypeError", e)
    u = set()
    for i in range(10):
        u.add(HE(i % 4))
    print(len(u), HE(2) in u, HE(7) in u)
    u.discard(HE(2))
    print(len(u), sorted(x.x for x in u))
    d = {}
    for i in range(10):
        d[HE(i % 3)] = d.get(HE(i % 3), 0) + 1
    print(len(d), d[HE(0)], d[HE(1)], d[HE(2)])
    print(len({HE(1), HE(1), HE(2)}))

main()
'''

GETITEM = '''
class V:
    def __init__(self, xs: list) -> None:
        self.xs = xs

    def __getitem__(self, i):
        return self.xs[i]

def main() -> None:
    v = V([1, 2, 3])
    print(v[0], v[-1])
    print(v[1:2])

main()
'''


class GeneralPathTests(Base):
    def test_eq_with_none_calls_the_user_method(self):
        out = self.same(EQ_NONE)
        self.assertIn('eq AttributeError', out)

    def test_ne_asks_ne_or_inverts_eq(self):
        out = self.same(NE_RULES)
        self.assertTrue(out.startswith('False True False\nne called'))

    def test_hash_and_eq_in_sets_and_dicts(self):
        self.same(HASHED)

    def test_the_uncaught_error_of_eq_with_none(self):
        source = ('class P:\n    def __init__(self, x: int) -> None:\n        self.x = x\n\n'
                  '    def __eq__(self, other):\n        return self.x == other.x\n\n'
                  'def main() -> None:\n    print("before")\n    print(P(1) == None)\n\nmain()\n')
        self.same(source)

    def test_slice_through_getitem_is_refused_by_name(self):
        built, _ = self.build(GETITEM, '0')
        self.assertEqual(built.returncode, 3, built.stderr)
        self.assertIn('slice', built.stderr)
        self.assertNotIn('Traceback', built.stderr)
        self.same(GETITEM.replace('    print(v[1:2])\n', ''))

    def test_slice_of_an_unresolved_receiver_raises_by_name(self):
        source = ('class V:\n    def __init__(self, xs: list) -> None:\n        self.xs = xs\n\n'
                  '    def __getitem__(self, i):\n        return self.xs[i]\n\n'
                  'def first(v, k):\n    return v[0:k]\n\n'
                  'def main() -> None:\n    print(first([5, 6, 7], 2))\n    try:\n        print(first(V([1, 2]), 1))\n'
                  '    except NotImplementedError as e:\n        print("not supported")\n\nmain()\n')
        built, exe = self.build(source, '0')
        self.assertEqual(built.returncode, 0, built.stderr)
        ran = subprocess.run([str(exe)], capture_output=True, timeout=60)
        self.assertEqual(ran.stdout.decode(), '[5, 6]\nnot supported\n')


T426 = '''import sys


class BaseAppError(Exception):
    pass


class ParseError(BaseAppError):
    pass


class RangeError(BaseAppError):
    pass


def validate(line: str) -> int:
    try:
        v = int(line)
    except ValueError:
        raise ParseError(f"not an int: {line!r}")
    if not 1 <= v <= 5:
        raise RangeError(f"out of range: {v}")
    return v


def main() -> None:
    processed = 0
    for line in sys.stdin.read().splitlines():
        try:
            v = validate(line)
            print("ok", v)
        except ParseError as e:
            print("ParseError:", e)
        except RangeError as e:
            print("RangeError:", e)
        finally:
            processed += 1
    print("processed", processed)


if __name__ == "__main__":
    main()
'''

SIBLINGS = '''
class Base(Exception):
    pass

class A(Base):
    pass

class B(Base):
    pass

class C(A):
    pass

def raiser(k: int) -> None:
    if k == 0:
        raise A("a")
    if k == 1:
        raise B("b")
    if k == 2:
        raise C("c")
    raise Base("base")

def main() -> None:
    for k in range(4):
        try:
            raiser(k)
        except B as e:
            print("B", e, type(e).__name__)
        except A as e:
            print("A", e, type(e).__name__)
        except Base as e:
            print("Base", e, type(e).__name__)

main()
'''


class UserExceptionTests(Base):
    def test_t426_sibling_classes(self):
        out = self.same(T426, stdin='1\nabc\n9\n3\n0\nx\n', irs=('0', '1'))
        self.assertIn('RangeError: out of range: 9', out)
        self.assertIn('ParseError: not an int', out)

    def test_t426_on_the_typed_path_alone(self):
        self.same(T426, typed=True, stdin='1\nabc\n9\n3\n')

    def test_sibling_and_derived_handlers(self):
        self.assertEqual(self.same(SIBLINGS, typed=True).splitlines(),
                         ['A a A', 'B b B', 'A c C', 'Base base Base'])


if __name__ == '__main__':
    unittest.main()

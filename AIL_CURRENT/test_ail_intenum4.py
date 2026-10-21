"""IntEnum / IntFlag leftovers: `**`, equality across kinds, and division-by-zero text, against CPython 3.12.

1. `C.A ** 2`, `2 ** C.A`, `C.A ** C.B`, the 2- and 3-argument `pow()`, negative / zero exponents and values
   reaching the expression through a parameter, a list item, an attribute and a dict value all give CPython's
   answer (an IntFlag or another IntEnum is an int subclass too).
2. An IntEnum / IntFlag member compares equal by value to another IntEnum / IntFlag member (also across classes
   and to a plain int / float / bool), but not to a plain Enum / Flag member with the same value: that one is an
   object, and the core `_AilIntEnum` / `_AilStrEnum` equality now says so in both directions.
3. Int `% 0` is CPython's "integer modulo by zero" (it used to say "integer division or modulo by zero").  Int
   `// 0` and `divmod(int, 0)` keep "integer division or modulo by zero"; float `%` / `//` keep "float modulo" /
   "float floor division by zero", and `divmod` with a float and a zero divisor is "float divmod()" (the general
   runtime and the typed `_ail_divmod_f` helper).  The forms are checked directly, through parameters, list
   items, dict values, attributes and loop variables, on the general path, the default build (IR 0 and 1) and
   the typed path for the divmod helper.
"""
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent
CLI = str(ROOT / 'ail_chatgpt.py')


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix='ail-intenum4-')
        self.dir = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def cpython(self, source):
        path = self.dir / 'cpython_main.py'
        path.write_text(source, encoding='utf-8')
        return subprocess.run([sys.executable, '-B', str(path)], capture_output=True, text=True,
                              timeout=300).stdout

    def build(self, source, mode):
        entry = self.dir / 'main.py'
        entry.write_text(source, encoding='utf-8')
        exe = self.dir / ('out_' + mode)
        env = dict(os.environ, AIL_NO_CACHE='1')
        env.pop('AIL_NO_GENERAL', None)
        env.pop('AIL_UNIFIED_FORCE', None)
        env.pop('AIL_IR', None)
        env['AIL_IR'] = '1' if mode.endswith('1') else '0'
        if mode == 'general':
            env['AIL_UNIFIED_FORCE'] = '1'
        elif mode.startswith('typed'):
            env['AIL_NO_GENERAL'] = '1'
        return subprocess.run([sys.executable, '-B', CLI, 'compile', str(entry), '--syntax', 'python',
                               '-o', str(exe)], cwd=self.dir, capture_output=True, text=True, timeout=900,
                              env=env), exe

    def same(self, source, typed=False, general=True):
        expected = self.cpython(source)
        modes = (['general'] if general else []) + ['default0', 'default1'] + (['typed0', 'typed1'] if typed else [])
        for mode in modes:
            built, exe = self.build(source, mode)
            self.assertEqual(built.returncode, 0, '%s: %s' % (mode, built.stdout + built.stderr))
            ran = subprocess.run([str(exe)], capture_output=True, text=True, timeout=300)
            self.assertEqual(ran.stdout, expected, mode)
            self.assertEqual(ran.returncode, 0, mode + ': ' + ran.stderr)
        return expected

ENUM_SRC = r'''from enum import IntEnum, IntFlag, Enum, Flag, StrEnum

class C(IntEnum):
    A = 3
    B = 5
    NEG = -2
    ZERO = 0
    ALIAS = 3

class D(IntEnum):
    A = 3

class E(Enum):
    A = 3
    B = 5

class F(IntFlag):
    X = 1
    Y = 4
    XY = 5

class G(Flag):
    X = 1

class S(StrEnum):
    A = "x"
    B = "y"

class T(StrEnum):
    A = "x"

class U(Enum):
    A = "x"

class H:
    def __init__(self, c, n: int):
        self.c = c
        self.n = n

def show(label: str, text: str) -> None:
    print(label, text)

def p(label: str, f) -> None:
    try:
        show(label, repr(f()))
    except Exception as e:
        show(label, type(e).__name__ + ': ' + str(e))

def eq(a, b) -> bool:
    return a == b

def ne(a, b) -> bool:
    return a != b

def pow2(a, b):
    return a ** b

def pow3(a, b, m: int):
    return pow(a, b, m)

# exponentiation: direct, reflected, same/different IntEnum, IntFlag, aliases, negative/zero
p('C.A ** 2', lambda: C.A ** 2)
p('2 ** C.A', lambda: 2 ** C.A)
p('C.A ** C.B', lambda: C.A ** C.B)
p('C.A ** D.A', lambda: C.A ** D.A)
p('D.A ** C.A', lambda: D.A ** C.A)
p('C.A ** F.Y', lambda: C.A ** F.Y)
p('F.Y ** C.A', lambda: F.Y ** C.A)
p('F.X ** 2', lambda: F.X ** 2)
p('(F.X | F.Y) ** 2', lambda: (F.X | F.Y) ** 2)
p('2 ** F.Y', lambda: 2 ** F.Y)
p('C.ALIAS ** 2', lambda: C.ALIAS ** 2)
p('C.NEG ** 2', lambda: C.NEG ** 2)
p('C.NEG ** 3', lambda: C.NEG ** 3)
p('C.A ** 0', lambda: C.A ** 0)
p('C.ZERO ** 0', lambda: C.ZERO ** 0)
p('C.A ** -1', lambda: C.A ** -1)
p('C.NEG ** -2', lambda: C.NEG ** -2)
p('C.ZERO ** -1', lambda: C.ZERO ** -1)
p('C.A ** True', lambda: C.A ** True)
p('pow(C.A, 2)', lambda: pow(C.A, 2))
p('pow(2, C.A)', lambda: pow(2, C.A))
p('pow(C.A, C.B)', lambda: pow(C.A, C.B))
p('pow(C.A, 2, 5)', lambda: pow(C.A, 2, 5))
p('pow(2, C.A, 5)', lambda: pow(2, C.A, 5))
p('pow(C.A, -1, 5)', lambda: pow(C.A, -1, 5))
p('pow(C.A, C.B, 7)', lambda: pow(C.A, C.B, 7))
p('pow(C.ALIAS, 2, 5)', lambda: pow(C.ALIAS, 2, 5))
p('pow2(C.A, 3)', lambda: pow2(C.A, 3))
p('pow3(C.A, 3, 7)', lambda: pow3(C.A, 3, 7))

def through(x, n: int) -> int:
    return x ** n

p('arg C.B ** 2', lambda: through(C.B, 2))
p('arg 2 ** C.B', lambda: 2 ** through(C.B, 1))
l = [C.A, C.B]
p('list[1] ** 2', lambda: l[1] ** 2)
p('2 ** list[0]', lambda: 2 ** l[0])
d = {'k': C.NEG}
p("dict['k'] ** 3", lambda: d['k'] ** 3)
h = H(C.B, 2)
p('attr.c ** attr.n', lambda: h.c ** h.n)
a = C.A
p('local a ** 2', lambda: a ** 2)

# equality across kinds, both directions and through containers/arguments
show('C.A == C.A', str(C.A == C.A))
show('C.A is C.ALIAS', str(C.A is C.ALIAS))
show('C.A == C.ALIAS', str(C.A == C.ALIAS))
show('C.A == D.A', str(C.A == D.A))
show('D.A == C.A', str(D.A == C.A))
show('C.A != D.A', str(C.A != D.A))
show('D.A != C.A', str(D.A != C.A))
show('C.A == E.A', str(C.A == E.A))
show('E.A == C.A', str(E.A == C.A))
show('C.A != E.A', str(C.A != E.A))
show('C.A == F.X', str(C.A == F.X))
show('F.X == C.A', str(F.X == C.A))
show('F.XY == C.B', str(F.XY == C.B))
show('F.X == G.X', str(F.X == G.X))
show('G.X == F.X', str(G.X == F.X))
show('F.X != G.X', str(F.X != G.X))
show('C.A == 3', str(C.A == 3))
show('3 == C.A', str(3 == C.A))
show('C.A == 3.0', str(C.A == 3.0))
show('C.A == True', str(C.A == True))
show('C.A == None', str(C.A == None))
show('C.A == "3"', str(C.A == "3"))
show('S.A == S.A', str(S.A == S.A))
show('S.A == T.A', str(S.A == T.A))
show('T.A == S.A', str(T.A == S.A))
show('S.A != T.A', str(S.A != T.A))
show('S.A == U.A', str(S.A == U.A))
show('U.A == S.A', str(U.A == S.A))
show('S.A == "x"', str(S.A == "x"))
show('"x" == S.A', str("x" == S.A))
show('S.A == S.B', str(S.A == S.B))
show('eq(C.A, D.A)', str(eq(C.A, D.A)))
show('eq(C.A, E.A)', str(eq(C.A, E.A)))
show('ne(C.A, E.A)', str(ne(C.A, E.A)))
ls = [C.A, D.A, E.A, F.X, G.X]
show('list eq', repr([eq(ls[0], x) for x in ls]))
dm = {'i': C.A, 'e': E.A, 'f': F.X, 'g': G.X}
show("dict eq i/e", str(eq(dm['i'], dm['e'])))
show("dict eq i/f", str(eq(dm['i'], dm['f'])))
show("dict eq f/g", str(eq(dm['f'], dm['g'])))
hd = H(D.A, 0)
show('attr eq', str(eq(C.A, hd.c)))
show('attr eq rev', str(eq(hd.c, C.A)))
show('hash C.A == hash 3', str(hash(C.A) == hash(3)))
show('hash C.A == hash D.A', str(hash(C.A) == hash(D.A)))
'''

CROSS_SRC = r'''from enum import IntEnum, IntFlag, Enum, Flag, StrEnum

class C(IntEnum):
    A = 3
class D(Enum):
    A = 3
class F(IntFlag):
    X = 3
class G(Flag):
    X = 3
class S(StrEnum):
    A = "x"
class U(Enum):
    A = "x"

def p(label: str, f) -> None:
    try:
        print(label, repr(f()))
    except Exception as e:
        print(label, type(e).__name__ + ': ' + str(e))

def c(label: str, f) -> None:
    try:
        print(label, repr(f()))
    except Exception as e:
        print(label, type(e).__name__)

p('C.A + D.A', lambda: C.A + D.A)
p('D.A + C.A', lambda: D.A + C.A)
p('C.A - D.A', lambda: C.A - D.A)
p('D.A - C.A', lambda: D.A - C.A)
p('C.A * D.A', lambda: C.A * D.A)
p('D.A * C.A', lambda: D.A * C.A)
p('C.A / D.A', lambda: C.A / D.A)
p('D.A / C.A', lambda: D.A / C.A)
p('C.A // D.A', lambda: C.A // D.A)
p('D.A // C.A', lambda: D.A // C.A)
p('C.A % D.A', lambda: C.A % D.A)
p('D.A % C.A', lambda: D.A % C.A)
p('C.A ** D.A', lambda: C.A ** D.A)
p('D.A ** C.A', lambda: D.A ** C.A)
p('C.A << D.A', lambda: C.A << D.A)
p('D.A << C.A', lambda: D.A << C.A)
p('C.A >> D.A', lambda: C.A >> D.A)
p('D.A >> C.A', lambda: D.A >> C.A)
p('C.A & D.A', lambda: C.A & D.A)
p('D.A & C.A', lambda: D.A & C.A)
p('C.A | D.A', lambda: C.A | D.A)
p('D.A | C.A', lambda: D.A | C.A)
p('C.A ^ D.A', lambda: C.A ^ D.A)
p('D.A ^ C.A', lambda: D.A ^ C.A)
p('C.A + G.X', lambda: C.A + G.X)
p('G.X + C.A', lambda: G.X + C.A)
p('G.X & C.A', lambda: G.X & C.A)
p('C.A & G.X', lambda: C.A & G.X)
p('G.X | C.A', lambda: G.X | C.A)
p('C.A | G.X', lambda: C.A | G.X)
p('C.A + F.X', lambda: C.A + F.X)
p('F.X + C.A', lambda: F.X + C.A)
c('C.A < D.A', lambda: C.A < D.A)
c('D.A < C.A', lambda: D.A < C.A)
c('C.A > D.A', lambda: C.A > D.A)
c('D.A > C.A', lambda: D.A > C.A)
c('C.A <= D.A', lambda: C.A <= D.A)
c('D.A <= C.A', lambda: D.A <= C.A)
c('C.A >= D.A', lambda: C.A >= D.A)
c('D.A >= C.A', lambda: D.A >= C.A)
c('C.A < G.X', lambda: C.A < G.X)
c('G.X < C.A', lambda: G.X < C.A)
p('S.A + U.A', lambda: S.A + U.A)
c('S.A < U.A', lambda: S.A < U.A)
c('S.A > U.A', lambda: S.A > U.A)
c('U.A < S.A', lambda: U.A < S.A)
'''

ZERO_INT_SRC = r'''def ps(label: str, text: str) -> None:
    print(label, text)

def imod(a: int, b: int) -> int:
    return a % b

def ifloordiv(a: int, b: int) -> int:
    return a // b

class H:
    def __init__(self, a: int, b: int):
        self.a = a
        self.b = b

def run(label: str, a: int, b: int) -> None:
    try:
        ps(label + ' %', repr(a % b))
    except Exception as e:
        ps(label + ' %', type(e).__name__ + ': ' + str(e))
    try:
        ps(label + ' //', repr(a // b))
    except Exception as e:
        ps(label + ' //', type(e).__name__ + ': ' + str(e))
    try:
        t = divmod(a, b)
        print(label + ' divmod', t[0], t[1])
    except Exception as e:
        ps(label + ' divmod', type(e).__name__ + ': ' + str(e))

run('literal 5', 5, 0)
run('literal -5', -5, 0)
run('literal 0', 0, 0)
run('max', 9223372036854775807, 0)
run('min', -9223372036854775807 - 1, 0)
run('True', True, 0)
run('False', False, 0)

try:
    ps('5 % False', repr(5 % False))
except Exception as e:
    ps('5 % False', type(e).__name__ + ': ' + str(e))

xs = [5, -5, 0]
zs = [0]
run('list l[0]', xs[0], zs[0])
run('list l[1]', xs[1], zs[0])
run('list l[2]', xs[2], zs[0])

d = {'a': 5, 'n': -5, 'z': 0}
run("dict a", d['a'], d['z'])
run("dict n", d['n'], d['z'])
run("dict z", d['z'], d['z'])

h = H(7, 0)
run('attr', h.a, h.b)
for b in zs:
    run('loop', 5, b)
try:
    ps('imod', repr(imod(5, 0)))
except Exception as e:
    ps('imod', type(e).__name__ + ': ' + str(e))
try:
    ps('ifloordiv', repr(ifloordiv(5, 0)))
except Exception as e:
    ps('ifloordiv', type(e).__name__ + ': ' + str(e))
'''

ZERO_FLOAT_SRC = r'''def ps(label: str, text: str) -> None:
    print(label, text)

def fmod(a: float, b: float) -> float:
    return a % b

def ffloordiv(a: float, b: float) -> float:
    return a // b

def run(label: str, a: float, b: float) -> None:
    try:
        ps(label + ' %', repr(a % b))
    except Exception as e:
        ps(label + ' %', type(e).__name__ + ': ' + str(e))
    try:
        ps(label + ' //', repr(a // b))
    except Exception as e:
        ps(label + ' //', type(e).__name__ + ': ' + str(e))
    try:
        t = divmod(a, b)
        print(label + ' divmod', t[0], t[1])
    except Exception as e:
        ps(label + ' divmod', type(e).__name__ + ': ' + str(e))

run('5.0', 5.0, 0.0)
run('-5.0', -5.0, 0.0)
run('0.0', 0.0, 0.0)
run('-0.0', -0.0, -0.0)
try:
    ps('5.0 % 0', repr(5.0 % 0))
except Exception as e:
    ps('5.0 % 0', type(e).__name__ + ': ' + str(e))
try:
    ps('5.0 // 0', repr(5.0 // 0))
except Exception as e:
    ps('5.0 // 0', type(e).__name__ + ': ' + str(e))
try:
    t = divmod(5.0, 0)
    print('5.0 divmod 0', t[0], t[1])
except Exception as e:
    ps('5.0 divmod 0', type(e).__name__ + ': ' + str(e))
try:
    ps('5 % 0.0', repr(5 % 0.0))
except Exception as e:
    ps('5 % 0.0', type(e).__name__ + ': ' + str(e))
try:
    ps('5 // 0.0', repr(5 // 0.0))
except Exception as e:
    ps('5 // 0.0', type(e).__name__ + ': ' + str(e))
try:
    t = divmod(5, 0.0)
    print('5 divmod 0.0', t[0], t[1])
except Exception as e:
    ps('5 divmod 0.0', type(e).__name__ + ': ' + str(e))
try:
    ps('fmod', repr(fmod(5.0, 0.0)))
except Exception as e:
    ps('fmod', type(e).__name__ + ': ' + str(e))
try:
    ps('ffloordiv', repr(ffloordiv(5.0, 0.0)))
except Exception as e:
    ps('ffloordiv', type(e).__name__ + ': ' + str(e))

xs = [5.0, -5.0]
zs = [0.0]
try:
    ps('list fmod', repr(xs[0] % zs[0]))
except Exception as e:
    ps('list fmod', type(e).__name__ + ': ' + str(e))
try:
    t = divmod(xs[1], zs[0])
    print('list divmod', t[0], t[1])
except Exception as e:
    ps('list divmod', type(e).__name__ + ': ' + str(e))
for b in zs:
    try:
        t = divmod(5.0, b)
        print('loop divmod', t[0], t[1])
    except Exception as e:
        ps('loop divmod', type(e).__name__ + ': ' + str(e))
'''

TYPED_DIVMOD_SRC = r'''def m(a: int, b: int) -> int:
    return a % b

def f(a: int, b: int) -> int:
    return a // b

def dm(a: int, b: int):
    return divmod(a, b)

def mf(a: float, b: float) -> float:
    return a % b

def ff(a: float, b: float) -> float:
    return a // b

def dmf(a: float, b: float):
    return divmod(a, b)

def main() -> None:
    try:
        print(m(5, 0))
    except ZeroDivisionError as e:
        print('imod', e)
    try:
        print(f(5, 0))
    except ZeroDivisionError as e:
        print('ifloordiv', e)
    try:
        print(dm(5, 0))
    except ZeroDivisionError as e:
        print('idivmod', e)
    try:
        print(dm(-5, 0))
    except ZeroDivisionError as e:
        print('idivmodneg', e)
    try:
        print(mf(5.0, 0.0))
    except ZeroDivisionError as e:
        print('fmod', e)
    try:
        print(ff(5.0, 0.0))
    except ZeroDivisionError as e:
        print('ffloordiv', e)
    try:
        print(dmf(5.0, 0.0))
    except ZeroDivisionError as e:
        print('fdivmod', e)
    try:
        print(dmf(-5.0, 0.0))
    except ZeroDivisionError as e:
        print('fdivmodneg', e)

main()
'''

class IntEnum4Tests(Base):
    def test_exponentiation_and_cross_kind_equality(self):
        self.same(ENUM_SRC)

    def test_int_enum_ops_with_a_plain_enum_member(self):
        self.same(CROSS_SRC)

    def test_int_modulo_floordiv_divmod_text(self):
        self.same(ZERO_INT_SRC)

    def test_float_modulo_floordiv_divmod_text(self):
        self.same(ZERO_FLOAT_SRC)

    def test_typed_divmod_zero_text(self):
        self.same(TYPED_DIVMOD_SRC, typed=True, general=False)


if __name__ == '__main__':
    unittest.main()

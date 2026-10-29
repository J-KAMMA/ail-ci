"""reintenum4: the enum leftovers of the general path's prelude -- ``**``, cross-kind equality,
plain-enum ordering and ``divmod`` dispatch -- match CPython 3.12.

Fixed here (each compared against CPython below):

* ``**`` on an IntEnum/IntFlag is the int power of its value (``C.B ** 2``, ``pow(C.B, 2)``,
  ``pow(C.B, 2, 5)``, ``2 ** C.B``); ``pow(x, y, None)`` is the binary power and a float anywhere
  keeps CPython's int-only 3-argument message; any other instance in a 3-argument ``pow`` gets
  the three-operand operand-type message naming both classes/values.
* plain ``Enum`` equality is ``object``'s: it returns NotImplemented for another object, so the
  other operand's ``__eq__`` runs before the identity answer.  ``IntEnum``/``IntFlag`` compare
  with an int/float (and their IntEnum/IntFlag value) and not with another enum kind;
  ``StrEnum`` compares with a str and another StrEnum's value and not with a plain Enum.
* plain ``Enum`` members do not order: ``< <= > >=`` raise the operator-specific TypeError naming
  both classes; ``IntEnum``/``StrEnum`` keep int/str ordering.
* ``divmod`` follows ``__divmod__``/``__rdivmod__``: IntEnum/IntFlag use the int pair, a class with
  only ``__index__`` is refused by CPython's message, ``5 % 0`` says "integer modulo by zero" while
  ``//``/``divmod`` keep "integer division or modulo by zero".

Values reach the operators through a parameter, a list item, an attribute and a dict value.
Programs are built with the general path forced and with the default build; stdout and the exit
status must match CPython.
"""
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent

PROGRAMS = {
    'pow': '''
from enum import Enum, IntEnum, IntFlag

class C(IntEnum):
    A = 1
    B = 3

class F(IntFlag):
    X = 2
    Y = 4

class E(Enum):
    A = 1

class O(IntEnum):
    A = 3
    B = 5
    def __index__(self):
        return 1

class G(IntFlag):
    X = 3
    Y = 5
    def __index__(self):
        return 1

class A(Exception):
    pass

class B(Exception):
    pass


def t(label, thunk):
    try:
        print(label, repr(thunk()))
    except Exception as exc:
        print(label, type(exc).__name__, str(exc))


t("intenum_sq", lambda: C.B ** 2)
t("intenum_builtin", lambda: pow(C.B, 2))
t("intenum_mod", lambda: pow(C.B, 2, 5))
t("intenum_rpow", lambda: 2 ** C.B)
t("intenum_neg", lambda: C.B ** -1)
t("intenum_peer", lambda: C.B ** C.A)
t("intflag_sq", lambda: F.Y ** 2)
t("float_third", lambda: pow(2.0, 3, 5))
t("float_exp", lambda: pow(2, 3.0, 5))
t("float_mod", lambda: pow(2, 3, 5.0))
t("intenum_float_mod", lambda: pow(C.B, 2, 1.0))
t("none_mod", lambda: pow(C.B, 2, None))
t("float_exp_enum", lambda: pow(C.B, 2.0, 5))
t("plain_int", lambda: E.A ** 2)
t("plain_right", lambda: 2 ** E.A)
t("str_base", lambda: "a" ** 2)
t("str_exp", lambda: 2 ** "a")
t("list_base", lambda: [1] ** 2)
t("list_exp", lambda: 2 ** [1])
t("plain_cross", lambda: C.B ** E.A)
t("exc_names", lambda: A() ** B())
t("exc_names_rev", lambda: B() ** A())
t("exc_int", lambda: A() ** 2)
t("int_exc", lambda: 2 ** A())
t("override_a", lambda: pow(O.A, 2, 5))
t("override_b", lambda: pow(O.B, 3, 7))
t("override_peer", lambda: pow(O.A, O.B, 7))
t("override_flag", lambda: (pow(G.X, 2, 5), pow(G.Y, 3, 7)))
t("override_plain", lambda: (pow(O.A, 2, 5), O.A ** 2))
''',
    'equality': '''
from enum import Enum, IntEnum, IntFlag, StrEnum

class C(IntEnum):
    A = 1
    B = 3

class E(Enum):
    A = 1

class P(Enum):
    A = 1

class S(StrEnum):
    A = "x"

class T(StrEnum):
    A = "x"

class F(IntFlag):
    A = 1

class G(IntFlag):
    A = 1


class Probe:
    def __init__(self, tag):
        self.tag = tag

    def __eq__(self, other):
        print("Probe.__eq__", self.tag)
        return True

    def __hash__(self):
        return 0


class Plain:
    def __eq__(self, other):
        print("Plain.__eq__")
        return "yes"


def t(label, thunk):
    try:
        print(label, repr(thunk()))
    except Exception as exc:
        print(label, type(exc).__name__, str(exc))


t("intenum_plain", lambda: C.A == E.A)
t("plain_intenum", lambda: E.A == C.A)
t("plain_plain", lambda: E.A == P.A)
t("plain_int", lambda: E.A == 1)
t("int_plain", lambda: 1 == E.A)
t("intenum_int", lambda: C.A == 1)
t("int_intenum", lambda: 1 == C.A)
t("intenum_float", lambda: C.A == 1.0)
t("intenum_flag", lambda: C.A == F.A)
t("flag_flag", lambda: F.A == G.A)
t("strenum_strenum", lambda: S.A == T.A)
t("strenum_str", lambda: S.A == "x")
t("str_strenum", lambda: "x" == S.A)
t("strenum_plain", lambda: S.A == E.A)
t("plain_strenum", lambda: E.A == S.A)
t("strenum_intenum", lambda: S.A == C.A)
t("plain_probe", lambda: E.A == Probe("right"))
t("probe_plain", lambda: Probe("left") == E.A)
t("intenum_probe", lambda: C.A == Probe("r2"))
t("strenum_probe", lambda: S.A == Probe("r3"))
t("plain_custom", lambda: E.A == Plain())
''',
    'ordering': '''
from enum import Enum, IntEnum, StrEnum

class E(Enum):
    A = 1

class P(Enum):
    A = 1

class C(IntEnum):
    A = 1

class S(StrEnum):
    A = "x"

class T(StrEnum):
    A = "x"
    B = "y"


def t(label, thunk):
    try:
        print(label, repr(thunk()))
    except Exception as exc:
        print(label, type(exc).__name__, str(exc))


t("e_lt_int", lambda: E.A < 2)
t("int_lt_e", lambda: 2 < E.A)
t("e_gt_int", lambda: E.A > 2)
t("e_le_int", lambda: E.A <= 2)
t("e_ge_int", lambda: E.A >= 2)
t("e_lt_p", lambda: E.A < P.A)
t("p_lt_e", lambda: P.A < E.A)
t("e_lt_e", lambda: E.A < E.A)
t("e_gt_p", lambda: E.A > P.A)
t("e_ge_p", lambda: E.A >= P.A)
t("c_lt_int", lambda: C.A < 2)
t("int_lt_c", lambda: 1 < C.A)
t("c_le_c", lambda: C.A <= C.A)
t("s_lt_str", lambda: S.A < "z")
t("str_lt_s", lambda: "a" < S.A)
t("s_lt_t", lambda: S.A < T.B)
t("s_gt_t", lambda: S.A > T.B)
t("s_ge_t", lambda: S.A >= T.A)
t("s_lt_e", lambda: S.A < E.A)
t("e_lt_s", lambda: E.A < S.A)
t("c_lt_e", lambda: C.A < E.A)
t("e_lt_c", lambda: E.A < C.A)
t("c_lt_s", lambda: C.A < S.A)
t("s_lt_c", lambda: S.A < C.A)
t("s_le_e", lambda: S.A <= E.A)
t("s_ge_e", lambda: S.A >= E.A)
''',
    'divmod': '''
from enum import Enum, IntEnum, IntFlag

class C(IntEnum):
    B = 3
    N = -7
    A = 1

class F(IntFlag):
    X = 5

class E(Enum):
    A = 1

class P:
    def __index__(self):
        return 3

class Q:
    def __int__(self):
        return 3


def t(label, thunk):
    try:
        print(label, repr(thunk()))
    except Exception as exc:
        print(label, type(exc).__name__, str(exc))


t("c_2", lambda: divmod(C.B, 2))
t("7_c", lambda: divmod(7, C.B))
t("c_c", lambda: divmod(C.B, C.A))
t("neg_l", lambda: divmod(C.N, 2))
t("neg_r", lambda: divmod(7, C.N))
t("f_2", lambda: divmod(F.X, 2))
t("2_f", lambda: divmod(2, F.X))
t("plain", lambda: divmod(E.A, 2))
t("plain_r", lambda: divmod(2, E.A))
t("index", lambda: divmod(P(), 2))
t("index_r", lambda: divmod(2, P()))
t("int_only", lambda: divmod(Q(), 2))
t("divmod_method", lambda: C.B.__divmod__(2))
t("floordiv_mod", lambda: (C.B // 2, C.B % 2, C.N // 2, C.N % 2))
''',
    'zero_division': '''
from enum import IntEnum

class C(IntEnum):
    B = 3


def t(label, thunk):
    try:
        thunk()
    except Exception as exc:
        print(label, type(exc).__name__, str(exc))


t("mod0", lambda: 5 % 0)
t("floordiv0", lambda: 5 // 0)
t("divmod0", lambda: divmod(5, 0))
t("cmod0", lambda: C.B % 0)
t("cfloordiv0", lambda: C.B // 0)
t("cdivmod0", lambda: divmod(C.B, 0))
t("fmod0", lambda: 5.0 % 0)
t("ffloordiv0", lambda: 5.0 // 0)
''',
    'values': '''
from enum import Enum, IntEnum, IntFlag, StrEnum


class C(IntEnum):
    A = 1
    B = 3
    N = -7
    LOW = -1000000000000
    HIGH = 1000000000000
    MAXI = 9223372036854775807


class E(Enum):
    A = 1


class F(IntFlag):
    A = 1
    B = 2


class S(StrEnum):
    E = ""
    A = "alpha"


class T(StrEnum):
    A = "alpha"


class W(IntEnum):
    A = 1
    B = 1


class Box:
    def __init__(self, v):
        self.v = v


def t(label, thunk):
    try:
        print(label, repr(thunk()))
    except Exception as exc:
        print(label, type(exc).__name__, str(exc))


def via_param(x):
    return (x ** 2, pow(x, 2), pow(x, 2, 5), divmod(x, 2), x < 2, x == 1)


dct = {"c": C.B, "e": E.A, "s": S.A}
box = Box(C.B)


t("param", lambda: via_param(C.B))
t("list", lambda: [x ** 2 for x in [C.B, C.N]])
t("list_eq", lambda: [C.B == E.A, C.A == 1])
t("attr", lambda: (box.v ** 2, pow(box.v, 2, 5), box.v == 3))
t("dict", lambda: (dct["c"] ** 2, divmod(dct["c"], 2), dct["e"] == 1, dct["s"] == "alpha"))
t("alias", lambda: (C.A is C.A, C.A == C.A, hash(C.A) == hash(1), C.A == W.A, W.A == W.B,
                    hash(W.A) == hash(W.B)))
t("neg", lambda: (C.N ** 2, divmod(C.N, 2), C.N < 0, pow(C.N, 2, 5), -C.N))
t("width", lambda: (C.HIGH * 2, C.HIGH + C.LOW, divmod(C.HIGH, 7), pow(C.HIGH, 2, 1000000007),
                    C.HIGH > 999999999999, C.MAXI == 9223372036854775807,
                    C.MAXI - 1 == 9223372036854775806))
t("strempty", lambda: (S.E == "", S.E < "a", S.E == E.A, len(S.E), S.E + "z"))
t("struni", lambda: (S.A == "alpha", S.A < "beta", T.A == S.A, S.A == C.A, "alpha" == S.A))
t("flag", lambda: (F.A ** 2, pow(F.A, 2, 5), divmod(F.A, 2), F.A == C.A, F.A == F.A, F.A < 2))
t("cross", lambda: (C.A < E.A, E.A < C.A, C.A + E.A, E.A + C.A, C.A == E.A, E.A == C.A))
t("floats", lambda: (C.B * 0.5, C.B < 3.5, C.B == 3.0, C.B ** 0.5, divmod(C.B, 2.0)))
t("pow3chan", lambda: (pow(box.v, 2, 5), pow(dct["c"], 2, 5), pow(C.A, C.B, 5), pow(F.B, 3, 5)))
t("plain_divmod", lambda: divmod(E.A, 2))
t("plain_pow", lambda: E.A ** 2)
''',
}


def run_cpython(directory, name, text):
    source = Path(directory) / (name + '_cpython.py')
    source.write_text(text, encoding='utf-8')
    done = subprocess.run([sys.executable, '-B', str(source)], capture_output=True, text=True,
                          timeout=120, env=dict(os.environ, PYTHONUTF8='1'))
    return done.stdout.replace('\r\n', '\n'), done.returncode


def build(directory, name, text, general):
    source = Path(directory) / (name + '.py')
    source.write_text(text, encoding='utf-8')
    exe = Path(directory) / (name + ('_g' if general else '_d'))
    env = dict(os.environ, AIL_NO_CACHE='1', AIL_QUIET_FALLBACK='1')
    env.pop('AIL_NO_GENERAL', None)
    env.pop('AIL_GENERAL', None)
    if general:
        env['AIL_UNIFIED_FORCE'] = '1'
    else:
        env.pop('AIL_UNIFIED_FORCE', None)
    built = subprocess.run([sys.executable, '-B', str(ROOT / 'ail_chatgpt.py'), 'compile',
                            source.name, '--syntax', 'python', '-o', exe.name], cwd=directory,
                           capture_output=True, text=True, timeout=900, env=env)
    return built, exe


class ReIntEnum4(unittest.TestCase):
    def test_enum_leftovers_match_cpython(self):
        with tempfile.TemporaryDirectory(prefix='ail-reintenum4-') as directory:
            for name, text in PROGRAMS.items():
                want, status = run_cpython(directory, name, text)
                for general in (False, True):
                    with self.subTest(case=name, general=general):
                        built, exe = build(directory, name, text, general)
                        self.assertEqual(built.returncode, 0, built.stdout + built.stderr)
                        ran = subprocess.run([str(exe)], capture_output=True, text=True, timeout=120,
                                             cwd=directory)
                        self.assertEqual(ran.returncode, status, ran.stderr[-1200:])
                        self.assertEqual(ran.stdout.replace('\r\n', '\n'), want, ran.stderr[-1200:])


if __name__ == '__main__':
    unittest.main()

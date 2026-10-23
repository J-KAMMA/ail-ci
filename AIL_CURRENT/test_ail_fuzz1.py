"""fuzz1: silent differences found by tools/difffuzz.py.

* A default argument that is not a literal (a name, `X * 2`, `-X`, `len(L)`, `S[1:3]`, `S.upper()`,
  an attribute, a dict value, a list item, a function name, a builtin) is evaluated ONCE, when the
  `def` runs, as CPython does; before, it was re-read at every call, so `X = 2; def f(a=X); X = 3`
  printed 3 where CPython prints 2.
* A default that names something defined only after the `def` (CPython: NameError at the `def`) is
  refused by name; before, it built, and ran with the later definition.
* The same for a LAMBDA default (`h = lambda a=g(): a` with `def g()` below): CPython raises
  NameError where the lambda is made, AIL printed `start`, `1` and exited 0. Refused by name where
  the lambda can be made before the binding; a lambda made after the binding still builds.
  A lambda default reading a local bound later in the same function is refused too (CPython:
  UnboundLocalError there).
* tools/difffuzz.py: its shrinker works (a reused build directory made it see "no difference").

Each program is built twice (default build, AIL_UNIFIED_FORCE=1 general path) and must print what
CPython prints with the same exit status, or be refused by name at compile time when CPython raises.
"""
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent
CLI = str(ROOT / "ail_chatgpt.py")

P_NAMES = r"""X = 2
S = "hello"
L = [1, 2, 3]
D = {"k": 7}
def helper():
    return 5
class C:
    v = 9
o = C()
def f1(a=X): return a
def f2(a=X * 2, b=-X): return (a, b)
def f3(n=len(L)): return n
def f4(s=S[1:3], u=S.upper()): return (s, u)
def f5(a=o.v, d=D["k"], i=L[1]): return (a, d, i)
def f6(fn=helper, ln=len): return (fn(), ln("ab"))
def f7(acc=L): acc.append(1); return len(acc)
def f8(*, k=X + 1, j=3): return (k, j)
def f9(a=1, b="x"): return (a, b)
class K:
    def m(self, a=X + 10): return a
def main():
    global X, S
    X = 3
    S = "zzz"
    L.append(4)
    o.v = 100
    D["k"] = 8
    print(f1())
    print(f2())
    print(f3())
    print(f4())
    print(f5())
    print(f6())
    print(f7(), f7())
    print(f8())
    print(f9())
    print(K().m())
    print(f1(5), f8(k=1), f8(j=0), K().m(1))
main()
"""

P_GLOBALS = r"""Y = 5
def f(a=Y, b=Y + 1):
    return a + b
def main():
    global Y
    for i in range(3):
        Y += 1
        print(f(), f(i), f(b=i))
    Y = 0
    print(f())
main()
"""

F_FORWARD = r"""def f(a=g):
    return a
def g():
    return 1
def main():
    print("start")
    print(f()())
main()
"""

F_FORWARD2 = r"""def f(a=g):
    return a
def main():
    print(f()())
def g():
    return 1
main()
"""

# The review's four non-literal default probes (p1, p2a, p2b, p3).
P1 = r"""X = 2
S = "hello"
D = {"k": 7}
L = [1, 2, 3]
class C:
    v = 9
o = C()
def f1(a=X): return a
def f2(a=X * 2, b=-X): return (a, b)
def f3(s=S[1:3], u=S.upper()): return (s, u)
def f4(a=o.v, d=D["k"], i=L[1]): return (a, d, i)
def main():
    global X, S
    X = 3
    S = "zzz"
    o.v = 100
    D["k"] = 8
    L[1] = 99
    print(f1(), f2(), f3(), f4())
main()
"""

P2A = r"""def helper():
    return 5
X = 4
def g1(fn=helper, ln=len, x=X): return (fn(), ln("abcd"), x)
class K:
    def m(self, a=X + 10): return a
    def n(self, *, k=X * 3): return k
def h(a=1, b="s"):
    return (a, b)
def main():
    global X
    X = 100
    print(g1(), K().m(), K().n())
    print(g1(helper, len, 1), K().m(2), K().n(k=3))
    print(h(), h(7), h(b="z"))
main()
"""

P2B = r"""def bump():
    global N
    N = N + 1
    print("bump", N)
    return N
N = 0
def f(a=bump(), b=N): return (a, b)
def main():
    print("start", N)
    print(f())
    print(f())
    print(N)
main()
"""

P3 = r"""L = [1, 2]
def f(acc=L, tag="t"):
    acc.append(len(acc))
    return (len(acc), tag)
def g(a=L):
    return len(a)
def main():
    print(f(), f(), f())
    print(L)
    print(g(), g())
    print(len(L))
main()
"""

# Item 1: a lambda default that refers to a function defined later. CPython evaluates the default
# where the lambda is made, so it raises NameError (UnboundLocalError for a local) there; AIL used to
# print `start`, `1` and exit 0 because every module-level def exists before module code runs.
U3 = r"""h = lambda a=g(): a
def g():
    return 1
print("start")
print(h())
"""

U3_CALLED_EARLY = r"""def main():
    h = lambda a=g(): a
    return h()
main()
def g():
    return 1
print("start")
"""

U3_VALUE = r"""def main():
    h = lambda a=g: a
    return h
main()
def g():
    return 1
print("start")
"""

U3_CLASS_BODY = r"""class K:
    h = lambda a=g(): a
def g():
    return 1
print("start")
print(K.h())
"""

U3_KWONLY = r"""h = lambda *, a=g(): a
def g():
    return 1
print("start")
print(h())
"""

U3_LOCAL = r"""def main():
    h = lambda a=g(): a
    def g():
        return 1
    return h()
print(main())
"""

U3_GLOBAL_REBIND = r"""X = 1
def main():
    global X
    h = lambda a=X: a
    X = 2
    return h()
print(main(), X)
"""

U3_LOCAL_EARLIER = r"""def main():
    x = 1
    h = lambda a=x: a
    x = 2
    return h()
print(main())
"""

# the same shape, but the lambda is made after g is bound: CPython prints 1, so this must build
U3_AFTER_BINDING = r"""def main():
    h = lambda a=g(): a
    print(h())
def g():
    return 1
main()
"""

U3_AFTER_BINDING2 = r"""class B:
    def m(self):
        h = lambda a=g(): a
        return h()
def g():
    return 3
def main():
    print(B().m())
main()
"""

# lambda defaults that do NOT refer forward: evaluated once, at the point the lambda is made
L_DEFAULTS = r"""X = 2
L = [1]
def k():
    print("k")
    return 7
h1 = lambda a=X: a
h2 = lambda a=L: a
h3 = lambda a=k(): a
X = 3
L.append(2)
d = {"f": lambda a=X: a}
lst = [lambda a=X: a]
def main():
    print(h1(), h2(), h3(), h3())
    print(d["f"](), lst[0](), h1(5))
    L.append(3)
    print(len(h2()), len(L))
main()
"""

F_UNDEF = r"""class C:
    X = 5
    def m(self, a=X):
        return a
X = 1
def main():
    print(C().m())
main()
"""

NEVER_SET = r"""def f(a=Z):
    return a
def setz():
    global Z
    Z = 1
def main():
    print("start")
    setz()
    print(f())
main()
"""

H_VALUES = r"""def main():
    print(hash(-9007199254740993), hash(9007199254740993))
    print(hash(-1), hash(2**61 - 1), hash(2**61), hash(-2**61), hash(-(2**61) - 5), hash(2**62))
    print(hash(2**62 - 1 + 2**62), hash(-9223372036854775807))
    print(hash(0), hash(1), hash(-2), hash(True), hash(False))
    print(hash(1.5), hash(-0.5), hash(0.0), hash(-0.0), hash(1e300), hash(2.0**70), hash(5e-324), hash(3.0), hash(-3.0), hash(0.1))
    inf = 1e308 * 10
    print(hash(inf), hash(-inf))
    print(hash(None), hash(()), hash((1, 2)), hash((1, (2, 3))), hash((None,)), hash((1.5, True, -1)))
    y = -9007199254740993
    print(hash(y) > 0, hash(y) > -0.0, hash(y) < 0.0)
    xs = [5, -7, 2**40]
    print([hash(v) for v in xs], hash(xs[1]))
    d = {1: 100}
    print(hash(d[1]), hash(len(xs)))
main()
"""

H_INSTANCES = r"""class P:
    def __init__(self, a, b):
        self.a = a
        self.b = b
    def __hash__(self):
        return hash((self.a, self.b))
    def __eq__(self, o):
        return self.a == o.a
class Q:
    def __init__(self, a):
        self.a = a
    def __hash__(self):
        return 17
    def __eq__(self, o):
        return True
class R:
    def __init__(self, a):
        self.a = a
    def __hash__(self):
        return hash(self.a)
    def __eq__(self, o):
        return True
def main():
    print(hash((3, 4)))
    t = (3, 4)
    print(hash(t))
    print(hash(P(3, 4)))
    print(hash(Q(1)), hash(R(-1)), hash(R(2**40)))
main()
"""

H_ODD = r"""class Bad:
    def __hash__(self):
        return "x"
class Raiser:
    def __hash__(self):
        raise ValueError("no hash")
class Neg:
    def __hash__(self):
        return -1
class Big:
    def __hash__(self):
        return 4611686018427387904
def main():
    print(hash(Neg()), hash(Big()))
    try:
        hash(Bad())
    except TypeError as e:
        print("TypeError", e)
    try:
        hash(Raiser())
    except ValueError as e:
        print("ValueError", e)
    print(hash((Neg(), 1)))
    try:
        hash([1])
    except TypeError as e:
        print("TypeError", e)
main()
"""

H_CLASS_SET = r"""class P:
    def __init__(self, a, b):
        self.a = a
        self.b = b
    def __eq__(self, o):
        return self.a == o.a and self.b == o.b
    def __hash__(self):
        return hash((self.a, self.b))
def main():
    print(hash(2**62 + (2**62 - 1)), hash(-2**62 - (2**62 - 1)))
    p = P(3, 4)
    print(hash(p), hash(P(-1, 2)), hash(p) == hash(P(3, 4)))
    s = {p, P(3, 4), P(5, 6)}
    print(len(s))
    for v in (-9007199254740993, 0, 7):
        if hash(v) > -0.0:
            print("pos", v)
        else:
            print("nonpos", v)
main()
"""

H_EXCEPT = r"""class MyErr(Exception):
    pass

def main():
    nz = -0.0
    try:
        try:
            if hash(-9007199254740993) > nz:
                raise MyErr(4)
            [][0]
        except MyErr as ex:
            print("MyErr")
    except Exception as ex2:
        print('outer', type(ex2).__name__)
main()
"""


def run_py(path):
    r = subprocess.run([sys.executable, "-B", str(path)], capture_output=True, timeout=60)
    return r.returncode, r.stdout


EXC_P1 = r"""def main():
    for i in range(3):
        try:
            raise KeyError(i)
        except KeyError as err:
            if i == 1:
                break
    try:
        print(err)
    except UnboundLocalError:
        print("ub")
main()
"""

EXC_P2 = r"""def main():
    try:
        try:
            raise ValueError("a")
        except ValueError as e:
            raise KeyError("b")
    except KeyError:
        pass
    try:
        print(e)
    except UnboundLocalError:
        print("ub")
main()
"""

EXC_P3 = r"""def main():
    def g():
        try:
            1/0
        except ZeroDivisionError as z:
            return lambda: z
    print(g()())
main()
"""

EXC_Q1 = r"""def chk(f):
    try:
        print(f())
    except UnboundLocalError as u:
        print("UB", str(u))
    except Exception as x:
        print("other", type(x).__name__, x)

def main():
    def a():
        n = 0
        while True:
            n += 1
            try:
                raise KeyError(n)
            except KeyError as w:
                if n == 2:
                    break
        return w
    chk(a)
    def b():
        for i in range(3):
            try:
                raise KeyError(i)
            except KeyError as w:
                continue
        return w
    chk(b)
    def c():
        for i in (1, 2, 3):
            try:
                raise ValueError(i)
            except ValueError as w:
                if i == 2:
                    break
        return w
    chk(c)
    def d():
        for i in [5, 6, 7]:
            try:
                raise ValueError(i)
            except ValueError as w:
                if i == 6:
                    break
        else:
            return -1
        return w
    chk(d)
    def e():
        w = "pre"
        try:
            raise ValueError("x")
        except ValueError as w:
            pass
        return w
    chk(e)
    def f():
        try:
            try:
                raise ValueError("in")
            except ValueError as w:
                try:
                    raise KeyError("k")
                except KeyError as w2:
                    raise IndexError("deep")
        except IndexError:
            pass
        return (w, w2)
    chk(f)
    def g():
        try:
            try:
                raise ValueError("in")
            except ValueError as w:
                raise
        except ValueError:
            pass
        return w
    chk(g)
    def h():
        try:
            try:
                raise ValueError("in")
            except ValueError as w:
                raise KeyError("k")
            finally:
                print("fin")
        except KeyError:
            pass
        return w
    chk(h)
    def i():
        try:
            raise ValueError("r")
        except ValueError as w:
            return str(w)
    chk(i)
    def j():
        try:
            raise ValueError("r")
        except ValueError as w:
            return w
        finally:
            print("fin j")
    chk(j)
    def k():
        try:
            raise ValueError("r")
        except ValueError as w:
            x = lambda: w
            return 5
    chk(k)
    def l():
        try:
            raise ValueError("r")
        except ValueError as w:
            def inner():
                return w
            r = inner()
        try:
            return inner()
        except NameError as ne:
            return "NE " + str(ne)
    chk(l)
    def m():
        out = []
        for i in range(4):
            try:
                if i % 2:
                    raise ValueError(i)
                out.append(i)
            except ValueError as w:
                out.append(w.args[0] * 10)
                if i == 3:
                    break
        return out, w
    chk(m)
    def n():
        try:
            raise ValueError("a")
        except ValueError as w:
            try:
                1 / 0
            except ZeroDivisionError:
                pass
            return w.args
    chk(n)
    def o():
        try:
            raise ValueError("a")
        except ValueError as w:
            pass
        try:
            raise KeyError("b")
        except KeyError as w:
            return w.args
    chk(o)
    def p():
        x = {}
        try:
            raise ValueError("a")
        except ValueError as w:
            x["k"] = w
            q = len(x)
        return x["k"].args, q
    chk(p)
main()
"""

EXC_Q2 = r"""class E(Exception):
    pass
def main():
    r = []
    for i in range(3):
        try:
            try:
                raise E(i)
            except E as err:
                r.append(str(err))
                if i == 1:
                    raise ValueError("v")
        except ValueError as e2:
            r.append("v%d" % i)
            continue
        r.append("ok")
    print(r)
    try:
        print(err)
    except UnboundLocalError:
        print("ub err")
    try:
        print(e2)
    except UnboundLocalError:
        print("ub e2")
    def f():
        try:
            1/0
        except ZeroDivisionError as z:
            raise
    try:
        f()
    except ZeroDivisionError as q:
        print("zd", q)
    try:
        f()
    except ZeroDivisionError as q:
        print("zd", q)
    z = 5
    try:
        int("x")
    except ValueError as z:
        print(z)
    try:
        print(z)
    except UnboundLocalError:
        print("ub z")
main()
"""

EXC_Q3 = r"""class K:
    def m(self, x):
        try:
            return 10 // x
        except ZeroDivisionError as e:
            return len(str(e))
def t(x):
    s = 0
    for i in range(x):
        try:
            s += 10 // (i - 2)
        except ZeroDivisionError as e:
            s += 100
            if i > 5:
                break
            continue
    return s
def gen(n):
    for i in range(n):
        try:
            if i == 1:
                raise ValueError(i)
            yield i
        except ValueError as e:
            yield -e.args[0]
def main():
    print(K().m(0), K().m(5), t(4), t(9), list(gen(3)))
    try:
        1/0
    except ZeroDivisionError as e:
        print("c", e)
    try:
        print(e)
    except NameError as n:
        print("NameError")
main()
"""

class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="ail-fuzz1-")
        self.dir = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def build(self, src, general):
        path = self.dir / "p.py"
        path.write_text(src, encoding="utf-8")
        env = dict(os.environ, AIL_NO_CACHE="1", AIL_QUIET_FALLBACK="1")
        env.pop("AIL_UNIFIED_FORCE", None)
        if general:
            env["AIL_UNIFIED_FORCE"] = "1"
        exe = self.dir / ("exe_g" if general else "exe_d")
        built = subprocess.run([sys.executable, "-B", CLI, "compile", str(path), "--syntax", "python", "-o", str(exe)],
                               cwd=self.dir, capture_output=True, text=True, env=env)
        return built, exe

    def same(self, src):
        path = self.dir / "ref.py"
        path.write_text(src, encoding="utf-8")
        code, out = run_py(path)
        for general in (False, True):
            built, exe = self.build(src, general)
            self.assertEqual(built.returncode, 0, built.stdout + built.stderr)
            ran = subprocess.run([str(exe)], capture_output=True, timeout=60)
            self.assertEqual(ran.stdout, out, "general" if general else "default")
            self.assertEqual(ran.returncode, code)
        return out

    def refused(self, src, word):
        path = self.dir / "ref.py"
        path.write_text(src, encoding="utf-8")
        code, out = run_py(path)
        self.assertNotEqual(code, 0)          # CPython fails (NameError), prints nothing before the def
        for general in (False, True):
            built, _ = self.build(src, general)
            self.assertNotEqual(built.returncode, 0, "built a program CPython rejects")
            self.assertIn(word, built.stdout + built.stderr)


class NonLiteralDefaults(Base):
    def test_defaults_evaluated_once_at_def(self):
        out = self.same(P_NAMES)
        self.assertIn(b"(4, -2)\n", out)     # X was 2 when the defs ran, main set it to 3 later

    def test_defaults_with_global_changes(self):
        out = self.same(P_GLOBALS)
        self.assertTrue(out)

    def test_never_set_global_is_name_error_like_cpython(self):
        # Z is assigned only inside setz(): CPython raises NameError at the def, before "start"
        src = """def f(a=Z):
    return a
def setz():
    global Z
    Z = 1
def main():
    print("start")
    setz()
    print(f())
main()
"""
        path = self.dir / "ref.py"
        path.write_text(src, encoding="utf-8")
        code, out = run_py(path)
        self.assertEqual((code, out), (1, b""))
        for general in (False, True):
            built, exe = self.build(src, general)
            if built.returncode != 0:
                self.assertIn("Z", built.stdout + built.stderr)
                continue
            ran = subprocess.run([str(exe)], capture_output=True, timeout=60)
            self.assertEqual((ran.returncode, ran.stdout), (1, b""))
            self.assertIn(b"NameError: name 'Z' is not defined", ran.stderr)

    def test_forward_referenced_function_default_refused(self):
        self.refused(F_FORWARD, "defined after the def")
        self.refused(F_FORWARD2, "defined after the def")

    def test_class_attribute_default_refused_or_same(self):
        # the default is the class attribute X (5); a module X defined later must not be used
        path = self.dir / "ref.py"
        path.write_text(F_UNDEF, encoding="utf-8")
        code, out = run_py(path)
        self.assertEqual((code, out), (0, b"5\n"))
        for general in (False, True):
            built, exe = self.build(F_UNDEF, general)
            if built.returncode != 0:
                continue                      # refused by name: fine
            ran = subprocess.run([str(exe)], capture_output=True, timeout=60)
            self.assertEqual(ran.stdout, out)

    # the review's four probes (p1, p2a, p2b, p3): every non-literal default keeps the value it had
    # when the `def` ran, the value it computed, and the one mutable object it made
    def test_p1_review_nonliteral_defaults(self):
        out = self.same(P1)
        self.assertEqual(out, b"2 (4, -2) ('el', 'HELLO') (9, 7, 2)\n")

    def test_p2a_review_function_builtin_kwonly_method(self):
        out = self.same(P2A)
        self.assertEqual(out, b"(5, 4, 4) 14 12\n(5, 4, 1) 2 3\n(1, 's') (7, 's') (1, 'z')\n")

    def test_p2b_review_default_calls_a_function_once_in_order(self):
        out = self.same(P2B)
        self.assertEqual(out, b"bump 1\nstart 1\n(1, 1)\n(1, 1)\n1\n")

    def test_p3_review_mutable_default_shared(self):
        out = self.same(P3)
        self.assertEqual(out, b"(3, 't') (4, 't') (5, 't')\n[1, 2, 2, 3, 4]\n5 5\n5\n")


class ForwardLambdaDefaults(Base):
    """Item 1: a lambda default that refers to a function defined later. CPython evaluates the default
    where the lambda is made (NameError / UnboundLocalError there), so AIL must refuse by name; before,
    `h = lambda a=g(): a` with `def g()` below printed `start`, `1` and exited 0."""

    def test_forward_reference_refused(self):
        for src in (U3, U3_CALLED_EARLY, U3_VALUE, U3_CLASS_BODY, U3_KWONLY):
            self.refused(src, "default in a lambda uses g")

    def test_local_function_bound_later_refused(self):
        # `g` is a local of main that only becomes bound at its nested `def` below the lambda
        self.refused(U3_LOCAL, "bound after the point where the lambda is made")

    def test_local_read_before_a_later_reassignment_still_builds(self):
        # x is bound before the lambda, so the later `x = 2` does not matter: CPython prints 1
        self.assertEqual(self.same(U3_LOCAL_EARLIER), b"1\n")

    def test_global_rebind_is_not_a_local(self):
        # `global X` makes the later `X = 2` a module write, not a local: the default reads 1
        self.assertEqual(self.same(U3_GLOBAL_REBIND), b"1 2\n")

    def test_lambda_made_after_the_binding_still_builds(self):
        self.assertEqual(self.same(U3_AFTER_BINDING), b"1\n")

    def test_method_lambda_made_after_the_binding_still_builds(self):
        self.assertEqual(self.same(U3_AFTER_BINDING2), b"3\n")

    def test_backward_lambda_defaults_evaluated_once(self):
        out = self.same(L_DEFAULTS)
        self.assertEqual(out, b"k\n2 [1, 2] 7 7\n3 3 5\n3 3\n")


class HashValues(Base):
    """hash() of an int / bool / float / None / tuple, and of an instance with __hash__, is CPython's number
    (found by difffuzz seed 305: `hash(-9007199254740993) > -0.0` took the other branch, so a later
    `except` clause ran for the wrong exception)."""

    def test_int_float_none_tuple(self):
        out = self.same(H_VALUES)
        self.assertIn(b"-9007199254740993 9007199254740993\n", out)

    def test_instance_with_hash_method(self):
        out = self.same(H_INSTANCES)
        self.assertIn(b"17 -2 1099511627776", out)

    def test_bad_and_raising_hash_methods(self):
        out = self.same(H_ODD)
        self.assertIn(b"TypeError __hash__ method should return an integer", out)

    def test_hash_in_a_class_and_a_set(self):
        self.same(H_CLASS_SET)

    def test_seed_305_except_branch(self):
        out = self.same(H_EXCEPT)
        self.assertEqual(out, b"outer IndexError\n")


class ExceptAsUnbinding(Base):
    """`except E as n:` ends with `del n` however the handler is left (found by difffuzz seed 101; the
    reviewer's probes): break / continue, a raise out of the handler, a return, a closure's cell."""

    def test_break_out_of_handler(self):
        self.assertEqual(self.same(EXC_P1), b"ub\n")

    def test_raise_out_of_handler_into_enclosing_try(self):
        self.assertEqual(self.same(EXC_P2), b"ub\n")

    def test_closure_cell_is_emptied(self):
        self.assertEqual(self.same(EXC_P3), b"")      # NameError, exit 1, as CPython

    def test_all_exits_of_a_handler(self):
        out = self.same(EXC_Q1)
        self.assertEqual(out.count(b"UB cannot access local"), 9)
        self.assertIn(b"NE cannot access free variable 'w'", out)

    def test_nested_reuse_and_reraise(self):
        out = self.same(EXC_Q2)
        self.assertIn(b"ub err\nub e2\n", out)

    def test_methods_typed_loops_generators_module_level(self):
        self.same(EXC_Q3)


class Generator(unittest.TestCase):
    def test_seed_is_deterministic_and_valid(self):
        tool = ROOT.parent / "tools" / "difffuzz.py"
        a = subprocess.run([sys.executable, str(tool), "--seed", "7"], capture_output=True, text=True).stdout
        b = subprocess.run([sys.executable, str(tool), "--seed", "7"], capture_output=True, text=True).stdout
        self.assertEqual(a, b)
        self.assertIn("def main():", a)
        self.assertTrue(a.rstrip().endswith("main()"))
        compile(a, "seed7", "exec")

    def test_minimizer_shrinks(self):
        # the shrinker must keep a program that still differs and drop a statement that does not matter;
        # tested on its pure parts (no build): the Pass body is not "shrunk" again and again
        sys.path.insert(0, str(ROOT.parent / "tools"))
        import difffuzz
        calls = []
        orig = difffuzz.ail_differs
        difffuzz.ail_differs = lambda src, mode, tmp, cp0: (calls.append(src) or "KEEP" in src)
        try:
            src = "def main():\n    x = 1\n    y = 2\n    print('KEEP')\nmain()\n"
            path = Path(tempfile.mkdtemp()) / "m.py"
            path.write_text(src)
            out = difffuzz.minimize(str(path), "d")
        finally:
            difffuzz.ail_differs = orig
        self.assertIn("KEEP", out)
        self.assertNotIn("x = 1", out)
        self.assertNotIn("y = 2", out)
        self.assertLess(len(calls), 40)


if __name__ == "__main__":
    unittest.main()

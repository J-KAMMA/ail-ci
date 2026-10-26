"""A local read where it may be unassigned raises CPython's UnboundLocalError on the typed path too (DIFFERENCES C76).

    def f(a):
        if a > 0:
            z = a
        return z          # f(-1): the typed path used to give 0

unbound.py does a must-assigned dataflow per function and gives a variable a flag only where a read may find it
unassigned.  Every program here is built by pyc.py under AIL_IR=1 and AIL_IR=0, once as the default build (typed path,
mixed clones) and once with --general-only, and must print what CPython prints with CPython's exit status.  The fixed
programs are also required to stay on the typed path in the default build (no "general path" note), so that the typed
code is what is being tested; one program per construct the task named: a branch, a loop that may run zero times, a
while loop, try/except/else/finally, match arms, augmented assignment, break/continue, nested functions reading outer
locals (CPython: NameError, "free variable" wording; the typed path refuses those and the general path answers),
`del`.  The randomized programs are generated from a seed (AIL_UNBOUND_SEEDS sets how many, default 6) and have
if/for/while/try/break/continue/return around assignments and reads of four variables and the loop variables.
Programs where every read is definitely assigned are not touched at all (checked by the byte-identical generated C of
the whole test suite's pins, and here by `test_definite_programs_get_no_flags`).
"""
import ast
import os
import random
import re
import subprocess
import sys
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / 'python' / 'pkg-v12'))

from test_ail_bugs7 import MODES, _cpython, build          # noqa: E402
import unbound                                              # noqa: E402

GENERAL = 'general path'


def _run(directory, name, text, stdin=''):
    """(stdout, exit status) of CPython and, per mode, of AIL, plus the build notes."""
    want = _cpython(directory, name, text, stdin)
    got = {}
    for mode, general, ir in MODES:
        exe, built = build(directory, name, text, ir, general)
        if built.returncode:
            got[(mode, ir)] = ('BUILD FAILED', (built.stdout + built.stderr)[-1500:], built.stderr)
            continue
        done = subprocess.run([str(exe)], input=stdin.encode(), capture_output=True, timeout=60, cwd=directory)
        got[(mode, ir)] = (done.stdout.replace(b'\r\n', b'\n'), done.returncode, built.stderr, done.stderr)
    return want, got


def call_block(calls, handler=True):
    """main(): every (function, args) in its own try so that the message of each UnboundLocalError is printed."""
    lines = ['def main():']
    for fn, args in calls:
        lines += ['    try:',
                  '        print(%s(%s))' % (fn, ', '.join(str(a) for a in args))]
        if handler:
            lines += ['    except UnboundLocalError as e:',
                      '        print("U", "%s", e)' % fn]
        lines += ['    except ZeroDivisionError:',
                  '        print("Z", "%s")' % fn]
    lines += ['main()', '']
    return '\n'.join(lines)


BRANCH = '''
def f1(a: int) -> int:
    if a > 0:
        z = a
    return z + 1

def f2(a: int) -> int:
    if a > 0:
        z = 1
    elif a < -5:
        z = 2
    return z

def f3(a: int) -> int:
    if a > 0:
        z = 1
    else:
        z = 2
    return z

def f4(a: int) -> int:
    if a > 2:
        y = 3
    if a > 0:
        z = a
        if a > 1:
            y = z
    return y + z

def f5(a: int) -> float:
    if a > 0:
        r = 1.5
    return r * 2.0

def f6(a: int) -> int:
    if a > 0:
        z = a
    t = 0
    if a > 0:
        t = z
    return t

def f7(a: int) -> int:
    n = 0
    if a > 0:
        z = a
        n += z
    if a > 5:
        n += z
    return n

def f8(a: int) -> int:
    x = 1 if a > 0 else 2
    if a > 3:
        z = x
    return x + (z if a > 4 else 0)
'''
BRANCH_CALLS = [('f%d' % i, [a]) for i in range(1, 9) for a in (-7, -1, 0, 1, 2, 4, 6)]

LOOPS = '''
def l1(n: int) -> int:
    for x in range(n):
        last = x
    return last

def l2(n: int) -> int:
    i = 0
    while i < n:
        last = i
        i += 1
    return last

def l3(n: int) -> int:
    for x in range(n):
        if x == 3:
            found = x
            break
    return found

def l5(n: int) -> int:
    total = 0
    for x in range(n):
        for y in range(x):
            deep = y
        total += deep
    return total

def l6(n: int) -> int:
    while True:
        k = n
        if k > 0:
            break
        n += 3
    return k

def l7(n: int) -> int:
    for x in range(n):
        pass
    return x

def l8(n: int) -> int:
    i = 0
    while i < n:
        i += 1
        if i == 2:
            continue
        seen = i
    return seen

def l9(n: int) -> int:
    t = 0
    for x in range(n):
        if x > 1:
            t += 1
        elif x == 0:
            m = 5
        else:
            t += m
    return t
'''
LOOP_CALLS = [('l%d' % i, [a]) for i in (1, 2, 3, 5, 6, 7, 8, 9) for a in (0, 1, 2, 4, 5)]

TRY = '''
def t1(n: int) -> int:
    try:
        v = 10 // n
    except ZeroDivisionError:
        pass
    return v

def t2(n: int) -> int:
    try:
        v = 10 // n
    except ZeroDivisionError:
        v = -1
    return v

def t3(n: int) -> int:
    try:
        v = 10 // n
    except ZeroDivisionError:
        return -9
    return v

def t4(n: int) -> int:
    try:
        w = 1
        v = 10 // n
    except ZeroDivisionError:
        pass
    return w

def t5(n: int) -> int:
    try:
        pass
    finally:
        q = n
    return q

def t6(n: int) -> int:
    try:
        v = 10 // n
    except ZeroDivisionError:
        u = 1
    else:
        u = 2
    return u + v

def t7(n: int) -> int:
    r = 0
    try:
        if n > 0:
            k = n
        r = 100 // (n - 1)
    finally:
        r += 1
    return r + k

def t8(n: int) -> int:
    for i in range(3):
        try:
            if i == n:
                raise ValueError("x")
            got = i
        except ValueError:
            continue
    return got
'''
TRY_CALLS = [('t%d' % i, [a]) for i in range(1, 9) for a in (0, 1, 2, 5)]

MATCH = '''
def m1(n: int) -> int:
    match n:
        case 0:
            z = 10
        case 1:
            z = 11
    return z

def m2(n: int) -> int:
    match n:
        case 0:
            z = 10
        case _:
            z = 12
    return z

def m3(n: int) -> int:
    match n:
        case 0:
            z = 10
        case 1:
            y = 3
        case _:
            z = 12
    return z

def m4(n: int) -> int:
    match n:
        case 0:
            return 5
        case k:
            z = k
    return z
'''
MATCH_CALLS = [('m%d' % i, [a]) for i in range(1, 5) for a in (0, 1, 2, 7)]

ELSE = '''
def e1(n: int) -> int:
    for x in range(n):
        if x == 3:
            found = x
            break
    else:
        found = -1
    return found

def e2(n: int) -> int:
    for x in range(n):
        if x == 3:
            break
    else:
        late = 1
    return late

def e3(n: int) -> int:
    for x in range(n):
        pass
    else:
        late = 5
    return late + x
'''
ELSE_CALLS = [('e%d' % i, [a]) for i in range(1, 4) for a in (0, 1, 4, 6)]

KINDS = '''
def s1(a: int) -> int:
    if a > 0:
        w = "x" * a
    return len(w + "!")

def s2(a: int) -> int:
    for i in range(a):
        t = str(i)
    return len(t)

def s3(a: int) -> bool:
    if a > 1:
        ok = a > 3
    return ok

def s4(a: int) -> float:
    n = 0.5
    while n < a:
        n *= 2.0
        last = n
    return last
'''
KINDS_CALLS = [('s%d' % i, [a]) for i in range(1, 5) for a in (0, 1, 2, 5)]

# containers and calls through a possibly-unassigned name: the typed path takes the name as written, so these may be
# built by the general path; the answers are CPython's all the same
CONTAINERS = '''
def c1(a: int) -> int:
    if a > 0:
        xs = [a, a + 1]
    return len(xs)

def c2(a: int) -> int:
    for i in range(a):
        d = {i: a}
    return d[0]

def c3(a: int) -> int:
    if a > 0:
        xs = [a]
    xs.append(3)
    return len(xs)

def c4(a: int) -> int:
    total = 0
    for i in range(a):
        acc = [i, i]
        total += len(acc)
    return total + len(acc)
'''
CONTAINER_CALLS = [('c%d' % i, [a]) for i in range(1, 5) for a in (0, 1, 3)]

AUG = '''
def g1(a: int) -> int:
    if a > 0:
        t = 1
    t += a
    return t

def g2(a: int) -> int:
    if a > 0:
        t = 1.5
    t *= 2.0
    return int(t)

def g3(a: int) -> int:
    for i in range(a):
        s = i
    s += 1
    return s
'''
AUG_CALLS = [('g%d' % i, [a]) for i in range(1, 4) for a in (0, 1, 3)]

# reads that are definitely assigned: none of these functions needs a flag
DEFINITE = '''
def d1(a: int) -> int:
    if a > 0:
        z = 1
    else:
        z = 2
    return z

def d2(a: int) -> int:
    for i in range(a):
        s = i
        t = s + 1
    return a

def d3(a: int) -> int:
    while True:
        k = a
        if k > 0:
            break
        a += 1
    return k

def d4(a: int) -> int:
    try:
        v = 10 // a
    except ZeroDivisionError:
        v = 0
    return v

def d5(a: int) -> int:
    if a > 0:
        return 1
    z = a
    return z
'''


class Unbound(unittest.TestCase):
    def check(self, name, text, calls, typed=True, extra='', handler=True):
        full = text + extra + '\n' + call_block(calls, handler)
        with tempfile.TemporaryDirectory(prefix='ail-unbound-') as directory:
            want, got = _run(directory, name, full)
            self.compare(name, want, got, typed)

    def compare(self, name, want, got, typed):
        for (mode, ir), result in got.items():
            with self.subTest(program=name, mode=mode, ir=ir):
                self.assertNotEqual(result[0], 'BUILD FAILED', result[1])
                self.assertEqual((result[0], result[1]), want, result[3].decode(errors='replace') if len(result) > 3 else '')
                if typed and mode == 'default':
                    self.assertNotIn(GENERAL, result[2], result[2][-600:])

    def test_branch(self):
        self.check('branch', BRANCH, BRANCH_CALLS)

    def test_loops(self):
        self.check('loops', LOOPS, LOOP_CALLS)

    def test_try(self):
        self.check('try', TRY, TRY_CALLS)

    def test_match(self):
        """A match statement is lowered to an if/elif chain (matchlower.py) before either path sees it."""
        import ail_syntax
        lowered = ail_syntax._matchlower().rewrite(MATCH)
        self.assertNotIn('match ', lowered)
        full = MATCH + '\n' + call_block(MATCH_CALLS)
        with tempfile.TemporaryDirectory(prefix='ail-unbound-') as directory:
            want = _cpython(directory, 'match', full, '')
            got = _run(directory, 'matchlow', lowered + '\n' + call_block(MATCH_CALLS))[1]
            self.compare('match', want, got, True)

    def test_for_else(self):
        self.check('else', ELSE, ELSE_CALLS, typed=False)

    def test_kinds(self):
        self.check('kinds', KINDS, KINDS_CALLS)

    def test_containers(self):
        self.check('containers', CONTAINERS, CONTAINER_CALLS, typed=False)

    def test_augmented(self):
        self.check('aug', AUG, AUG_CALLS)

    def test_exception_classes(self):
        """The error is a NameError and an Exception; `type(e).__name__`, repr and args are CPython's."""
        text = '''
def f(a: int) -> int:
    if a > 0:
        z = a
    return z

def main():
    for a in range(-1, 3):
        try:
            print(f(a))
        except NameError as e:
            print("N", e, type(e).__name__, repr(e))
        try:
            print(f(a))
        except Exception as e:
            print("E", str(e))
        try:
            print(f(a))
        except ValueError:
            print("not here")
        except UnboundLocalError as e:
            print("U", e.args)
main()
'''
        with tempfile.TemporaryDirectory(prefix='ail-unbound-') as directory:
            want, got = _run(directory, 'classes', text)
            self.compare('classes', want, got, True)

    def test_uncaught(self):
        text = 'def f(a: int) -> int:\n    if a > 0:\n        z = a\n    return z\n\nprint(f(1))\nprint(f(0))\n'
        with tempfile.TemporaryDirectory(prefix='ail-unbound-') as directory:
            for mode, general, ir in MODES:
                exe, built = build(directory, 'uncaught', text, ir, general)
                self.assertEqual(built.returncode, 0, built.stderr[-1500:])
                done = subprocess.run([str(exe)], capture_output=True, timeout=60, cwd=directory)
                with self.subTest(mode=mode, ir=ir):
                    self.assertEqual(done.returncode, 1)
                    self.assertEqual(done.stdout.replace(b'\r\n', b'\n'), b'1\n')
                    self.assertEqual(done.stderr.decode().strip().splitlines()[-1],
                                     "UnboundLocalError: cannot access local variable 'z' where it is not "
                                     "associated with a value")

    def test_script_level_code(self):
        """Top-level statements are module scope in CPython: an unassigned read is a NameError, 'name is not defined'."""
        text = (
            "n = 0\n"
            "for i in range(n):\n"
            "    last = i\n"
            "try:\n"
            "    print(last)\n"
            "except NameError as e:\n"
            "    print('N', e, type(e).__name__)\n"
            "k = 2\n"
            "if k > 3:\n"
            "    z = 5\n"
            "try:\n"
            "    print(z + 1)\n"
            "except NameError as e:\n"
            "    print('N2', e)\n"
            "print(z)\n")
        with tempfile.TemporaryDirectory(prefix='ail-unbound-') as directory:
            want, got = _run(directory, 'script', text)
            self.assertEqual(want[1], 1)
            self.compare('script', want, got, True)

    def test_mixed_mode_clone_is_not_made(self):
        """A boxed program's int function would get a typed clone; one that may read an unassigned local does not
        (the clone could not raise into the boxed handlers), so the boxed code answers."""
        text = (
            "def f(a):\n"
            "    if a > 0:\n"
            "        z = a\n"
            "    return z\n"
            "\n"
            "def h(a):\n"
            "    return a * 2 + 1\n"
            "\n"
            "def g(n):\n"
            "    d = {'k': [n]}\n"
            "    d['k'].append(f(n))\n"
            "    return d\n"
            "\n"
            "def main():\n"
            "    for k in range(-2, 3):\n"
            "        try:\n"
            "            print(g(k), h(k))\n"
            "        except UnboundLocalError as e:\n"
            "            print('U', e, h(k))\n"
            "main()\n")
        with tempfile.TemporaryDirectory(prefix='ail-unbound-') as directory:
            want = _cpython(directory, 'mixed', text, '')
            for ir in ('0', '1'):
                exe, built = build(directory, 'mixed', text, ir, False)
                self.assertEqual(built.returncode, 0, built.stderr[-1500:])
                done = subprocess.run([str(exe)], capture_output=True, timeout=60, cwd=directory)
                with self.subTest(ir=ir):
                    self.assertEqual((done.stdout.replace(b'\r\n', b'\n'), done.returncode), want)
                    for c in Path(directory).glob('exe_mixed_%s_0_mix*.c' % ir):
                        self.assertNotIn('f__typed', c.read_text(errors='replace'), c.name)

    def test_nested_function_reads_outer_local(self):
        """NameError, 'free variable': the typed path refuses it, the general path (and CPython) say the same thing."""
        text = '''
def h(n: int) -> int:
    def inner() -> int:
        return q + 1
    if n:
        q = 5
    try:
        return inner()
    except NameError as e:
        print("free", e, type(e).__name__, isinstance(e, UnboundLocalError))
    return -2

def ok(n: int) -> int:
    base = n + 1
    def inner(x: int) -> int:
        return x + base
    return inner(2)

def late(n: int) -> int:
    def inner(x: int) -> int:
        return x + base
    base = n * 2
    return inner(1)

def main():
    print(h(0))
    print(h(1))
    print(ok(4))
    print(late(4))
main()
'''
        with tempfile.TemporaryDirectory(prefix='ail-unbound-') as directory:
            want, got = _run(directory, 'free', text)
            self.compare('free', want, got, False)

    def test_del(self):
        text = '''
def k(n: int) -> int:
    x = n + 1
    del x
    try:
        return x
    except UnboundLocalError as e:
        print(e)
    return -1

def j(n: int) -> int:
    if n > 0:
        x = n
    try:
        del x
    except UnboundLocalError as e:
        print(e)
    return n

print(k(1))
print(j(1))
print(j(0))
'''
        with tempfile.TemporaryDirectory(prefix='ail-unbound-') as directory:
            want, got = _run(directory, 'del', text)
            self.compare('del', want, got, False)

    def test_general_path_proven_reads(self):
        """General path (cbloat): a read of a parameter, or of a local assigned on every path to it, has no
        UnboundLocalError check; every read that is not proven keeps it and raises as CPython does."""
        text = '''
def g1(c):
    if c:
        x = 1
    return x

def g2(c):
    if c:
        x = 1
    else:
        x = 2
    return x

def g3(n):
    for i in range(n):
        y = i
    return y, i

def g4(n):
    while n > 0:
        z = n
        n -= 1
    return z

def g5(c):
    try:
        v = int(c)
    except ValueError:
        pass
    return v

def g6(c):
    try:
        v = int(c)
    except ValueError:
        return -1
    return v

def g7(c):
    try:
        w = 1
        if c:
            raise KeyError
        q = 2
    except KeyError:
        return w, q
    finally:
        r = 5
    return w, q, r

def g8(c):
    x = 1
    for _ in range(3):
        if c:
            print(x)
            del x
        c = True
    return 0

def g9(c):
    if c > 0:
        x = 1
    elif c < 0:
        x = 2
    return x

def g10(a, b):
    a, b = b, a
    a += b
    return a, b

def g11(c):
    if c:
        return 1
    else:
        m = 2
    return m

def g12(n):
    while True:
        if n > 3:
            t = n
            break
        n += 1
    return t

def g13(c):
    for i in range(2):
        if i == 1:
            u += 1
        else:
            u = 0
    return u

def g14(c):
    if c:
        yy = 1
    return [yy for _ in range(1)]
'''
        calls = [('g1', [1]), ('g1', [0]), ('g2', [0]), ('g3', [2]), ('g3', [0]), ('g4', [3]), ('g4', [0]),
                 ('g5', ['"1"']), ('g5', ['"a"']), ('g6', ['"a"']), ('g6', ['"3"']), ('g7', [0]), ('g7', [1]),
                 ('g8', [False]), ('g9', [0]), ('g9', [3]), ('g10', [1, 2]), ('g11', [0]), ('g11', [1]),
                 ('g12', [0]), ('g13', [0]), ('g14', [0]), ('g14', [1])]
        self.check('general_proven', text, calls, typed=False)

    def test_general_path_c_has_no_check_on_params(self):
        text = 'def f(x):\n    y = x + 1\n    return y * x\nprint(f(3))\n'
        with tempfile.TemporaryDirectory(prefix='ail-unbound-') as directory:
            src = Path(directory) / 'p.py'
            src.write_text(text)
            env = dict(os.environ, AIL_UNIFIED_FORCE='1', AIL_NO_CACHE='1')
            done = subprocess.run([sys.executable, str(Path(__file__).resolve().parent / 'ail_chatgpt.py'), 'compile',
                                   str(src), '--syntax', 'python', '--debug-dir', str(Path(directory) / 'dbg'),
                                   '-o', str(Path(directory) / 'exe')], capture_output=True, text=True, env=env)
            self.assertEqual(done.returncode, 0, done.stderr)
            c = (Path(directory) / 'dbg' / 'program.c').read_text()
            body = c[c.index('/* ---- functions and methods'):c.index('/* ---- module body')]
            self.assertNotIn('ail_op_load(', body)
            self.assertIn('ail_op_mul(', body)

    def test_definite_programs_get_no_flags(self):
        tree = ast.parse(DEFINITE)
        self.assertEqual(unbound.census(tree), {})
        self.assertEqual(unbound.census(ast.parse(BRANCH)), {'f1': ['z'], 'f2': ['z'], 'f4': ['y', 'z'], 'f5': ['r'],
                                                             'f6': ['z'], 'f7': ['z'], 'f8': ['z']})
        self.assertEqual(unbound.census(ast.parse(LOOPS)), {'l1': ['last'], 'l2': ['last'], 'l3': ['found'],
                                                            'l5': ['deep'], 'l7': ['x'], 'l8': ['seen'], 'l9': ['m']})
        self.assertEqual(unbound.census(ast.parse(TRY)), {'t1': ['v'], 't4': ['w'], 't6': ['v'], 't7': ['k'],
                                                          't8': ['got']})
        self.assertEqual(unbound.census(ast.parse(MATCH)), {'m1': ['z'], 'm3': ['z']})
        self.assertEqual(unbound.census(ast.parse(AUG)), {'g1': ['t'], 'g2': ['t'], 'g3': ['s']})
        # the definite program is left byte-for-byte alone by the pass
        tree = ast.parse(DEFINITE)
        before = ast.dump(tree)
        self.assertEqual(unbound.rewrite(tree, RuntimeError), 0)
        self.assertEqual(ast.dump(tree), before)

    def test_definite_programs_run(self):
        calls = [('d%d' % i, [a]) for i in (1, 2, 3, 4, 5) for a in (0, 1, 3)]
        self.check('definite', DEFINITE, calls, handler=False)

    def test_analysis_unit(self):
        def flagged(src):
            return unbound.census(ast.parse(src))
        self.assertEqual(flagged('def f(a):\n    if a:\n        z = 1\n    return z\n'), {'f': ['z']})
        self.assertEqual(flagged('def f(a):\n    if a:\n        z = 1\n    else:\n        z = 2\n    return z\n'), {})
        self.assertEqual(flagged('def f(a):\n    while True:\n        z = a\n        if z:\n            break\n    return z\n'), {})
        self.assertEqual(flagged('def f(a):\n    while a:\n        z = a\n        a -= 1\n    return z\n'), {'f': ['z']})
        self.assertEqual(flagged('def f(a):\n    try:\n        z = 1\n    except E:\n        raise\n    return z\n'), {})
        self.assertEqual(flagged('def f(a):\n    try:\n        z = 1\n    except E:\n        pass\n    return z\n'), {'f': ['z']})
        self.assertEqual(flagged('def f(a):\n    if a:\n        z = 1\n    else:\n        sys.exit(1)\n    return z\n'), {})
        self.assertEqual(flagged('def f(a):\n    for i in a:\n        pass\n    return i\n'), {'f': ['i']})
        self.assertEqual(flagged('def f(a):\n    x = [i for i in a]\n    return x, i\n'), {})   # a global i
        self.assertEqual(flagged('def f(a):\n    if a:\n        z = 1\n    return [z for _ in a]\n'), {'f': ['z']})
        self.assertEqual(flagged('def f(a):\n    y = a and (z := 2)\n    return z\n'), {'f': ['!\'z\' may be unassigned and is bound by a walrus']})
        self.assertEqual(flagged('def f(a):\n    if a:\n        z = 1\n    return lambda: z\n'),
                         {'f': ["!'z' is read by a nested lambda before this function has assigned it "
                                "(CPython: NameError, free variable)"]})
        self.assertEqual(flagged('def f(a):\n    z = 1\n    return lambda: z\n'), {})


# ---- randomized programs -------------------------------------------------------------------------------------

VARS = ('v0', 'v1', 'v2', 'v3')


class Gen(object):
    def __init__(self, rnd):
        self.r = rnd
        self.loops = []          # kinds of the enclosing loops, innermost last
        self.depth = 0
        self.loop_vars = []
        self.counter = 0
        self.in_try = 0
        self.nojump = 0

    def var(self):
        pool = list(VARS) + list(self.loop_vars) * 2
        return self.r.choice(pool)

    def term(self):
        k = self.r.random()
        if k < 0.25:
            return str(self.r.randint(0, 5))
        if k < 0.4:
            return 'a'
        return self.var()

    def expr(self):
        e = self.term()
        for _ in range(self.r.choice((0, 0, 1, 2))):
            op = self.r.choice(('+', '-', '+'))
            e = '%s %s %s' % (e, op, self.term())
        if self.r.random() < 0.12:
            e = '(%s) * %d' % (e, self.r.randint(0, 3))
        if self.in_try and self.r.random() < 0.3:
            e = '%s // (a - %d)' % (self.term(), self.r.randint(0, 3))
        return e

    def cond(self):
        k = self.r.random()
        if k < 0.4:
            return 'a %s %d' % (self.r.choice(('>', '<', '==', '>=')), self.r.randint(-1, 4))
        if k < 0.55:
            return 'a %% 2 == %d' % self.r.randint(0, 1)
        return '%s %s %d' % (self.var(), self.r.choice(('>', '<', '==')), self.r.randint(0, 5))

    def block(self, indent, n=None):
        n = n or self.r.randint(1, 2)
        out = []
        for _ in range(n):
            out += self.stmt(indent)
        return out

    def stmt(self, indent):
        pad = '    ' * indent
        k = self.r.random()
        deep = self.depth >= 2
        if k < 0.25:
            return [pad + '%s = %s' % (self.r.choice(VARS), self.expr())]
        if k < 0.35:
            return [pad + '%s += %s' % (self.r.choice(VARS), self.expr())]
        if k < 0.45:
            return [pad + 'print(%s)' % self.expr()]
        if k < 0.50 and self.loops and not self.nojump:
            word = self.r.choice(('break', 'continue'))
            return [pad + 'if %s:' % self.cond(), pad + '    ' + word]
        if k < 0.53:
            return [pad + 'if %s:' % self.cond(), pad + '    return %s' % self.expr()]
        if deep:
            return [pad + '%s = %s' % (self.r.choice(VARS), self.expr())]
        self.depth += 1
        try:
            if k < 0.68:
                out = [pad + 'if %s:' % self.cond()] + self.block(indent + 1)
                if self.r.random() < 0.3:
                    out += [pad + 'elif %s:' % self.cond()] + self.block(indent + 1)
                if self.r.random() < 0.5:
                    out += [pad + 'else:'] + self.block(indent + 1)
                return out
            if k < 0.80:
                name = 'i%d' % self.counter
                self.counter += 1
                bound = self.r.choice(('a % 4', '3', '2', '0', 'a % 3'))
                self.loops.append('for')
                self.loop_vars.append(name)
                try:
                    body = self.block(indent + 1)
                finally:
                    self.loops.pop()
                return [pad + 'for %s in range(%s):' % (name, bound)] + body
            if k < 0.88:
                name = 'w%d' % self.counter
                self.counter += 1
                self.loops.append('while')
                try:
                    body = self.block(indent + 1)
                finally:
                    self.loops.pop()
                return ([pad + '%s = 0' % name, pad + 'while %s < %d:' % (name, self.r.randint(1, 3)),
                         pad + '    %s += 1' % name] + body)
            fin = self.r.random() < 0.25
            self.in_try += 1
            self.nojump += fin
            try:
                out = [pad + 'try:'] + self.block(indent + 1)
                out += [pad + 'except ZeroDivisionError:'] + self.block(indent + 1)
                if self.r.random() < 0.25:
                    out += [pad + 'else:'] + self.block(indent + 1)
            finally:
                self.in_try -= 1
                self.nojump -= fin
            if fin:
                self.nojump += 1
                try:
                    out += [pad + 'finally:'] + self.block(indent + 1)
                finally:
                    self.nojump -= 1
            return out
        finally:
            self.depth -= 1

    def function(self, i):
        self.loops, self.loop_vars, self.depth, self.counter, self.in_try, self.nojump = [], [], 0, 0, 0, 0
        body = self.block(1, self.r.randint(2, 4))
        # a name that is never assigned in the function is a global (NameError), and the typed path wants a
        # name's first textual occurrence to be an assignment: every variable gets a binding that never runs
        # (a > 99), which leaves its reads maybe-unassigned for the analysis and fine for the type lookup
        for v in reversed(VARS):
            body.insert(0, '    if a > 99:\n        %s = 0' % v)
        return '\n'.join(['def f%d(a: int) -> int:' % i] + body + ['    return %s' % self.expr(), ''])

    def program(self, nfun=3):
        funcs = [self.function(i) for i in range(nfun)]
        calls = [('f%d' % i, ['k - 2']) for i in range(nfun)]
        main = ['def main():', '    for k in range(9):']
        for i in range(nfun):
            main += ['        try:',
                     '            print("f%d", f%d(k - 2))' % (i, i),
                     '        except UnboundLocalError as e:',
                     '            print("U%d", e)' % i,
                     '        except ZeroDivisionError:',
                     '            print("Z%d")' % i]
        return '\n\n'.join(funcs) + '\n\n' + '\n'.join(main) + '\nmain()\n'


class Random(unittest.TestCase):
    def test_random_programs(self):
        seeds = int(os.environ.get('AIL_UNBOUND_SEEDS', '6'))
        base = int(os.environ.get('AIL_UNBOUND_BASE', '20261020'))
        texts = [(seed, Gen(random.Random(base + seed)).program()) for seed in range(seeds)]
        for seed, text in texts:
            ast.parse(text)

        def one(item):
            seed, text = item
            with tempfile.TemporaryDirectory(prefix='ail-unbound-r%d-' % seed) as directory:
                return seed, text, _run(directory, 'rand%d' % seed, text)

        flagged = 0
        typed = 0
        with ThreadPoolExecutor(max_workers=min(4, seeds)) as pool:
            for seed, text, (want, got) in pool.map(one, texts):
                flagged += bool(unbound.census(ast.parse(text)))
                typed += GENERAL not in got[('default', '1')][2]
                for (mode, ir), result in got.items():
                    with self.subTest(seed=seed, mode=mode, ir=ir):
                        self.assertNotEqual(result[0], 'BUILD FAILED', result[1])
                        self.assertEqual((result[0], result[1]), want,
                                         'seed %d (AIL_UNBOUND_BASE=%d)\n%s\n%s' % (
                                             seed, base, text, result[3].decode(errors='replace') if len(result) > 3 else ''))
        # the generator has to exercise the flags and the typed path, not only the general one
        self.assertGreaterEqual(flagged, max(1, seeds // 2))
        self.assertGreaterEqual(typed, max(1, seeds // 2))


if __name__ == '__main__':
    unittest.main()

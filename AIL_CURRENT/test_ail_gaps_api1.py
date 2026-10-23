"""API gaps of the general path (DIFFERENCES C92 .. 7), against CPython 3.12.

1. `collections.deque` methods on a deque that reaches the call as an unknown value (a function argument, a list item, an
   attribute, a dict value): `insert`, `rotate` (positive, negative, larger than len), `index`, `remove`, `count`, `reverse`,
   and `append`, `extend`, `pop` (they went to the two-element wrapper list `[data, maxlen]`). The exceptions have the text of
   CPython: `5 is not in deque`, `deque already at its maximum size`, `deque.pop() takes no arguments (1 given)`.
   `deque + deque`, `q += iterable`, `list += iterable`.
2. `repr()` / `print()` of a `defaultdict`: `defaultdict(<class 'list'>, {...})` for int, list, set, str, dict, a class, `None`,
   `defaultdict(<function f at 0x...>, {...})` for a function or lambda (the address differs from run to run in CPython too, so
   the test compares everything but the address).
3. `list + Counter` and the other operands: `can only concatenate list (not "Counter") to list`, `unsupported operand type(s)
   for +: 'Counter' and 'list'`, uncaught: exit status 1.

4. Boundary programs: `q.extend(q)` of a local deque, `deque + deque(maxlen=1)`, `Counter += [1]` (AttributeError), the
   defaultdict forms `(factory, mapping)`, `(factory, k=v)`, `()`, `None`, `tuple`, nested lambda, a container that holds
   itself in `repr`, a lambda in a call of the tuple pass (a compiler crash), `recv.method(*xs)`, `deque.maxlen`.

Programs are generated from fixed seeds, built with the general path forced and with the default build; stdout and the exit
status must match CPython.
"""
import os
import random
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent
CHATGPT = str(ROOT / 'ail_chatgpt.py')
HAVE_CC = shutil.which('gcc') is not None


def _cpython(directory, name, text):
    src = Path(directory) / (name + '_cpython.py')
    src.write_text(text, encoding='utf-8')
    done = subprocess.run([sys.executable, '-B', str(src)], capture_output=True, timeout=120,
                          env=dict(os.environ, PYTHONUTF8='1'))
    return done.stdout.replace(b'\r\n', b'\n'), done.returncode, _last_line(done.stderr)


def _last_line(err):
    lines = [x for x in err.decode('utf-8', 'replace').splitlines() if x.strip()]
    return lines[-1] if lines else ''


def _build_run(directory, name, text, general):
    src = Path(directory) / (name + '.ail')
    src.write_text(text, encoding='utf-8')
    exe = Path(directory) / ('exe_' + name + ('_g' if general else '_d'))
    env = dict(os.environ, AIL_NO_CACHE='1', AIL_QUIET_FALLBACK='1')
    env.pop('AIL_NO_GENERAL', None)
    if general:
        env['AIL_UNIFIED_FORCE'] = '1'
    cmd = [sys.executable, '-B', CHATGPT, 'compile', src.name, '--syntax', 'python', '-o', exe.name]
    built = subprocess.run(cmd, cwd=directory, capture_output=True, text=True, timeout=900, env=env)
    if built.returncode != 0:
        return None, (built.stdout + built.stderr)[-1500:]
    got = subprocess.run([str(exe)], capture_output=True, timeout=120, cwd=directory)
    return (got.stdout.replace(b'\r\n', b'\n'), got.returncode, _last_line(got.stderr)), got.stderr.decode('utf-8', 'replace')[-800:]


def check_program(test, name, text, modes=(True, False), rc=0, mask=None):
    """stdout and exit status equal CPython's; an uncaught exception also has the same last stderr line."""
    with tempfile.TemporaryDirectory(prefix='ail-gaps1-') as directory:
        want = _cpython(directory, name, text)
        test.assertEqual(want[1], rc, text)
        if mask:
            want = (mask(want[0]),) + want[1:]
        for general in modes:
            got, err = _build_run(directory, name, text, general)
            test.assertIsNotNone(got, '%s (general=%s)\n%s' % (text, general, err))
            if mask:
                got = (mask(got[0]),) + got[1:]
            test.assertEqual(got, want, '%s (general=%s)\n%s' % (text, general, err))


def in_main(body):
    """The statements of `body` as the body of main() (a collections object cannot be built at module level)."""
    return 'def main():\n' + ''.join(('    ' + x if x.strip() else x) + '\n' for x in body.strip('\n').split('\n')) + '\n\nmain()\n'


# ---- 1. deque methods on an unknown receiver ----------------------------------------------------------------------------

_HEAD = '''from collections import deque, Counter, defaultdict


class Holder:
    def __init__(self, items, maxlen=None):
        self.q = deque(items, maxlen=maxlen)


def attempt(fn):
    try:
        r = fn()
        if r is not None:
            print("->", r)
    except Exception as e:
        print(type(e).__name__, e)

'''


def _op(rng, var):
    k = rng.randrange(14)
    v = rng.randrange(-2, 6)
    n = rng.choice((0, 1, 2, 3, -1, -2, -3, 7, -9, 12, 100, -101))
    if k == 0:
        return '%s.insert(%d, %d)' % (var, rng.choice((0, 1, 2, -1, -2, 5, -7, 100)), v)
    if k == 1:
        return '%s.rotate(%d)' % (var, n)
    if k == 2:
        return '%s.rotate()' % var
    if k == 3:
        return 'print(%s.index(%d))' % (var, v)
    if k == 4:
        lo = rng.choice(('', ', 1', ', -2', ', 0, 2', ', 2, 100'))
        return 'print(%s.index(%d%s))' % (var, v, lo)
    if k == 5:
        return '%s.remove(%d)' % (var, v)
    if k == 6:
        return 'print(%s.count(%d))' % (var, v)
    if k == 7:
        return '%s.reverse()' % var
    if k == 8:
        return '%s.append(%d)' % (var, v)
    if k == 9:
        return '%s.appendleft(%d)' % (var, v)
    if k == 10:
        return '%s.extend([%d, %d])' % (var, v, v + 1)
    if k == 11:
        return 'print(%s.pop())' % var
    if k == 12:
        return 'print(%s.popleft())' % var
    return 'print(len(%s), %s)' % (var, var)


def _deque_case(rng, n):
    """(definitions, the call that runs them inside main()): the receiver is an argument, a list item, an attribute,
    a dict value or an element returned by a call."""
    items = [rng.randrange(-1, 5) for _ in range(rng.randrange(0, 7))]
    maxlen = rng.choice((None, None, len(items) + 2, len(items) + 4, 3)) if items else rng.choice((None, 3))
    if maxlen is not None and maxlen < len(items):
        items = items[-maxlen:] if maxlen else []
    mk = 'deque(%r%s)' % (items, '' if maxlen is None else ', maxlen=%d' % maxlen)
    ops = [_op(rng, 'q') for _ in range(rng.randrange(3, 9))]
    where = rng.randrange(5)
    body = ['    attempt(lambda: %s)' % op for op in ops]
    run = 'run%d' % n
    if where == 0:        # a function argument
        return ['def %s(q):' % run] + body + ['    print(q)'], '%s(%s)' % (run, mk)
    if where == 1:        # a list item
        return ['def %s(box):' % run, '    q = box[0]'] + body + ['    print(box)'], '%s([%s])' % (run, mk)
    if where == 2:        # an attribute
        return ['def %s(h):' % run, '    q = h.q'] + body + ['    print(h.q)'], \
            '%s(Holder(%r, %r))' % (run, items, maxlen)
    if where == 3:        # a dict value
        return ['def %s(d):' % run, '    q = d["k"]'] + body + ['    print(d)'], '%s({"k": %s})' % (run, mk)
    stmts = []            # statements, not lambdas, on an element returned by a call
    for op in ops:
        stmts += ['    try:', '        %s' % op, '    except Exception as e:', '        print(type(e).__name__, e)']
    return ['def make%d():' % n, '    return {"a": [%s]}' % mk, '', 'def %s():' % run,
            '    q = make%d()["a"][0]' % n] + stmts + ['    print(q)'], '%s()' % run


class DequeMethods(unittest.TestCase):
    @unittest.skipUnless(HAVE_CC, 'needs gcc')
    def test_random_programs(self):
        for seed in range(12):
            defs, calls = [], []
            for i in range(3):
                d, c = _deque_case(random.Random(7100 + seed * 10 + i), i)
                defs.append('\n'.join(d) + '\n\n')
                calls.append(c)
            text = _HEAD + '\n'.join(defs) + in_main('\n'.join(calls))
            check_program(self, 'dq%d' % seed, text)

    @unittest.skipUnless(HAVE_CC, 'needs gcc')
    def test_fixed(self):
        text = _HEAD + '''
def f(q):
    q.insert(1, 99)
    q.rotate(2)
    print(q, q.index(99), q.count(99))
    q.remove(99)
    q.reverse()
    q.rotate(-1)
    q.rotate(10)
    print(q)
    q.append(5)
    q.appendleft(0)
    q.extend([8, 9])
    q.extend(q)
    print(q.pop(), q.popleft(), q)


'''
        text += in_main('''
f([deque([1, 2, 3, 2])][0])
f({"a": deque([4, 5, 6])}["a"])
f(Holder([1, 2, 3]).q)
q = deque([1, 2, 3], maxlen=3)
attempt(lambda: q.insert(0, 1))
attempt(lambda: q.index(77))
attempt(lambda: q.remove(77))
attempt(lambda: deque().rotate(3))
attempt(lambda: deque().pop())
attempt(lambda: [deque([1])][0].pop(0))
r = deque([1]) + deque([2, 3], maxlen=2)
print(r, deque([1], maxlen=2) + deque([2, 3]))
attempt(lambda: deque([1]) + [2])
w = [1]
w += "ab"
w += {7: 1}
w += range(2)
w += deque([5])
w += Counter("c")
print(w)
q += [4, 5]
q += q
print(q)
try:
    w += 3
except TypeError as e:
    print("TypeError", e)
''')
        check_program(self, 'dq_fixed', text)


# ---- 2. defaultdict repr ----------------------------------------------------------------------------------------------------

class K:
    pass


def _dd_text(factory, fill):
    return '''from collections import defaultdict


class K:
    pass


def helper():
    return [0, 0]


def show(x):
    print(x)
    print(repr(x), [x], {"k": x}, "%s" % (x,), f"{x}")


''' + in_main('''
d = defaultdict(%s)
%s
show(d)
box = [d]
show(box[0])
c = d.copy()
print(c, len(c))
print(dict(d))
''' % (factory, fill))


class DefaultdictRepr(unittest.TestCase):
    @unittest.skipUnless(HAVE_CC, 'needs gcc')
    def test_factories(self):
        fills = {
            'int': 'd["a"] += 2\nd["b"]\nd[3] += 1',
            'list': 'd["a"].append(1)\nd["b"]\nd[2].extend([3, 4])',
            'set': 'd["a"].add(1)\nd["b"]\nd[2].add("x")',
            'str': 'd["a"] += "x"\nd["b"]',
            'dict': 'd["a"]["k"] = 1\nd["b"]',
            'float': 'd["a"] += 1.5\nd["b"]',
            'K': 'd["a"] = 1\nd[2] = 2',
            'None': 'd["a"] = 1\nd[2] = [3]',
        }
        for factory, fill in fills.items():
            check_program(self, 'dd_' + factory, _dd_text(factory, fill))

    @unittest.skipUnless(HAVE_CC, 'needs gcc')
    def test_empty_and_miss(self):
        text = 'from collections import defaultdict\n\n\n' + in_main('''
for d in (defaultdict(int), defaultdict(list), defaultdict(set), defaultdict(str), defaultdict(None), defaultdict(dict)):
    print(d, repr(d), str(d), len(d))
d = defaultdict(None)
try:
    d["z"]
except KeyError as e:
    print("KeyError", e)
print(d)
e = defaultdict(int)
for ch in "hello world":
    e[ch] += 1
print(e)
print(sorted(e.items()))
''')
        check_program(self, 'dd_empty', text)

    @unittest.skipUnless(HAVE_CC, 'needs gcc')
    def test_function_factory(self):
        # CPython prints `defaultdict(<function <lambda> at 0x7f...>, {...})`; the address is never the same twice,
        # so everything but the address is compared
        text = '''from collections import defaultdict


def helper():
    return [0, 0]


''' + in_main('''
a = defaultdict(lambda: 0)
a["q"] += 1
b = defaultdict(helper)
b["r"][1] += 2
for d in (a, b):
    print(repr(d))
    print(str([d]))
''')

        def mask(out):
            return re.sub(rb'0x[0-9a-f]+', b'0xADDR', out)
        check_program(self, 'dd_func', text, mask=mask)


# ---- 3. list + Counter -------------------------------------------------------------------------------------------------------

_OPERANDS = ['[1]', '(1,)', '"s"', '1', '2.5', 'None', '{"a": 1}', '{1}', 'Counter("ab")', 'True', 'deque([1])',
             'defaultdict(int)']
_ADD = '''from collections import Counter, deque, defaultdict


def add(a, b):
    try:
        print(a + b)
    except TypeError as e:
        print("TypeError:", e)


'''


class AddErrors(unittest.TestCase):
    @unittest.skipUnless(HAVE_CC, 'needs gcc')
    def test_matrix(self):
        rows = ['add(%s, %s)' % (a, b) for a in _OPERANDS for b in _OPERANDS]
        check_program(self, 'add_matrix', _ADD + in_main('\n'.join(rows)))

    @unittest.skipUnless(HAVE_CC, 'needs gcc')
    def test_uncaught_exits_with_one(self):
        for name, expr in (('list_counter', '[1] + Counter("ab")'), ('counter_list', 'Counter("ab") + [1]'),
                           ('tuple_counter', '(1, 2) + Counter()'), ('str_counter', '"x" + Counter("a")'),
                           ('counter_dict', 'Counter("a") + {"a": 1}')):
            text = 'from collections import Counter\n\n\n' + in_main('print("before")\nc = Counter("ab")\nprint(%s)\nprint("after")' % expr)
            check_program(self, 'uncaught_' + name, text, rc=1)

    @unittest.skipUnless(HAVE_CC, 'needs gcc')
    def test_random_operands(self):
        rng = random.Random(7300)
        rows = ['add(%s, %s)' % (rng.choice(_OPERANDS), rng.choice(_OPERANDS)) for _ in range(40)]
        check_program(self, 'add_random', _ADD + in_main('\n'.join(rows)))


# ---- 4. boundary programs: self-extend of a local deque, Counter in-place with a non-mapping, defaultdict forms ----------------

class Boundaries(unittest.TestCase):
    @unittest.skipUnless(HAVE_CC, 'needs gcc')
    def test_local_deque_extend_self_and_concat(self):
        body = """
q2 = deque([1, 2]); q2.extend(q2); print(q2)
q3 = deque([1, 2, 3], maxlen=4); q3.extend(q3); print(q3)
q4 = deque([1, 2]); q4 += q4; print(q4)
print(deque([1]) + deque([2], maxlen=1))
print(deque([1], maxlen=2) + deque([2, 3]))
"""
        check_program(self, 'dq_self', 'from collections import deque\n\n\n' + in_main(body))

    @unittest.skipUnless(HAVE_CC, 'needs gcc')
    def test_counter_inplace_with_non_mapping(self):
        body = """
for other in ([1], "ab", 3, None, (1,), deque([1])):
    for op in range(3):
        c = Counter("aab")
        try:
            if op == 0:
                c += other
            elif op == 1:
                c -= other
            else:
                c |= other
            print(c)
        except Exception as ex:
            print(type(ex).__name__, ex)
c = Counter("aab"); c += {"a": 2, "z": 1}; print(c)
c = Counter("aab"); c -= Counter("a"); print(c)
try:
    print(Counter("a") + [1])
except TypeError as ex:
    print("TypeError", ex)
"""
        check_program(self, 'cnt_iadd', 'from collections import Counter, deque\n\n\n' + in_main(body))

    @unittest.skipUnless(HAVE_CC, 'needs gcc')
    def test_defaultdict_forms(self):
        body = """
dd = defaultdict(lambda: defaultdict(int))
dd["x"]["y"] += 3
print(repr(dd["x"]), len(dd))
t = defaultdict(tuple); t[0]; print(t)
e = defaultdict(int, {"z": 1, "a": 2}); print(e, len(e), dict(e)); e["q"] += 1; print(e)
p = defaultdict(list, [("k", [1])]); p["k"].append(2); p["n"]; print(p)
n = defaultdict(None); print(n)
try:
    n["q"]
except KeyError as ex:
    print("KeyError", ex)
print(defaultdict(int, a=1), defaultdict(set, {"s": {1}}, b={2}))
z = defaultdict(); print(z)
self_ref = defaultdict(list); self_ref["me"] = self_ref; print(self_ref)
d = {}; d["me"] = d; print(d)
l = [1]; l.append(l); print(l, [l, l])
"""
        check_program(self, 'dd_forms', 'from collections import defaultdict\n\n\n' + in_main(body))

    @unittest.skipUnless(HAVE_CC, 'needs gcc')
    def test_lambda_argument_in_tuple_pass(self):
        # a lambda handed to a call the tuple pass does not know used to crash the compiler (a callable type with two fields)
        text = """def apply(f, x):
    return f(x)


def main():
    pair = (1, "a")
    print(apply(lambda v: v + 1, pair[0]), pair)
    print(sorted(["bb", "a", "ccc"], key=lambda w: len(w)))


main()
"""
        check_program(self, 'lam_tuple', text)

    @unittest.skipUnless(HAVE_CC, 'needs gcc')
    def test_starred_method_call_and_maxlen(self):
        body = """
class K:
    def __init__(self):
        self.v = []

    def put(self, a, b=0):
        self.v.append((a, b))
        return len(self.v)


def maxlen_of(q):
    return q.maxlen


def main():
    k = K()
    for args in ((1,), (1, 2), (3,)):
        print(k.put(*args))
    try:
        k.put(*(1, 2, 3))
    except TypeError:
        print("TypeError")
    s = "a-b-c"
    print(s.split(*("-",)), s.split(*("-", 1)), s.replace(*("-", "+")))
    L = [1, 2, 3]
    print(L.index(*(2,)), L.pop(*()), L)
    d = {"a": 1}
    print(d.get(*("a",)), d.get(*("z", 9)))
    q = deque([1, 2, 2, 3], maxlen=5)
    for args in ((2,), (2, 2), (2, 1, 3), (3, -2, 100)):
        print(q.index(*args))
    print(q.maxlen, deque().maxlen, maxlen_of(q), maxlen_of(deque()), [deque(maxlen=7)][0].maxlen, {"k": q}["k"].maxlen)


main()
"""
        check_program(self, 'star_method', 'from collections import deque\n\n\n' + body)


_STAR_USER = """
def g0(): return 'g0'
def g1(a): return ('g1', a)
def g2(a, b=2): return ('g2', a, b)
def g3(a, *r): return ('g3', a, r)
def g4(a, b=5, *r, k=9): return ('g4', a, b, r, k)
def g5(*r): return len(r)
def g6(a, b, c): return a + b + c


class K:
    def __init__(self, a, b=1):
        self.s = (a, b)

    def m0(self): return 'm0'
    def m2(self, x, y=3): return (x, y)
    def mv(self, *a): return len(a)
    def mw(self, x, *a): return (x, a)


class E:
    def append(self, *a): return ('E.append', len(a))


class W:
    def __init__(self):
        self.k = K(0)
        self.q = deque([1, 2, 1])
        self.l = [9, 8]
        self.t = (1, 2, 1)
        self.d = {1: 2}
        self.st = {1}
        self.e = E()
        self.s = 'abcabc'


def main():
    w = W()
    k = w.k
    for n in range(0, 6):
        xs = list(range(n))
"""
_STAR_USER_CALLS = ['g0(*xs)', 'g1(*xs)', 'g2(*xs)', 'g3(*xs)', 'g4(*xs)', 'g5(*xs)', 'g6(*xs)', 'k.m0(*xs)', 'k.m2(*xs)',
                    'k.mv(*xs)', 'k.mw(*xs)', 'K(*xs).s', 'w.k.mw(*xs)', 'w.e.append(*xs)']
_STAR_BUILTIN_CALLS = ['w.%s.%s(*xs)' % (r, m) for r, ms in (
    ('q', 'append pop index count insert remove rotate popleft appendleft extend clear get'),
    ('l', 'append pop index count insert remove extend clear get'),
    ('t', 'index count get append'),
    ('d', 'pop get setdefault clear popitem append'),
    ('st', 'add remove discard pop clear get'),
    ('s', 'zfill lower upper isdigit append')) for m in ms.split()]


class StarArity(unittest.TestCase):
    """C98: recv.m(*xs) and f(*xs) bind like the plain call and raise CPython's argument-count text."""

    def _program(self, calls):
        body = ''.join('        try:\n            print(%r, n, %s)\n        except Exception as e:\n'
                       '            print(%r, n, type(e).__name__, e)\n' % (c, c, c) for c in calls)
        return 'from collections import deque\n\n' + _STAR_USER + body + '\n\nmain()\n'

    @unittest.skipUnless(HAVE_CC, 'needs gcc')
    def test_user_functions_methods_classes(self):
        check_program(self, 'star_user', self._program(_STAR_USER_CALLS))

    @unittest.skipUnless(HAVE_CC, 'needs gcc')
    def test_builtin_methods_count_errors(self):
        check_program(self, 'star_builtin', self._program(_STAR_BUILTIN_CALLS))

    @unittest.skipUnless(HAVE_CC, 'needs gcc')
    def test_reviewer_boundary_program(self):
        check_program(self, 'star_ed', ED_PROGRAM)

    @unittest.skipUnless(HAVE_CC, 'needs gcc')
    def test_counter_iand_with_other_operands(self):
        body = """
c0 = Counter("aab")
for other in ({"a": 1}, {"a": 1, "b": 5}, Counter("b"), [1], "ab", 3, None, (1,), defaultdict(int, {"a": 1})):
    c = Counter(c0)
    try:
        c &= other
        print(c)
    except Exception as ex:
        print(type(ex).__name__, ex, c)
"""
        check_program(self, 'cnt_iand', 'from collections import Counter, defaultdict\n\n\n' + in_main(body))


ED_PROGRAM = "from collections import deque, defaultdict, Counter\n\n\nclass Box:\n    def __init__(self):\n        self.q = deque([3, 1, 3, 2])\n\n    def f(self, *a):\n        return len(a)\n\n\ndef main():\n    b = Box()\n    for args in ((), (3,), (3, 1), (3, 0, 4), (1, 2, 3, 4), (1, 2, 3, 4, 5)):\n        try:\n            print(b.q.index(*list(args)))\n        except Exception as e:\n            print(type(e).__name__, e)\n        try:\n            print(b.f(*args))\n        except Exception as e:\n            print(type(e).__name__, e)\n    xs = []\n    q = deque([1])\n    q.append(*[7]); q.extend(*[[8, 9]]); print(q, q.maxlen, deque(maxlen=4).maxlen)\n    try:\n        q.append(*xs)\n    except TypeError as e:\n        print('TE', e)\n    a = [1]; a.append(a); print(a)\n    d = {}; d['x'] = [d, d]; print(d)\n    dd = defaultdict(list); dd['k'].append(dd); dd['j'] = [dd]; print(dd, repr(dd))\n    print([a, a], (a, d), str(d))\n    c = Counter('aab')\n    for other in ({'a': 1}, Counter('b'), [1], 'ab'):\n        for op in ('+=', '-=', '|=', '&='):\n            cc = Counter(c)\n            try:\n                if op == '+=': cc += other\n                elif op == '-=': cc -= other\n                elif op == '|=': cc |= other\n                else: cc &= other\n                print(op, cc)\n            except Exception as e:\n                print(op, type(e).__name__, e)\n    r = deque([1, 2, 3], maxlen=3); r.extend(r); print(r)\n    r += r; print(r, len(r))\n    e = deque(); e.extend(e); print(e)\n    print(defaultdict(int, {'b': 2}, c=3), defaultdict(list, [('a', [1])]), defaultdict(), defaultdict(str, x='y')['z'] == '')\n\n\nmain()\n"


if __name__ == '__main__':
    unittest.main()

"""The truth value of a deque and the Counter operators on the general path (DIFFERENCES C90, C91), against CPython 3.12.

1. Truthiness (C90). A deque is a two-element list `[data, maxlen]` at run time, so `bool(q)`, `if q`, `while q`, `not q`,
   `q or x`, `q and x`, `any([q])` and a comprehension filter were always true: `q = deque([0]); while q: q.popleft()`
   raised IndexError on the empty deque. The header of the list object now says "deque" (`ail_gcobj.flags`), and
   `ail_obj_truthy`, `len()` and `repr()` ask the data list. The same flag marks a Counter (a dict at run time). The probe
   also keeps the other prelude classes honest: Fraction, Enum / IntEnum / StrEnum members, ChainMap, a namedtuple, a class
   with `__bool__` or `__len__`, `range(0)` (it was true) and the builtin containers, each reached as a variable, a list item,
   a dict item, an attribute, an argument and a call result.
2. Counter operators (C91). `Counter + Counter`, `-`, `&`, `|`, unary `+` and `-` and the in-place forms, with operands that
   are expressions or arguments (a Counter is a dict at run time): the entries of the left operand first, then the keys only the
   right one has (`+ - |`), only positive counts kept, `repr` in `most_common` order, `Counter(mapping)` taking the counts,
   a Counter plus a dict raising CPython's TypeError.

Programs are generated from fixed seeds, built with the general path forced and with the default build; stdout and the exit
status must match CPython.
"""
import os
import random
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
    return done.stdout.replace(b'\r\n', b'\n'), done.returncode


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
    return (got.stdout.replace(b'\r\n', b'\n'), got.returncode), got.stderr.decode('utf-8', 'replace')[-800:]


def check_program(test, name, text, modes=(True, False)):
    with tempfile.TemporaryDirectory(prefix='ail-deqctr-') as directory:
        want = _cpython(directory, name, text)
        test.assertEqual(want[1], 0, text)
        for general in modes:
            got, err = _build_run(directory, name, text, general)
            test.assertIsNotNone(got, '%s (general=%s)\n%s' % (text, general, err))
            test.assertEqual(got, want, '%s (general=%s)\n%s' % (text, general, err))


# ---- 1. truthiness ---------------------------------------------------------------------------------------------------

_HEAD = '''from collections import deque, Counter, defaultdict, ChainMap, namedtuple
from fractions import Fraction
from enum import Enum, IntEnum, StrEnum

Pt = namedtuple("Pt", "x y")


class Color(Enum):
    RED = 0
    BLUE = 1


class Lvl(IntEnum):
    ZERO = 0
    ONE = 1


class Tag(StrEnum):
    EMPTY = ""
    FULL = "full"


class Flag:
    def __init__(self, v):
        self.v = v

    def __bool__(self):
        return self.v > 0


class Sized:
    def __init__(self, n):
        self.n = n

    def __len__(self):
        return self.n


class Plain:
    pass


class Holder:
    def __init__(self, v):
        self.v = v


def ident(x):
    return x


def probe(x):
    return (bool(x), not x, (x or "o") is not x, (x and "a") is not x, 1 if x else 2,
            [1 for _ in range(1) if x] == [1], any([x]), all([x]), len([y for y in [x, x] if y]))


'''

_SCALARS = ('0', '1', '-3', '0.0', '2.5', '""', '"s"', 'None', 'True', 'False', '[]', '[0]', '()', '(0,)', '{}',
            '{0: 0}', 'set()', '{1}', 'frozenset()', 'b""', 'b"x"', 'bytearray()', 'range(0)', 'range(3)', 'range(5, 2)',
            'range(5, 2, -1)', 'Fraction(0)', 'Fraction(3, 4)', 'Fraction(-1, 2)', 'Color.RED', 'Color.BLUE', 'Lvl.ZERO',
            'Lvl.ONE', 'Tag.EMPTY', 'Tag.FULL', 'ChainMap({})', 'ChainMap({}, {1: 2})', 'Pt(0, 0)', 'Pt(1, 2)',
            'Flag(0)', 'Flag(2)', 'Sized(0)', 'Sized(3)', 'Plain()', 'Counter()', 'Counter("a")', 'Counter({"a": 0})',
            'Counter({"z": -2})', 'defaultdict(list)', 'defaultdict(int, {1: 2})')


def _deque_expr(rng):
    kind = rng.randrange(6)
    if kind == 0:
        return 'deque()'
    if kind == 1:
        return 'deque([%d])' % rng.randrange(3)
    if kind == 2:
        return 'deque([%s])' % ', '.join(str(rng.randrange(3)) for _ in range(rng.randrange(1, 5)))
    if kind == 3:
        return 'deque(maxlen=%d)' % rng.randrange(1, 4)
    if kind == 4:
        return 'deque([%d, %d], maxlen=%d)' % (rng.randrange(3), rng.randrange(3), rng.randrange(1, 4))
    return 'deque(range(%d))' % rng.randrange(0, 4)


def _truth_case(rng, n):
    value = _deque_expr(rng) if rng.random() < 0.55 else rng.choice(_SCALARS)
    holder = rng.choice(('var', 'list', 'dict', 'attr', 'param', 'call', 'nested'))
    if holder == 'var':
        setup, e = 'x = %s' % value, 'x'
    elif holder == 'list':
        setup, e = 'h = [0, %s]' % value, 'h[1]'
    elif holder == 'nested':
        setup, e = 'h = [[%s]]' % value, 'h[0][0]'
    elif holder == 'dict':
        setup, e = 'h = {"k": %s}' % value, 'h["k"]'
    elif holder == 'attr':
        setup, e = 'h = Holder(%s)' % value, 'h.v'
    elif holder == 'call':
        setup, e = 'x = %s' % value, 'ident(x)'
    else:
        setup, e = 'x = %s' % value, None
    lines = ['def case%d():' % n, '    ' + setup]
    if e is None:
        lines.append('    print(%d, probe(x))' % n)
    else:
        lines.append('    r = (bool(%s), not %s, (%s or "o") is not %s, (%s and "a") is not %s)' % ((e,) * 6))
        lines.append('    s = 0')
        lines.append('    if %s:' % e)
        lines.append('        s += 1')
        lines.append('    if not %s:' % e)
        lines.append('        s += 2')
        lines.append('    t = 1 if %s else 2' % e)
        lines.append('    print(%d, r, s, t, probe(%s))' % (n, e))
    return '\n'.join(lines) + '\n'


def make_truth_program(seed, count=16):
    rng = random.Random(seed)
    cases = [_truth_case(rng, n) for n in range(count)]
    return _HEAD + '\n\n'.join(cases) + '\n\n' + '\n'.join('case%d()' % n for n in range(count)) + '\n'


_DEQUE_OPS = ('append', 'appendleft', 'pop', 'popleft', 'extend', 'clear', 'rotate', 'while_drain', 'copy_check')


def make_deque_program(seed, steps=40):
    """Random operations on deques of a few shapes (in a variable, a list, a dict, an attribute, a parameter), the truth
    value and the length printed after each; `while q:` drains."""
    rng = random.Random(seed)
    lines = ['from collections import deque', '', '',
             'class Box:', '    def __init__(self):', '        self.q = deque()', '', '',
             'def drain(q):', '    n = 0', '    while q:', '        q.popleft()', '        n += 1', '    return n', '', '',
             'def first(q, default):', '    return q[0] if q else default', '', '',
             'def main():']
    names = ['q0', 'q1', 'q2']
    lines.append('    q0 = deque()')
    lines.append('    q1 = deque(maxlen=%d)' % rng.randrange(1, 5))
    lines.append('    q2 = deque([%d, %d])' % (rng.randrange(4), rng.randrange(4)))
    lines.append('    box = Box()')
    lines.append('    hold = [q0, q1, q2]')
    lines.append('    byname = {"a": q0, "b": q1}')
    for _ in range(steps):
        which = rng.randrange(3)
        q = names[which]
        op = rng.choice(_DEQUE_OPS)
        if op in ('append', 'appendleft'):
            lines.append('    %s.%s(%d)' % (q, op, rng.randrange(5)))
        elif op in ('pop', 'popleft'):
            lines.append('    if %s:' % q)
            lines.append('        %s.%s()' % (q, op))
        elif op == 'extend':
            lines.append('    %s.extend([%s])' % (q, ', '.join(str(rng.randrange(5)) for _ in range(rng.randrange(0, 4)))))
        elif op == 'clear':
            lines.append('    %s.clear()' % q)
        elif op == 'rotate':
            lines.append('    %s.rotate(%d)' % (q, rng.randrange(-3, 4)))
        elif op == 'while_drain':
            lines.append('    print("drain", drain(%s))' % q)
        else:
            lines.append('    box.q = %s' % q)
            lines.append('    print("box", bool(box.q), len(box.q), "T" if box.q else "F", not box.q)')
        lines.append('    print(%d, bool(q0), bool(q1), bool(q2), bool(hold[%d]), bool(byname["a"]), '
                     'not byname["b"], len(q0), len(q1), len(q2), first(q0, -1), first(q%d, -2))' % (rng.randrange(100), which, which))
        lines.append('    print(q0, q1, q2)')
    lines += ['    n = 0', '    while q2:', '        q2.pop()', '        n += 1', '    print(n, len(q2), bool(q2))',
              '    work = deque([0])', '    seen = 0', '    while work:', '        x = work.popleft()', '        seen += 1',
              '        if x < 5:', '            work.append(x + 1)', '            work.append(x + 2)',
              '    print(seen, bool(work))', '', '', 'main()']
    return '\n'.join(lines) + '\n'


@unittest.skipUnless(HAVE_CC, 'no C compiler')
class TruthDifferential(unittest.TestCase):
    def test_general_path_matches_cpython(self):
        for seed in range(3):
            with self.subTest(seed=seed):
                check_program(self, 'truth%d' % seed, make_truth_program(seed), (True,))

    def test_default_build_matches_cpython(self):
        check_program(self, 'truth_d', make_truth_program(20), (False,))

    def test_deque_operations(self):
        for seed in range(3):
            with self.subTest(seed=seed):
                check_program(self, 'dq%d' % seed, make_deque_program(seed), (True,))
        check_program(self, 'dq_d', make_deque_program(30), (False,))

    def test_c90_shape(self):
        # the shape of gdev g10_000: a breadth-first search that ends when the queue is empty
        text = '''from collections import deque


def bfs(graph, start):
    seen = {start}
    order = []
    queue = deque([start])
    while queue:
        node = queue.popleft()
        order.append(node)
        for nxt in graph[node]:
            if nxt not in seen:
                seen.add(nxt)
                queue.append(nxt)
    return order


def main():
    graph = {0: [1, 2], 1: [3, 4], 2: [5, 6], 3: [], 4: [7], 5: [7], 6: [], 7: []}
    print(bfs(graph, 0))
    q = deque([0])
    while q:
        q.popleft()
    print(len(q), bool(q), q)


main()
'''
        check_program(self, 'c90', text)


# ---- 2. Counter operators --------------------------------------------------------------------------------------------

_KEYS = ('a', 'b', 'c', 'd', 'e', 'f')


def _counter_expr(rng):
    kind = rng.randrange(7)
    if kind == 0:
        return 'Counter()'
    if kind == 1:
        return 'Counter("%s")' % ''.join(rng.choice(_KEYS) for _ in range(rng.randrange(1, 6)))
    if kind == 2:
        return 'Counter([%s])' % ', '.join(str(rng.randrange(4)) for _ in range(rng.randrange(0, 6)))
    keys = rng.sample(_KEYS, rng.randrange(1, 5))
    counts = [rng.choice((-3, -2, -1, 0, 1, 1, 2, 3, 4)) for _ in keys]
    if kind == 6 and rng.random() < 0.5:
        counts = [c + 0.5 if rng.random() < 0.3 else c for c in counts]
    return 'Counter({%s})' % ', '.join('"%s": %r' % (k, c) for k, c in zip(keys, counts))


_BIN = ('+', '-', '&', '|')
_NAME = {'+': 'add', '-': 'sub', '&': 'and_', '|': 'or_'}


def _counter_case(rng, n):
    a, b = _counter_expr(rng), _counter_expr(rng)
    op = rng.choice(_BIN)
    style = rng.randrange(6)
    if style == 0:        # operands are expressions
        body = ['    print(%d, %s %s %s)' % (n, a, op, b)]
    elif style == 1:      # names
        body = ['    a = %s' % a, '    b = %s' % b, '    print(%d, a %s b, a, b)' % (n, op)]
    elif style == 2:      # arguments of unknown kind
        body = ['    print(%d, %s(%s, %s))' % (n, _NAME[op], a, b)]
    elif style == 3:      # unary and chains
        body = ['    a = %s' % a, '    b = %s' % b,
                '    print(%d, +a, -a, +(a %s b), -(a %s b), (a %s b) %s a)' % (n, op, op, op, rng.choice(_BIN)),
                '    print(+b, -b)']
    elif style == 4:      # in place: a second name for the object sees the change
        body = ['    a = %s' % a, '    b = %s' % b, '    c = a', '    a %s= b' % op,
                '    print(%d, a is c, a, c, b)' % n,
                '    h = [%s]' % a, '    g = h[0]', '    h[0] %s= b' % op, '    print(g is h[0], g, h)']
    else:                 # sum, copies, constructors
        body = ['    a = %s' % a, '    b = %s' % b,
                '    s = sum([a, b, a], Counter())', '    d = a.copy()', '    d %s= b' % op,
                '    print(%d, s, a, d, Counter(a) %s Counter(b), dict(a), Counter(dict(b)) %s a)' % (n, op, op)]
    return 'def case%d():\n' % n + '\n'.join(body) + '\n'


_CHEAD = '''from collections import Counter


def add(a, b):
    return a + b


def sub(a, b):
    return a - b


def and_(a, b):
    return a & b


def or_(a, b):
    return a | b


'''


def make_counter_program(seed, count=14):
    rng = random.Random(seed)
    cases = [_counter_case(rng, n) for n in range(count)]
    return _CHEAD + '\n\n'.join(cases) + '\n\n' + '\n'.join('case%d()' % n for n in range(count)) + '\n'


@unittest.skipUnless(HAVE_CC, 'no C compiler')
class CounterDifferential(unittest.TestCase):
    def test_general_path_matches_cpython(self):
        for seed in range(4):
            with self.subTest(seed=seed):
                check_program(self, 'ctr%d' % seed, make_counter_program(seed), (True,))

    def test_default_build_matches_cpython(self):
        check_program(self, 'ctr_d', make_counter_program(40), (False,))

    def test_fixed_shapes(self):
        text = '''from collections import Counter


def main():
    print(Counter("ab") + Counter("b"))
    print(Counter("abb") - Counter("bbb"), Counter("abb") & Counter("bc"), Counter("abb") | Counter("bc"))
    print(+Counter({"a": -1, "b": 2}), -Counter({"a": -1, "b": 2}), -Counter(), +Counter())
    print(Counter({"x": 2, "y": 2, "z": 3}), Counter({"p": 1, "q": 5, "r": 5}))
    print(Counter(Counter("aab")), Counter({"a": 3, "b": 0}), Counter({"a": 3}).copy())
    c = Counter("aab")
    d = c
    c += Counter("bcc")
    c -= Counter("a")
    print(c is d, d)
    for bad in ({"a": 1}, [1], 3, "s"):
        try:
            print(Counter("a") + bad)
        except TypeError as e:
            print("TypeError", e)
        if not isinstance(bad, (list, str)):    # list + x and str + x have their own messages
            try:
                print(bad + Counter("a"))
            except TypeError as e:
                print("TypeError", e)
    try:
        print(Counter("a") - {"a": 1})
    except TypeError as e:
        print("TypeError", e)
    try:
        print(+"s")
    except TypeError as e:
        print("TypeError", e)
    print(+True, +3, +2.5, -Counter({"k": -4}))


main()
'''
        check_program(self, 'ctr_fixed', text)


if __name__ == '__main__':
    unittest.main()

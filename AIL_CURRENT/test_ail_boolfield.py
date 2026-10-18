"""A bool keeps printing as True / False wherever it is stored on the typed path (DIFFERENCES.md C28), against CPython.

A bool is an int64 0/1 in the generated C, so what keeps `print(t.done)` from printing 1 is the compiler knowing,
before typing, which fields, results, parameters, lists, dicts and locals hold only bools (boolkind.py): a field is a
bool when every store to its name is a bool (`self.done = True`, `self.ok = n > f`), a list or dict when everything
put in it is, a call's result when every `return` is. A slot that would hold a bool in some places and a number in
others cannot be told apart by kind, so it is refused by name and the general path runs the program.

T1  fixed programs: bools in fields (literal, comparison, set by a method, passed to the constructor, annotated or
    not), list[bool] elements, dict values, function and method results without annotations, ternaries, `x == y`
    stored and printed later, sum/max/min over bools, `&` `|` `^`, f-strings, str(), repr(), format and `%`;
    arithmetic on bools still gives int (True + 1 == 2, sum([True, True]) == 2). The typed path alone prints
    what CPython prints, under AIL_IR=0 and AIL_IR=1
T2  refusals by name: a field, result, list, dict, ternary, `max` or int-declared slot that mixes bools and numbers is
    refused on the typed path, and the program as a whole (general path) still prints what CPython prints
T3  random programs (`gen_program`) that put bools into all of those places: CPython == typed path (when it takes the
    program) under AIL_IR=0 and 1, and the whole pipeline always equals CPython
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
HAVE_CC = shutil.which('gcc') is not None
SEEDS = int(os.environ.get('AIL_BOOLFIELD_SEEDS', '12'))


def build(directory, text, name, ir='0', typed_only=True):
    """Compile `text`; typed_only keeps the general path out (a refusal is then a failed build)."""
    source, exe = Path(directory, name + '.py'), Path(directory, name + '_t')
    source.write_text(text, encoding='utf-8')
    env = dict(os.environ, AIL_NO_CACHE='1', AIL_IR=ir)
    env.pop('AIL_NO_GENERAL', None)
    if typed_only:
        env['AIL_NO_GENERAL'] = '1'
    res = subprocess.run([sys.executable, '-B', str(ROOT / 'ail_chatgpt.py'), 'compile', source.name, '--syntax',
                          'python', '-o', exe.name], cwd=directory, capture_output=True, text=True, timeout=900,
                         env=env)
    return res, exe


def run_cpython(directory, text, name):
    source = Path(directory, name + '_cpython.py')
    source.write_text(text, encoding='utf-8')
    return subprocess.run([sys.executable, str(source)], capture_output=True, text=True, timeout=300,
                          encoding='utf-8')


def run_exe(exe):
    return subprocess.run([str(exe)], capture_output=True, text=True, timeout=300, encoding='utf-8')


# ---------------------------------------------------------------------------------------------- T1: fixed programs

FIXED = {}

FIXED['field_literal'] = '''class T:
    def __init__(self) -> None:
        self.done = True
        self.todo = False
        self.n = 3

    def finish(self) -> None:
        self.done = False
        self.todo = True
        self.n += 1


def main() -> None:
    t = T()
    print(t.done, t.todo, t.n)
    t.finish()
    print(t.done, t.todo, t.n)
    print(str(t.done), repr(t.todo), f"{t.done}|{t.todo}", "d=" + str(t.done))
    print(t.done + 1, t.todo + 1, t.done * 3, int(t.todo))


main()
'''

FIXED['field_annotated'] = '''class T:
    def __init__(self) -> None:
        self.done: bool = True
        self.hit = False

    def flip(self) -> None:
        self.done = not self.done


def main() -> None:
    t = T()
    t.flip()
    print(t.done, t.hit)
    t.flip()
    print(t.done, t.hit, str(t.done))


main()
'''

FIXED['field_expression'] = '''class T:
    def __init__(self, n: int, f: int) -> None:
        self.ok = n > f
        self.same = n == f
        self.both = n > 0 and f > 0
        self.n = n

    def check(self, k: int):
        return self.n > k

    def flag(self):
        return self.ok


def main() -> None:
    for n in range(3):
        t = T(n, 1)
        print(t.ok, t.same, t.both, t.n, t.check(1), t.flag(), f"{t.ok} {t.check(0)}")
        ok = t.ok
        print(ok, str(ok), ok + 1)


main()
'''

FIXED['field_ctor_param'] = '''class T:
    def __init__(self, n: int, flag, mark: bool) -> None:
        self.n = n
        self.flag = flag
        self.mark = mark


def main() -> None:
    a = T(1, True, False)
    b = T(2, 3 > 2, True)
    print(a.flag, a.mark, b.flag, b.mark, a.n + b.n)
    print(str(a.flag), repr(b.mark))


main()
'''

FIXED['field_in_list_and_loop'] = '''class T:
    def __init__(self, n: int) -> None:
        self.n = n
        self.even = n % 2 == 0


def main() -> None:
    ts = []
    for i in range(4):
        ts.append(T(i))
    for t in ts:
        print(t.n, t.even)
    print(ts[1].even, ts[2].even)


main()
'''

FIXED['list_bool'] = '''def main() -> None:
    xs: list[bool] = [True, False, True]
    ys = [i % 2 == 0 for i in range(5)]
    zs = [False] * 3
    zs[1] = True
    ws = []
    for i in range(4):
        ws.append(i > 1)
    print(xs[0], xs[1], ys[0], ys[1], zs[0], zs[1], ws[0], ws[3])
    for x in xs:
        print(x)
    for i, y in enumerate(ys):
        print(i, y)
    z = zs[1]
    print(z, str(z), f"{z}", repr(ws[2]))
    print(sum(xs), sum(ys), len(ws), max(xs), min(xs), max(ys), min(ws))
    xs.append(zs[0])
    print(xs[3], xs.pop(), sorted(xs)[0], sorted(xs)[2])


main()
'''

FIXED['list_field'] = '''class T:
    def __init__(self, n: int) -> None:
        self.flags = [i > 1 for i in range(n)]
        self.log = []

    def mark(self, v: int) -> None:
        self.log.append(v == 2)
        self.flags[0] = v > 5


def main() -> None:
    t = T(4)
    t.mark(2)
    t.mark(7)
    print(t.flags[0], t.flags[3], t.log[0], t.log[1], len(t.log))
    for f in t.flags:
        print(f)
    print(sum(t.flags), max(t.log), min(t.log))


main()
'''

FIXED['dict_values'] = '''def main() -> None:
    d = {"a": True, "b": False}
    e: dict[str, bool] = {}
    e["x"] = 1 < 2
    e["y"] = 2 < 1
    f = {}
    for i in range(3):
        f[i] = i > 0
    print(d["a"], d["b"], e["x"], e["y"], f[0], f[2], d.get("c", False))
    for k, v in e.items():
        print(k, v)
    for k, v in d.items():
        print(v, str(v), f"{v}")
    for j in f:
        print(j, f[j])
    print(len(e))


main()
'''

FIXED['dict_field'] = '''class T:
    def __init__(self) -> None:
        self.seen: dict[int, bool] = {}
        self.n = 0

    def see(self, k: int) -> None:
        self.seen[k] = k % 2 == 0
        self.n += 1


def main() -> None:
    t = T()
    for i in range(4):
        t.see(i)
    print(t.seen[0], t.seen[1], t.seen[3], t.n)
    for k in t.seen:
        print(k, t.seen[k])


main()
'''

FIXED['function_results'] = '''def gt(a, b):
    return a > b


def parity(n: int):
    if n % 2 == 0:
        return True
    return False


def both(a: int, b: int):
    return gt(a, 1) and gt(b, 1)


def flags(n: int):
    return [n > i for i in range(4)]


def pick(x, flag):
    return flag and x > 2


def main() -> None:
    b = gt(4, 3)
    print(gt(1, 2), b, str(b), repr(gt(2, 1)), f"{gt(3, 3)}")
    print(parity(2), parity(3), both(2, 3), both(0, 3))
    fs = flags(2)
    print(fs[0], fs[1], fs[2], fs[3])
    print(pick(3, True), pick(1, True), pick(5, False))
    c = parity(4)
    print(c, c + 1, c + c)


main()
'''

FIXED['method_results'] = '''class Acc:
    def __init__(self, n: int) -> None:
        self.n = n

    def big(self):
        return self.n > 10

    def small(self, k: int):
        return self.n < k

    def pair(self, k: int):
        return self.big() or self.small(k)


def main() -> None:
    a = Acc(5)
    b = Acc(50)
    print(a.big(), b.big(), a.small(9), b.small(9), a.pair(3), a.pair(9))
    print(str(a.big()), f"{b.big()}", repr(b.small(1)))


main()
'''

FIXED['ternary_and_eq'] = '''def main() -> None:
    x = 3
    y = 3
    e = x == y
    ne = x != y
    t = True if x > 2 else False
    u = (x > 2) if y > 5 else (y > 1)
    print(e, ne, t, u, str(e), repr(ne), f"{t}")
    print(e + 1, t * 5, e + ne, int(e))
    r = [e, ne, t, u]
    print(r[0], r[1], r[2], r[3])
    m = max(e, ne)
    n = min(e, ne)
    print(m, n, max(e, e), min(ne, ne))
    print(e & t, e | ne, e ^ t, ne ^ ne, e & True)
    a = e
    a = a and t
    a &= u
    print(a)
    print(not e, not ne, (not e) + 1)


main()
'''

FIXED['arithmetic'] = '''def main() -> None:
    xs = [True, True, False]
    ys = [i > 0 for i in range(4)]
    print(sum([True, True]), True + 1, False + 1, True * 3, True + True, sum(xs), sum(ys))
    t = True
    f = False
    print(t + f, t - f, t * 7, t // 1, t % 2, -t, abs(f), ~f, t << 2)
    print(sum(x for x in xs), sum(1 for y in ys if y), xs.count(True), ys.count(False))
    c = 0
    for y in ys:
        c += y
    print(c)
    total = sum(ys) + sum(xs)
    print(total)


main()
'''

FIXED['text_forms'] = '''def main() -> None:
    a = 3 > 2
    b = 2 > 3
    xs = [a, b]
    print("%s %s" % (a, b))
    print("{} {}".format(a, b))
    print("{0}-{1}".format(xs[0], xs[1]))
    print(f"{a} {b} {xs[0]} {xs[1]}")
    print(f"{a!r} {b!s} {a:>5} {b:d}")
    print("%d %d" % (a, b))
    print("v=" + str(a) + "," + repr(b))
    print(a, b, sep="|")
    print(*xs)


main()
'''


FIXED['same_name_two_classes'] = '''class Walk:
    def __init__(self) -> None:
        self.keys: list[str] = []
        self.done: list[int] = []
        self.ok = True


class Job:
    def __init__(self, n: int) -> None:
        self.done = n > 2
        self.n = n


class Count:
    def __init__(self) -> None:
        self.done: int = 0


def visit(st: Walk, key: str) -> int:
    st.keys.append(key)
    st.done.append(0)
    slot = len(st.done) - 1
    st.done[slot] = 1
    return slot


def main() -> None:
    w = Walk()
    s = visit(w, "a")
    visit(w, "b")
    print(s, w.done[0], w.done[1], len(w.done), w.ok)
    j = Job(3)
    k = Job(1)
    c = Count()
    c.done += 5
    print(j.done, k.done, str(j.done), c.done, j.done + 1)


main()
'''

FIXED['same_name_int_and_bool_fields'] = '''class A:
    def __init__(self, n: int) -> None:
        self.done = n

    def bump(self) -> None:
        self.done = self.done + 1


class B:
    def __init__(self, n: int) -> None:
        self.done = n > 1

    def flip(self) -> None:
        self.done = not self.done


def main() -> None:
    a = A(1)
    b = B(2)
    a.bump()
    b.flip()
    print(a.done, b.done, a.done + 1, b.done + 1)


main()
'''


def rejected(res):
    return res.returncode != 0


class Fixed(unittest.TestCase):
    @unittest.skipUnless(HAVE_CC, 'gcc')
    def test_fixed_programs(self):
        for ir in ('0', '1'):
            with tempfile.TemporaryDirectory() as d:
                for name, text in FIXED.items():
                  with self.subTest(ir=ir, name=name):
                    expected = run_cpython(d, text, name)
                    self.assertEqual(expected.returncode, 0, name + '\n' + expected.stderr)
                    res, exe = build(d, text, name + '_' + ir, ir)
                    self.assertEqual(res.returncode, 0, 'AIL_IR=%s %s: the typed path refused it:\n%s' % (
                        ir, name, (res.stdout + res.stderr)[-1500:]))
                    got = run_exe(exe)
                    self.assertEqual(got.stdout, expected.stdout, 'AIL_IR=%s %s' % (ir, name))
                    self.assertEqual(got.returncode, 0, name)


# ------------------------------------------------------------------------------------------------ T2: refusals

MIXED = {}

MIXED['field'] = ('field `v`', '''class T:
    def __init__(self, n: int) -> None:
        self.v = 0
        self.n = n

    def mark(self) -> None:
        self.v = self.n > 1


def main() -> None:
    t = T(3)
    print(t.v)
    t.mark()
    print(t.v)


main()
''')

MIXED['result'] = ('returns a bool on some paths', '''def f(n: int):
    if n > 3:
        return n > 5
    return 0


def main() -> None:
    print(f(1), f(4), f(9))


main()
''')

MIXED['ternary'] = ('mixes bools and numbers', '''def main() -> None:
    x = 3
    y = (x > 1) if x else 0
    print(y)
    z = 1 if x > 5 else (x > 2)
    print(z)


main()
''')

MIXED['list'] = ('mixes bools and numbers', '''def main() -> None:
    xs = [1 > 0, 2]
    print(xs[0], xs[1])


main()
''')

MIXED['max'] = ('mixes bools and numbers', '''def main() -> None:
    x = 3
    print(max(x > 1, 0))


main()
''')

MIXED['int_param'] = ('declared int', '''def show(n: int) -> None:
    print(n)


def main() -> None:
    show(3 > 2)
    show(5)


main()
''')

MIXED['int_result'] = ('declared int', '''def less(a: int, b: int) -> int:
    return a < b


def main() -> None:
    print(less(1, 2))


main()
''')

MIXED['local_printed'] = ('holds a bool in some places', '''def main() -> None:
    x = 0
    for i in range(3):
        if i == 2:
            x = i == 2
    print(x)


main()
''')

MIXED['list_filled'] = ('`flags`', '''def main() -> None:
    flags = [0] * 3
    flags[1] = 1 > 0
    print(flags[0], flags[1])


main()
''')


class Refusals(unittest.TestCase):
    @unittest.skipUnless(HAVE_CC, 'gcc')
    def test_mixed_slots_are_refused_and_the_general_path_is_right(self):
        with tempfile.TemporaryDirectory() as d:
            for name, (needle, text) in MIXED.items():
              with self.subTest(name=name):
                expected = run_cpython(d, text, name)
                self.assertEqual(expected.returncode, 0, name + expected.stderr)
                res, _exe = build(d, text, name, '0')
                self.assertNotEqual(res.returncode, 0, name + ': the typed path took a slot that mixes kinds')
                self.assertIn(needle, res.stdout + res.stderr, name)
                res, exe = build(d, text, name + '_g', '0', typed_only=False)
                self.assertEqual(res.returncode, 0, name + '\n' + (res.stdout + res.stderr)[-1500:])
                self.assertEqual(run_exe(exe).stdout, expected.stdout, name + ' (whole pipeline)')


# ---------------------------------------------------------------------------------------------- T3: random programs

INTS = ('n0', 'n1', 'n2')


class Gen:
    """Programs that put bools into fields, lists, dicts, results, locals and expressions and print them every way.
    A slot has one kind (bool or int) throughout, so CPython's output is the typed path's whenever it takes it."""

    def __init__(self, rnd):
        self.r = rnd
        self.lines = []
        self.obs = []           # (source, is_bool) of something printable, in scope of main
        self.pre = []           # module level: classes and functions
        self.bools = []         # names of bool locals in main
        self.ints = ['n0', 'n1', 'n2']
        self.bl = []            # bool list names
        self.il = []            # int list names
        self.bd = []            # bool dict names (str keys "a".."c")
        self.objs = []          # (name, class spec)
        self.funcs_b = []       # unannotated / annotated bool functions: (name, nargs)
        self.cls = []           # class specs
        self.counter = 0

    def fresh(self, base):
        self.counter += 1
        return '%s%d' % (base, self.counter)

    # --- expressions
    def int_expr(self, depth=0):
        r = self.r
        choice = r.random()
        if depth > 2 or choice < 0.35:
            return r.choice(self.ints + [str(r.randint(0, 6))])
        if choice < 0.6:
            return '(%s %s %s)' % (self.int_expr(depth + 1), r.choice('+-*'), self.int_expr(depth + 1))
        if choice < 0.72 and self.bl:
            return 'sum(%s)' % r.choice(self.bl)
        if choice < 0.8:
            return '(%s + %s)' % (self.bool_expr(depth + 1), self.int_expr(depth + 1))
        if choice < 0.86:
            return 'int(%s)' % self.bool_expr(depth + 1)
        if choice < 0.92 and self.il:
            return 'len(%s)' % r.choice(self.il + self.bl)
        return '%s' % r.choice(self.ints)

    def bool_expr(self, depth=0):
        r = self.r
        choice = r.random()
        if depth > 2 or choice < 0.25:
            pool = self.bools + ['True', 'False']
            return r.choice(pool)
        if choice < 0.45:
            return '(%s %s %s)' % (self.int_expr(depth + 1), r.choice(['<', '>', '==', '!=', '<=', '>=']),
                                   self.int_expr(depth + 1))
        if choice < 0.52:
            return '(not %s)' % self.bool_expr(depth + 1)
        if choice < 0.6:
            return '(%s %s %s)' % (self.bool_expr(depth + 1), r.choice(['and', 'or']), self.bool_expr(depth + 1))
        if choice < 0.66 and self.bl:
            return '%s[%d]' % (r.choice(self.bl), 0)
        if choice < 0.72 and self.bd:
            return '%s["a"]' % r.choice(self.bd)
        if choice < 0.78 and self.funcs_b:
            name, nargs = r.choice(self.funcs_b)
            return '%s(%s)' % (name, ', '.join(self.int_expr(depth + 1) for _ in range(nargs)))
        if choice < 0.84 and self.objs:
            obj, spec = r.choice(self.objs)
            fld = r.choice(spec['bool_fields'] + [None])
            if fld is not None:
                return '%s.%s' % (obj, fld)
            if spec['bool_methods']:
                return '%s.%s(%s)' % (obj, r.choice(spec['bool_methods']), self.int_expr(depth + 1))
        if choice < 0.9:
            return '(%s %s %s)' % (self.bool_expr(depth + 1), r.choice(['&', '|', '^']), self.bool_expr(depth + 1))
        if choice < 0.95 and len(self.bools) >= 1:
            return '%s(%s, %s)' % (r.choice(['max', 'min']), self.bool_expr(depth + 1), self.bool_expr(depth + 1))
        return '(%s == %s)' % (self.int_expr(depth + 1), self.int_expr(depth + 1))

    # --- printing
    def show(self, src, is_bool):
        r = self.r
        form = r.choice(['plain', 'str', 'repr', 'fstr', 'concat', 'multi', 'pct', 'sep'] if is_bool else
                        ['plain', 'str', 'fstr', 'concat', 'multi'])
        if form == 'plain':
            return 'print(%s)' % src
        if form == 'str':
            return 'print(str(%s))' % src
        if form == 'repr':
            return 'print(repr(%s))' % src
        if form == 'fstr':
            return 'print(f"{%s}")' % src
        if form == 'concat':
            return 'print("v=" + str(%s))' % src
        if form == 'multi':
            return 'print("a", %s, 7)' % src
        if form == 'pct':
            return 'print("%%s" %% (%s,))' % src
        if form == 'fmt':
            return 'print("{}".format(%s))' % src
        return 'print(%s, %s, sep="|")' % (src, src)

    # --- statements in main
    def stmt_local(self):
        name = self.fresh('b')
        self.lines.append('    %s = %s' % (name, self.bool_expr()))
        self.bools.append(name)
        self.obs.append((name, True))

    def stmt_int(self):
        name = self.fresh('i')
        self.lines.append('    %s = %s' % (name, self.int_expr()))
        self.ints.append(name)
        self.obs.append((name, False))

    def stmt_list(self):
        r = self.r
        name = self.fresh('xs')
        form = r.choice(['lit', 'comp', 'fill', 'append', 'ann'])
        k = r.randint(2, 4)
        if form == 'lit':
            self.lines.append('    %s = [%s]' % (name, ', '.join(self.bool_expr() for _ in range(k))))
        elif form == 'ann':
            self.lines.append('    %s: list[bool] = [%s]' % (name, ', '.join(self.bool_expr() for _ in range(k))))
        elif form == 'comp':
            self.lines.append('    %s = [%s for q in range(%d)]' % (
                name, r.choice(['q > %d' % r.randint(0, 3), 'q %% 2 == %d' % r.randint(0, 1), 'q == n0']), k))
        elif form == 'fill':
            self.lines.append('    %s = [%s] * %d' % (name, r.choice(['False', 'True']), k))
            for _ in range(2):
                self.lines.append('    %s[%d] = %s' % (name, r.randrange(k), self.bool_expr()))
        else:
            self.lines.append('    %s = []' % name)
            for _ in range(k):
                self.lines.append('    %s.append(%s)' % (name, self.bool_expr()))
        self.bl.append(name)
        i = r.randrange(k)
        self.obs.append(('%s[%d]' % (name, i), True))
        self.obs.append(('%s[%d]' % (name, k - 1), True))
        self.obs.append(('sum(%s)' % name, False))
        if r.random() < 0.5:
            self.obs.append(('max(%s)' % name, True))
            self.obs.append(('min(%s)' % name, True))
        if r.random() < 0.3:
            self.obs.append(('sorted(%s)[0]' % name, True))
        loop = self.fresh('e')
        self.lines.append('    for %s in %s:' % (loop, name))
        self.lines.append('        ' + self.show(loop, True))

    def stmt_dict(self):
        r = self.r
        name = self.fresh('d')
        form = r.choice(['lit', 'ann', 'store'])
        if form == 'lit':
            self.lines.append('    %s = {"a": %s, "b": %s}' % (name, self.bool_expr(), self.bool_expr()))
        elif form == 'ann':
            self.lines.append('    %s: dict[str, bool] = {}' % name)
            self.lines.append('    %s["a"] = %s' % (name, self.bool_expr()))
            self.lines.append('    %s["b"] = %s' % (name, self.bool_expr()))
        else:
            self.lines.append('    %s = {}' % name)
            self.lines.append('    %s["a"] = %s' % (name, self.bool_expr()))
            self.lines.append('    %s["b"] = %s' % (name, self.bool_expr()))
        self.bd.append(name)
        self.obs.append(('%s["a"]' % name, True))
        self.obs.append(('%s["b"]' % name, True))
        self.obs.append(('%s.get("zz", False)' % name, True))
        k, v = self.fresh('k'), self.fresh('v')
        if r.random() < 0.6:
            self.lines.append('    for %s, %s in %s.items():' % (k, v, name))
            self.lines.append('        print(%s, %s)' % (k, self.show_inline(v)))

    def show_inline(self, v):
        return r_choice(self.r, [v, 'str(%s)' % v, 'repr(%s)' % v, 'f"{%s}"' % v])

    def make_function(self):
        r = self.r
        name = self.fresh('fn')
        nargs = r.randint(1, 2)
        params = ['p%d' % i for i in range(nargs)]
        saved = (self.ints, self.bools, self.bl, self.il, self.bd, self.objs)
        self.ints, self.bools, self.bl, self.il, self.bd, self.objs = list(params), [], [], [], [], []
        body = self.bool_expr()
        annotated = r.random() < 0.4
        if r.random() < 0.3:
            cond = '%s > %d' % (params[0], r.randint(0, 3))
            body = '%s if %s else %s' % (self.bool_expr(), cond, self.bool_expr())
            self.pre.append('def %s(%s)%s:\n    if %s:\n        return %s\n    return %s\n' % (
                name, ', '.join('%s: int' % p for p in params), ' -> bool' if annotated else '', cond,
                self.bool_expr(), self.bool_expr()))
        else:
            self.pre.append('def %s(%s)%s:\n    return %s\n' % (
                name, ', '.join('%s: int' % p for p in params), ' -> bool' if annotated else '', body))
        self.ints, self.bools, self.bl, self.il, self.bd, self.objs = saved
        self.funcs_b.append((name, nargs))

    def make_class(self):
        r = self.r
        cname = self.fresh('C').upper()
        nf = r.randint(1, 3)
        fields = []
        init = ['    def __init__(self, n: int%s) -> None:' % (', flag' if r.random() < 0.4 else '')]
        has_flag = 'flag' in init[0]
        init_lines = ['        self.n = n']
        bool_fields, bool_methods = [], []
        for i in range(nf):
            f = 'f%d' % i
            form = r.choice(['lit', 'cmp', 'ann', 'expr'])
            if form == 'lit':
                init_lines.append('        self.%s = %s' % (f, r.choice(['True', 'False'])))
            elif form == 'cmp':
                init_lines.append('        self.%s = n %s %d' % (f, r.choice(['<', '>', '==', '!=']), r.randint(0, 4)))
            elif form == 'ann':
                init_lines.append('        self.%s: bool = n %s %d' % (f, r.choice(['<', '>']), r.randint(0, 4)))
            else:
                init_lines.append('        self.%s = (n > 1) and (n < 5)' % f)
            bool_fields.append(f)
        if has_flag:
            init_lines.append('        self.fl = flag')
            bool_fields.append('fl')
        methods = []
        if r.random() < 0.8:
            f = r.choice(bool_fields)
            methods.append('    def toggle(self) -> None:\n        self.%s = not self.%s\n' % (f, f))
        if r.random() < 0.8:
            methods.append('    def big(self, k: int)%s:\n        return self.n > k\n' % (
                ' -> bool' if r.random() < 0.4 else ''))
            bool_methods.append('big')
        if 'big' in bool_methods and r.random() < 0.5:
            methods.append('    def both(self, k: int):\n        return self.big(k) and self.%s\n' % bool_fields[0])
            bool_methods.append('both')
        self.pre.append('class %s:\n%s\n%s\n%s\n' % (cname, '\n'.join(init), '\n'.join(init_lines), '\n'.join(methods)))
        self.cls.append({'name': cname, 'bool_fields': bool_fields, 'bool_methods': bool_methods,
                         'toggle': any('toggle' in m for m in methods), 'flag': has_flag})

    def stmt_obj(self, spec=None):
        r = self.r
        if not self.cls:
            return
        spec = spec or r.choice(self.cls)
        name = self.fresh('o')
        args = [self.int_expr()]
        if spec['flag']:
            args.append(self.bool_expr())
        self.lines.append('    %s = %s(%s)' % (name, spec['name'], ', '.join(args)))
        self.objs.append((name, spec))
        for f in spec['bool_fields']:
            self.obs.append(('%s.%s' % (name, f), True))
        if spec['toggle']:
            self.lines.append('    %s.toggle()' % name)
            for f in spec['bool_fields']:
                self.obs.append(('%s.%s' % (name, f), True))
        for m in spec['bool_methods']:
            self.obs.append(('%s.%s(%s)' % (name, m, self.int_expr()), True))

    def generate(self):
        r = self.r
        for _ in range(r.randint(0, 3)):
            self.make_function()
        for _ in range(r.randint(0, 2)):
            self.make_class()
        self.lines.append('    n0 = %d' % r.randint(0, 5))
        self.lines.append('    n1 = %d' % r.randint(0, 5))
        self.lines.append('    n2 = %d' % r.randint(0, 5))
        steps = [self.stmt_local, self.stmt_local, self.stmt_int, self.stmt_list, self.stmt_dict, self.stmt_obj,
                 self.stmt_obj]
        for _ in range(r.randint(4, 7)):
            r.choice(steps)()
        for spec in self.cls:
            if not any(s is spec for _o, s in self.objs):
                self.stmt_obj(spec)
        shown = list(self.obs)
        r.shuffle(shown)
        for src, is_bool in shown[:r.randint(8, 14)]:
            self.lines.append('    ' + self.show(src, is_bool))
        return '\n'.join(self.pre) + '\n\ndef main() -> None:\n' + '\n'.join(self.lines) + '\n\n\nmain()\n'


def r_choice(r, seq):
    return r.choice(seq)


def gen_program(seed):
    return Gen(random.Random(seed)).generate()


class Random(unittest.TestCase):
    @unittest.skipUnless(HAVE_CC, 'gcc')
    def test_random_programs(self):
        taken = 0
        total = 0
        with tempfile.TemporaryDirectory() as d:
            for seed in range(SEEDS):
                text = gen_program(seed)
                expected = run_cpython(d, text, 'p%d' % seed)
                if expected.returncode != 0:
                    continue          # a program CPython rejects (an index out of range)
                for ir in ('0', '1'):
                    total += 1
                    res, exe = build(d, text, 'p%d_%s' % (seed, ir), ir)
                    if res.returncode == 0:
                        taken += 1
                        got = run_exe(exe)
                        self.assertEqual(got.stdout, expected.stdout, 'AIL_IR=%s seed %d\n%s' % (ir, seed, text))
                    elif ir == '0':
                        res, exe = build(d, text, 'p%d_g' % seed, '0', typed_only=False)
                        self.assertEqual(res.returncode, 0, 'seed %d\n%s' % (seed, (res.stdout + res.stderr)[-1500:]))
                        self.assertEqual(run_exe(exe).stdout, expected.stdout, 'whole pipeline, seed %d\n%s' % (seed, text))
        print('boolfield random: the typed path took %d of %d' % (taken, total), file=sys.stderr)
        # the test means something only if the typed path takes most of what it is given
        self.assertGreaterEqual(taken * 100, total * 40, 'the typed path took %d of %d programs' % (taken, total))


if __name__ == '__main__':
    unittest.main()

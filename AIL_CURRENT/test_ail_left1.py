"""Small CPython differences fixed on branch left1oc, on both builds.

1. The empty tuple `()` inside a function (it used to make the tuple pass emit `class _AilT_: def __init__():`
   with an empty body, so the misleading Python syntax error "expected an indented block after function definition").
2. `+` between a list / tuple / str / deque and an operand of another type: CPython's
   `can only concatenate list (not "bytes") to list` (and the reflected forms), including an instance operand.
4. `deque * 2.5` and `deque * "x"`: `can't multiply sequence by non-int of type 'float'` — and the same for
   list, tuple, str, bytes / bytearray and the reflected forms.
3. `type(dd.copy()).__name__` of a `collections.defaultdict` (also Counter, deque and the dict views).
5. `d.keys().isdisjoint(...)` / `d.items().isdisjoint(...)` on dict views, including an unhashable item of the
   argument (CPython's items view compares by equality; the keys view hashes); `values()` still has no method.
6. `str.find(*xs)` / `str.startswith(*xs)` with a wrong argument type: CPython's own `must be str, not int`
   (also for a literal receiver, a tuple / list / argument / attribute / dict value holding the arguments).

Programs are built with the general path forced and with the default build; stdout and exit status must match
CPython 3.12.
"""
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent
CHATGPT = str(ROOT / 'ail_chatgpt.py')
HAVE_CC = shutil.which('gcc') is not None


def _last_line(err):
    lines = [x for x in err.decode('utf-8', 'replace').splitlines() if x.strip()]
    return lines[-1] if lines else ''


def _cpython(directory, name, text):
    src = Path(directory) / (name + '_cpython.py')
    src.write_text(text, encoding='utf-8')
    done = subprocess.run([sys.executable, '-B', str(src)], capture_output=True, timeout=120,
                          env=dict(os.environ, PYTHONUTF8='1'))
    return done.stdout.replace(b'\r\n', b'\n'), done.returncode, _last_line(done.stderr)


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


def check_program(test, name, text):
    with tempfile.TemporaryDirectory(prefix='ail-left1-') as directory:
        want = _cpython(directory, name, text)
        for general in (True, False):
            got, err = _build_run(directory, name, text, general)
            test.assertIsNotNone(got, '%s (general=%s)\n%s' % (text, general, err))
            test.assertEqual(got, want, '%s (general=%s)\n%s' % (text, general, err))


EMPTY_TUPLE = r'''class Box:
    def __init__(self, v):
        self.v = v


def ident(x):
    return x


def main():
    t = ()
    d = {(): 'empty', (1,): 'one'}
    xs = [t, ((),), (1, ())]
    b = Box(t)
    m = {'k': t}
    print(t, ident(t), xs[0], xs[1], xs[2], b.v, m['k'])
    print(len(t), bool(t), () == t, ((),) == ((),), () != ((),))
    print(d[()], d[ident(())], d.get((), 'missing'))
    print(t + (), () + (1,), (1,) + ())
    print(hash(()) == hash(()), {(): 1}[()])
    print(() in xs, [] == list(t), tuple(t), sorted([(), (), (1,)]))
    for e in t:
        print('never', e)
    print(type(()).__name__, repr(()), str(()), len(()), bool(()))


main()
'''

EMPTY_TUPLE_VALUE = r'''class Box:
    def __init__(self, v):
        self.v = v


def ident(x):
    return x


def ret():
    return ()


def take(x):
    return bool(x), type(x).__name__, len(x), x == (), not x


def main():
    t = ret()
    box = Box(t)
    xs = [t, t]
    ds = {'a': t}
    print(t, bool(t), type(t).__name__, len(t))
    for x in (t, ident(t), box.v, xs[0], ds['a'], ret(), ()):
        print(take(x))
    print(take(()))
    if t:
        print('truthy')
    else:
        print('falsy')
    print('T' if t else 'F', bool(((),)), bool((1,)), t == (), ((),) == ((),))
    print(type(()).__name__, type(ident(())).__name__, type(box.v).__name__)


main()
'''

ADD_ERRORS = r'''class C:
    pass


class Box:
    def __init__(self, v):
        self.v = v


from collections import deque, Counter, defaultdict


def ident(x):
    return x


def main():
    box = Box([1])
    d = {'k': (1,)}
    cases = [([1], b'a'), ((1,), b'a'), ('s', 1.5),
             ([1], C()), ((1,), C()), ('s', C()),
             (b'a', [1]), (b'a', C()), (b'a', 's'), (b'a', 1.5),
             (bytearray(b's'), 'a'), (bytearray(b's'), 1), (bytearray(b's'), 1.5),
             (bytearray(b's'), C()), (deque([1]), bytearray(b's')),
             (deque([1]), [2]), (deque([1]), C()), ([1], deque([2])),
             ([1], Counter()), (Counter(), [1]),
             ([1], defaultdict(int)), (defaultdict(int), [1]),
             ({'a': 1}, [1]), ({1, 2}, [1]), (1, [1]), (1.5, 's'), (None, [1]), (True, [1]),
             (box.v, b'a'), (d['k'], b'a'), (ident([1]), b'a')]
    for a, b in cases:
        try:
            print(repr(a + b))
        except Exception as e:
            print(type(e).__name__ + ':', e)


main()
'''

DEQUE_INLINE_ERRORS = r'''import collections


def main():
    cases = [([1], collections.deque([1])), (collections.deque([1]), [1]),
             (collections.deque([1]), 1), (1, collections.deque([1])),
             (collections.deque([1]), 'a'), ('a', collections.deque([1])),
             (collections.deque([1]), b'a'), (b'a', collections.deque([1])),
             (collections.deque([1]), (1,)), ((1,), collections.deque([1]))]
    for a, b in cases:
        try:
            print(a + b)
        except TypeError as e:
            print(e)


main()
'''

TYPE_NAMES = r'''import collections


class Box:
    def __init__(self, v):
        self.v = v


def ident(x):
    return x


def main():
    dd = collections.defaultdict(int)
    dd['a'] = 1
    box = Box(dd.copy())
    d = {'v': dd.copy()}
    for x in (dd.copy(), ident(dd.copy()), box.v, d['v']):
        print(type(x).__name__, x.__class__.__name__, repr(x), type(x).__name__ == 'defaultdict')
    plain = dd.copy()
    plain['b'] += 1
    print(plain['b'], type(plain).__name__)
    print(type(collections.Counter('aab')).__name__, type(collections.deque([1])).__name__)
    for view in (dd.keys(), dd.items(), dd.values()):
        print(type(view).__name__)


main()
'''

MUL_ERRORS = r'''from collections import deque


class Box:
    def __init__(self, v):
        self.v = v


def ident(x):
    return x


def main():
    q = deque([1, 2])
    box = Box(q)
    d = {'q': q}
    for x in (q, ident(q), box.v, d['q']):
        for n in (2.5, 'x', b'x', None, [1], (1,), {}):
            try:
                print(x * n)
            except Exception as e:
                print(type(e).__name__ + ':', e)
            try:
                print(n * x)
            except Exception as e:
                print(type(e).__name__ + ':', e)
    for seq in ([1], (1,), 'ab', b'ab'):
        for n in (2.5, 'x'):
            try:
                print(seq * n)
            except Exception as e:
                print(type(e).__name__ + ':', e)


main()
'''


MIXED_TUPLE_LIST = r'''class Box:
    def __init__(self, v):
        self.v = v


def ident(x):
    return x


def main():
    p = (1, "a")
    xs = [(), p]
    print(xs)
    print(xs[1], len(xs[1]), xs[0])
    ys = [p, ()]
    print(ys)
    zs = [(1,), (1, "a")]
    print(zs)
    box = Box(p)
    for v in (xs, ys, zs, [(), ident(p)], [box.v, ()], {'k': [(), p]}['k']):
        print(v)


main()
'''

DEQUE_MIXED_MUL = r'''from collections import deque


def ident(x):
    return x


def main():
    cases = [(deque([1]), 2.5), (deque([1]), "x"), (2.5, deque([1])),
             ([1], 2.5), (deque([1]), 3), (deque([1, 2]), -2),
             (deque([1], maxlen=2), 3), (True, deque([1])),
             (deque([1]), None), (deque([1]), [2]), (deque([1]), deque([2]))]
    for a, b in cases:
        try:
            print(repr(a * b))
        except TypeError as e:
            print("TE", e)
    for x in (deque([1]), ident(deque([1]))):
        print(x, str(x), len(x), x * 2, 2 * x, x * 0, x * -1)
        try:
            x *= 2.5
        except TypeError as e:
            print("TE", e)


main()
'''


COUNT_ARG_ORDER = r'''def main():
    s = 'abcabc'
    for args in ([0, 1.5], [0, 'x'], ['a', 1.5], ['a', 1, 2.5]):
        try:
            print('count', s.count(*args))
        except Exception as e:
            print('count', type(e).__name__ + ':', e)
        try:
            print('find', s.find(*args))
        except Exception as e:
            print('find', type(e).__name__ + ':', e)
        try:
            print('startswith', s.startswith(*args))
        except Exception as e:
            print('startswith', type(e).__name__ + ':', e)


main()
'''

VIEW_ISDISJOINT = r'''class Box:
    def __init__(self, d):
        self.d = d


def ident(x):
    return x


def main():
    d = {'a': 1, 'b': 2}
    box = Box(d)
    holder = {'d': d}
    for k in (d.keys(), ident(d.keys()), box.d.keys(), holder['d'].keys(),
              d.items(), ident(d.items()), box.d.items(), holder['d'].items()):
        print(k.isdisjoint({'z': 9}), k.isdisjoint({'a': 3}),
              k.isdisjoint([('a', 1)]), k.isdisjoint([]), k.isdisjoint(d))
    print(d.keys().isdisjoint({('a', 1)}))
    print(d.items().isdisjoint({('a', 1)}))
    print(d.items().isdisjoint({('a', 2)}))
    for which in (0, 1, 2):
        try:
            if which == 0:
                print(d.keys().isdisjoint(1))
            elif which == 1:
                print(d.items().isdisjoint([[]]))
            else:
                print(d.keys().isdisjoint([[]]))
        except Exception as e:
            print(type(e).__name__ + ':', e)
    try:
        print(d.values().isdisjoint({'a'}))
    except Exception as e:
        print(type(e).__name__ + ':', e)


main()
'''

FIND_STAR = r'''class Box:
    def __init__(self, args):
        self.args = args


def ident(x):
    return x


def main():
    s = 'hello world'
    box = Box([ord('o')])
    d = {'args': [ord('o')]}
    for args in ([ord('o')], ident([ord('o')]), box.args, d['args'], (ord('o'),), []):
        try:
            print(s.find(*args))
        except Exception as e:
            print(type(e).__name__ + ':', e)
    for args in ([0], [b'x'], [1, 2, 'x'], [0, 2], [1, 2, 3, 4]):
        try:
            print(s.find(*args))
        except Exception as e:
            print(type(e).__name__ + ':', e)
    for args in ([0], ['he', 2], [1, 2, 'x']):
        try:
            print(s.startswith(*args))
        except Exception as e:
            print(type(e).__name__ + ':', e)
    try:
        print('hello'.find(*[0]))
    except Exception as e:
        print(type(e).__name__ + ':', e)


main()
'''


DEQUE_MAXLEN_MUL = r'''from collections import deque


def ident(x):
    return x


def main():
    cases = [
        (deque([1, 2, 3], maxlen=4), 2),
        (deque([1, 2, 3], maxlen=4), 0),
        (deque([1, 2, 3], maxlen=4), -1),
        (deque([1, 2, 3], maxlen=4), 1),
        (deque([1, 2, 3], maxlen=4), 3),
        (deque([1, 2, 3], maxlen=4), 1000),
        (deque([1, 2, 3], maxlen=0), 3),
        (deque([1, 2, 3], maxlen=0), -2),
        (deque([], maxlen=4), 3),
        (deque([], maxlen=0), 5),
        (deque([1, 2, 3]), 2),
        (deque([1, 2, 3]), 0),
        (deque([1, 2, 3]), -2),
        (deque([1, 2, 3], maxlen=1), 2),
        (deque([1, 2, 3], maxlen=10), 2),
        (deque([1, 2], maxlen=3), 3),
    ]
    for q, n in cases:
        print(q * n, q)
        print(n * q)
    for q in [deque([1, 2, 3], maxlen=4), deque([1, 2, 3], maxlen=0),
              deque([], maxlen=4), deque([1, 2, 3]), deque([1, 2, 3], maxlen=1)]:
        for n in [2, 0, -1, 3]:
            d = deque(q, maxlen=q.maxlen)
            d *= n
            print('imul', d, d.maxlen)
    d = deque([1, 2, 3], maxlen=4)
    e = ident(d)
    d *= 2
    print('alias', d, e, len(e))
    d = deque([1, 2, 3], maxlen=4)
    d *= 1000
    print('big', d)


main()
'''


STAR_COUNT_INDEX = r'''class Box:
    def __init__(self, args):
        self.args = args


def f_int(s, v):
    try:
        print('int', 'count', s.count(*[v]))
    except Exception as e:
        print('int', 'count', type(e).__name__ + ':', e)
    try:
        print('int', 'index', s.index(*[v]))
    except Exception as e:
        print('int', 'index', type(e).__name__ + ':', e)


def f_none(s, v):
    try:
        print('none', 'count', s.count(*[v]))
    except Exception as e:
        print('none', 'count', type(e).__name__ + ':', e)
    try:
        print('none', 'index', s.index(*[v]))
    except Exception as e:
        print('none', 'index', type(e).__name__ + ':', e)


def f_float(s, v):
    try:
        print('float', 'count', s.count(*[v]))
    except Exception as e:
        print('float', 'count', type(e).__name__ + ':', e)
    try:
        print('float', 'index', s.index(*[v]))
    except Exception as e:
        print('float', 'index', type(e).__name__ + ':', e)


def f_bytes(s, v):
    try:
        print('bytes', 'count', s.count(*[v]))
    except Exception as e:
        print('bytes', 'count', type(e).__name__ + ':', e)
    try:
        print('bytes', 'index', s.index(*[v]))
    except Exception as e:
        print('bytes', 'index', type(e).__name__ + ':', e)


def f_tuple(s, v):
    try:
        print('tuple', 'count', s.count(*[v]))
    except Exception as e:
        print('tuple', 'count', type(e).__name__ + ':', e)
    try:
        print('tuple', 'index', s.index(*[v]))
    except Exception as e:
        print('tuple', 'index', type(e).__name__ + ':', e)


def main():
    s = 'abcabc'
    box = Box([0])
    d = {'args': [0]}
    xs = [[0]]
    f_int('abcabc', 0)
    f_none(str('xyz'), None)
    f_float('a' + '1', 1.5)
    f_bytes('abcabc', b'a')
    f_tuple(str('xyz'), (0,))
    for args in (box.args, d['args'], xs[0]):
        try:
            print('source', 'count', s.count(*args))
        except Exception as e:
            print('source', 'count', type(e).__name__ + ':', e)
        try:
            print('source', 'index', s.index(*args))
        except Exception as e:
            print('source', 'index', type(e).__name__ + ':', e)
    print('good', s.count(*['a']), s.index(*['a']))
    try:
        print('hello'.count(*[0]))
    except Exception as e:
        print(type(e).__name__ + ':', e)
    try:
        print('hello'.index(*[0]))
    except Exception as e:
        print(type(e).__name__ + ':', e)
    ys = [1, 2, 1]
    one = [1]
    print('list', ys.count(*one), ys.index(*one))


main()
'''


@unittest.skipUnless(HAVE_CC, 'gcc is required')
class LeftOneTests(unittest.TestCase):
    def test_empty_tuple(self):
        check_program(self, 'left1_empty', EMPTY_TUPLE)

    def test_empty_tuple_value(self):
        check_program(self, 'left1_empty_value', EMPTY_TUPLE_VALUE)

    def test_add_errors(self):
        check_program(self, 'left1_add', ADD_ERRORS)

    def test_deque_inline_errors(self):
        check_program(self, 'left1_deque_inline', DEQUE_INLINE_ERRORS)

    def test_type_names(self):
        check_program(self, 'left1_names', TYPE_NAMES)

    def test_mul_errors(self):
        check_program(self, 'left1_mul', MUL_ERRORS)

    def test_view_isdisjoint(self):
        check_program(self, 'left1_view', VIEW_ISDISJOINT)

    def test_find_star(self):
        check_program(self, 'left1_find', FIND_STAR)

    def test_mixed_tuple_list(self):
        check_program(self, 'left1_mixed_tuple', MIXED_TUPLE_LIST)

    def test_deque_mixed_mul(self):
        check_program(self, 'left1_deque_mixed_mul', DEQUE_MIXED_MUL)

    def test_count_arg_order(self):
        check_program(self, 'left1_count_order', COUNT_ARG_ORDER)

    def test_deque_maxlen_mul(self):
        check_program(self, 'left1_deque_maxlen_mul', DEQUE_MAXLEN_MUL)

    def test_star_count_index(self):
        check_program(self, 'left1_star_count_index', STAR_COUNT_INDEX)


if __name__ == '__main__':
    unittest.main()

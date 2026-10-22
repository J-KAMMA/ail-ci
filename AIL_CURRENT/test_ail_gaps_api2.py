"""API gaps of the general path, second round (DIFFERENCES C104, C105), against CPython 3.12.

1. A method the receiver's type does not have, called on a receiver whose kind the compiler does not know (a function
   argument, a list item, an attribute): `w.t.get(1)`, `t.append(1)`, `t.keys()` on a tuple segfaulted (the handler read the
   tuple as a dict / list); every receiver (list, tuple, str, dict, set, bytes, int, float, None, deque, Counter) times every
   method name the handlers serve must raise CPython's `AttributeError: 'tuple' object has no attribute 'get'`
   (`'collections.deque'`, `'Counter'`, `'dict_keys'` for those types). A receiver of a known kind gets the same error where
   the compiler used to refuse the call by name.
2. `dict.keys()`, `.values()`, `.items()`: `print`, `repr`, `str`, f-string show `dict_keys(['a'])`, `dict_values([1])`,
   `dict_items([('a', 1)])`; `len`, `in`, iteration, `list`, `sorted`, `==` against a set or another keys / items view,
   `& | - ^` with any iterable, `view[0]` (TypeError), a method call (AttributeError). The loop `for k in d.keys()` keeps its
   indexed C loop; the typed path refuses a view shown as a value by name (and the default build takes the general path).

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
from collections import Counter, deque
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


def _build(directory, name, text, general, extra_env=None, extra_args=()):
    src = Path(directory) / (name + '.ail')
    src.write_text(text, encoding='utf-8')
    exe = Path(directory) / ('exe_' + name + ('_g' if general else '_d'))
    env = dict(os.environ, AIL_NO_CACHE='1', AIL_QUIET_FALLBACK='1')
    env.pop('AIL_NO_GENERAL', None)
    if general:
        env['AIL_UNIFIED_FORCE'] = '1'
    env.update(extra_env or {})
    cmd = [sys.executable, '-B', CHATGPT, 'compile', src.name, '--syntax', 'python', '-o', exe.name] + list(extra_args)
    built = subprocess.run(cmd, cwd=directory, capture_output=True, text=True, timeout=900, env=env)
    return exe, built


def _build_run(directory, name, text, general):
    exe, built = _build(directory, name, text, general)
    if built.returncode != 0:
        return None, (built.stdout + built.stderr)[-1500:]
    got = subprocess.run([str(exe)], capture_output=True, timeout=120, cwd=directory)
    return (got.stdout.replace(b'\r\n', b'\n'), got.returncode, _last_line(got.stderr)), got.stderr.decode('utf-8', 'replace')[-800:]


def check_program(test, name, text, modes=(True, False), rc=0):
    """stdout and exit status equal CPython's; an uncaught exception also has the same last stderr line."""
    with tempfile.TemporaryDirectory(prefix='ail-gaps2-') as directory:
        want = _cpython(directory, name, text)
        test.assertEqual(want[1], rc, text)
        for general in modes:
            got, err = _build_run(directory, name, text, general)
            test.assertIsNotNone(got, '%s (general=%s)\n%s' % (text[:3000], general, err))
            test.assertEqual(got, want, '%s (general=%s)\n%s' % (text[:3000], general, err))


def in_main(body):
    return 'def main():\n' + ''.join(('    ' + x if x.strip() else x) + '\n' for x in body.strip('\n').split('\n')) + '\n\nmain()\n'


# ---- 1. receiver x method name -----------------------------------------------------------------------------------------

RECEIVERS = [('list', '[1, 2]'), ('tuple', '(1, 2)'), ('str', '"ab"'), ('dict', '{"a": 1}'), ('set', '{1, 2}'),
             ('bytes', 'b"ab"'), ('int', '5'), ('float', '2.5'), ('None', 'None'), ('deque', 'deque([1, 2])'),
             ('Counter', 'Counter("aab")'), ('bool', 'True'), ('frozenset', 'frozenset([1, 2])'), ('keys', '{"a": 1}.keys()'),
             ('values', '{"a": 1}.values()'), ('items', '{"a": 1}.items()')]
# every method the general path's handlers serve (pyboxed2._METHOD_OWNERS), with the argument count each takes at least
METHODS = {'add': 1, 'append': 1, 'appendleft': 1, 'bit_count': 0, 'bit_length': 0, 'capitalize': 0, 'casefold': 0,
           'center': 1, 'clear': 0, 'copy': 0, 'count': 1, 'difference': 1, 'difference_update': 1, 'discard': 1,
           'elements': 0, 'endswith': 1, 'expandtabs': 0, 'extend': 1, 'find': 1, 'fromkeys': 1, 'get': 1, 'index': 1,
           'insert': 2, 'intersection': 1, 'intersection_update': 1, 'is_integer': 0, 'isalnum': 0, 'isalpha': 0,
           'isascii': 0, 'isdecimal': 0, 'isdigit': 0, 'isdisjoint': 1, 'isidentifier': 0, 'islower': 0, 'isnumeric': 0,
           'isspace': 0, 'issubset': 1, 'issuperset': 1, 'istitle': 0, 'isupper': 0, 'items': 0, 'join': 1, 'keys': 0,
           'ljust': 1, 'lower': 0, 'lstrip': 0, 'most_common': 0, 'partition': 1, 'pop': 0, 'popitem': 0, 'popleft': 0,
           'remove': 1, 'removeprefix': 1, 'removesuffix': 1, 'replace': 2, 'reverse': 0, 'rfind': 1, 'rjust': 1,
           'rotate': 1, 'rpartition': 1, 'rsplit': 0, 'rstrip': 0, 'setdefault': 1, 'sort': 0, 'split': 0,
           'splitlines': 0, 'startswith': 1, 'strip': 0, 'swapcase': 0, 'symmetric_difference': 1,
           'symmetric_difference_update': 1, 'title': 0, 'total': 0, 'union': 1, 'update': 1, 'upper': 0, 'values': 0,
           'zfill': 1}
_NS = {'deque': deque, 'Counter': Counter}


def _missing(recv_src):
    obj = eval(recv_src, dict(_NS))
    return [m for m in METHODS if not hasattr(obj, m)]


_SHOW = '''from collections import deque, Counter


def show(r, m, f):
    try:
        f()
        print(r, m, "ok")
    except AttributeError as e:
        print(r, m, "AttributeError", e)
    except Exception as e:
        print(r, m, type(e).__name__)

'''


def _args(m):
    return ', '.join(['1'] * METHODS[m])


def unknown_receiver_program(names):
    """Each receiver is a list item reaching `f_<receiver>_<method>(x)` as an argument: its kind is not known there."""
    funcs, calls = [], []
    for r, src in RECEIVERS:
        if r not in names:
            continue
        calls.append('xs = [%s]' % src)
        for m in _missing(src):
            funcs.append('def f_%s_%s(x):\n    return x.%s(%s)\n\n' % (r, m, m, _args(m)))
            calls.append('show(%r, %r, lambda: f_%s_%s(xs[0]))' % (r, m, r, m))
    return _SHOW + ''.join(funcs) + in_main('\n'.join(calls))


def known_receiver_program(names, rng, per=22):
    """The receiver is a local of a statically known kind (a name bound to a literal)."""
    calls = []
    for r, src in RECEIVERS:
        if r not in names:
            continue
        miss = _missing(src)
        for m in rng.sample(miss, min(per, len(miss))):
            calls.append('x = %s\ntry:\n    x.%s(%s)\n    print(%r, %r, "ok")\nexcept AttributeError as e:\n'
                         '    print(%r, %r, "AttributeError", e)' % (src, m, _args(m), r, m, r, m))
    return _SHOW + in_main('\n'.join(calls))


_GROUPS = (('list', 'tuple', 'str'), ('dict', 'set', 'bytes', 'frozenset'), ('int', 'float', 'None', 'bool'),
           ('deque', 'Counter'), ('keys', 'values', 'items'))


class MethodMatrix(unittest.TestCase):
    @unittest.skipUnless(HAVE_CC, 'needs gcc')
    def test_unknown_receiver_every_method(self):
        for i, group in enumerate(_GROUPS):
            check_program(self, 'um%d' % i, unknown_receiver_program(group))

    @unittest.skipUnless(HAVE_CC, 'needs gcc')
    def test_known_receiver_sampled(self):
        for i, group in enumerate(_GROUPS):
            check_program(self, 'km%d' % i, known_receiver_program(group, random.Random(8100 + i)))

    @unittest.skipUnless(HAVE_CC, 'needs gcc')
    def test_reported_tuple_programs(self):
        text = '''class W:
    def __init__(self):
        self.t = (1, 2)


def f(t):
    try:
        t.append(1)
    except AttributeError as e:
        print(e)


def g(t):
    return t.keys()


w = W()
try:
    w.t.get(1)
except AttributeError as e:
    print(e)
f((1, 2))
l = [(1, 2)]
try:
    l[0].keys()
except AttributeError as e:
    print(e)
try:
    g((3,))
except AttributeError as e:
    print(e)
print(w.t.count(1), w.t.index(2), l[0].count(2))
'''
        check_program(self, 'tuple_reported', text)

    @unittest.skipUnless(HAVE_CC, 'needs gcc')
    def test_uncaught_attribute_error(self):
        text = in_main('def f(t):\n    return t.get(1)\nprint("before")\nprint(f((1, 2)))\nprint("after")')
        check_program(self, 'attr_uncaught', text, rc=1)

    @unittest.skipUnless(HAVE_CC, 'needs gcc')
    def test_valid_methods_still_work(self):
        # the methods a receiver does have, called on a value of unknown kind, still run (the guard lets them through)
        text = '''from collections import deque, Counter


def attempt(f):
    try:
        print(f())
    except Exception as e:
        print(type(e).__name__, e)


def lst(x):
    x.append(4)
    x.sort()
    print(x.pop(), x.index(2), x.count(1), x.copy(), x)


def dct(x):
    print(x.get("a"), x.get("z", 5), x.keys(), x.items())    # a view is a snapshot (C106): nothing changes the dict in this call
    print(x.setdefault("q", 1), x.pop("a"), x)


def txt(x):
    print(x.split(","), x.upper(), x.find("b"), x.join(["x", "y"]), x.startswith("a"))


def sett(x):
    x.add(3)
    x.discard(1)
    print(sorted(x.union({9})), x.isdisjoint({7}), sorted(x))


def dq(x):
    x.appendleft(0)
    x.rotate(1)
    print(x.popleft(), x)
    x.extend([8])
    print(x, x.count(8), x.index(8))
    attempt(lambda: x.sort())


def ctr(x):
    print(x.most_common(1), x.total(), sorted(x.elements()), x.get("a"), x.keys())
    attempt(lambda: x.append(1))


def tup(x):
    print(x.count(1), x.index(2))
    attempt(lambda: x.get(1))


def num(x):
    print(x.bit_length(), x.bit_count())
    attempt(lambda: x.append(1))


def flt(x):
    print(x.is_integer())
    attempt(lambda: x.get(1))


def main():
    lst([3, 1, 2])
    dct({"a": 1})
    txt("a,b")
    sett({1, 2})
    dq(deque([1, 2, 3]))
    ctr(Counter("aab"))
    tup((1, 2, 1))
    num(5)
    flt(2.5)


main()
'''
        check_program(self, 'valid_methods', text)


# ---- 2. dict views -----------------------------------------------------------------------------------------------------

_VIEWS_FIXED = '''from collections import Counter


def show(f):
    try:
        print(f())
    except Exception as e:
        print(type(e).__name__, e)


def keys_of(d):
    return d.keys()


def main():
    d = {"a": 1, "b": 2}
    e = {}
    k = d.keys()
    v = d.values()
    it = d.items()
    print(k, v, it)
    print(e.keys(), e.values(), e.items())
    print(repr(k), str(v), f"{it}", "%s" % (k,))
    print([k, v], (it,), {"x": k})
    print(len(k), len(v), len(it), len(e.keys()))
    print("a" in k, "z" in k, 2 in v, 5 in v, ("a", 1) in it, ("a", 2) in it)
    print(list(k), list(v), list(it), sorted(it), sorted(k, reverse=True), tuple(v), sorted(set(k)))
    print(sum(v), max(k), min(v), ",".join(k), bool(k), bool(e.keys()))
    for x in k:
        print(x)
    for x, y in it:
        print(x, y)
    print([x for x in v], {x: 1 for x in k})
    print(k == {"a", "b"}, {"a", "b"} == k, k == {"a"}, k != {"a", "b"}, k == frozenset(["a", "b"]))
    print(k == d.keys(), k == {"a": 1, "b": 2}.keys(), k == {"a": 1}.keys(), k == ["a", "b"], k == ("a", "b"))
    print(it == {("a", 1), ("b", 2)}, it == {("a", 1)}, it == d.items(), it == [("a", 1), ("b", 2)])
    print(v == v, v == d.values(), v == [1, 2])
    print(sorted(k & {"a", "z"}), sorted(k | {"z"}), sorted(k - {"a"}), sorted(k ^ {"a", "z"}))
    print(sorted({"a", "z"} & k), sorted({"z"} | k), sorted({"a", "z"} - k), sorted({"a", "z"} ^ k))
    print(sorted(k & ["a", "q"]), sorted(k | ["q"]), sorted(["a", "q"] - k), sorted(k - k), sorted(k & e.keys()))
    print(sorted(it & {("a", 1), ("c", 3)}), sorted(it | {("c", 3)}))
    print(type(k & {"a"}).__name__, type(k | k).__name__)
    show(lambda: v & {1})
    show(lambda: {1} | v)
    show(lambda: k & 5)
    show(lambda: 5 - k)
    show(lambda: k[0])
    show(lambda: v[0])
    show(lambda: it[0:1])
    show(lambda: k.append("z"))
    show(lambda: v.sort())
    show(lambda: it.get(1))
    show(lambda: keys_of(d).add(1))
    c = Counter("aab")
    print(c.keys(), c.values(), c.items(), sorted(c.keys()))
    print(c.keys() == {"a", "b"})
    print([k, v][0], [k, v][1])
    d["c"] = 3
    print(d.keys(), d.values(), d.items())
    print(list(d.keys()) + ["z"], list(d.values()) * 2)
    ks = list(d.keys())
    ks.append("q")
    print(ks)


main()
'''


def _view_case(rng, n):
    keys = rng.sample(range(-5, 12), rng.randrange(0, 6))
    d = {k: rng.randrange(-3, 4) for k in keys}
    pool = list(range(-5, 12))
    s = sorted(rng.sample(pool, rng.randrange(0, 5)))
    lines = ['d%d = %r' % (n, d), 'v%d = %s' % (n, rng.choice(('d%d.keys()', 'd%d.values()', 'd%d.items()')) % n)]
    kind = 'keys' if 'keys' in lines[1] else 'values' if 'values' in lines[1] else 'items'
    v = 'v%d' % n
    other = {'keys': 'set(%r)', 'values': '%r', 'items': 'set(zip(%r, %r))'}[kind]
    other = other % ((s,) if kind != 'items' else (s, s))
    probes = ['print(%s)' % v, 'print(repr(%s), str(%s), f"{%s}")' % (v, v, v), 'print(len(%s), bool(%s))' % (v, v),
              'print(sorted(%s))' % v, 'print(list(%s) == sorted(d%d.%s()))' % (v, n, kind) if kind == 'keys' else 'print(list(%s))' % v,
              'print(%s == %s, %s != %s)' % (v, other, v, other), 'print(%s == %s)' % (v, v)]
    elem = {'keys': repr(rng.choice(pool)), 'values': repr(rng.randrange(-3, 4)), 'items': '(%d, %d)' % (rng.choice(pool), rng.randrange(-3, 4))}[kind]
    probes.append('print(%s in %s, %s not in %s)' % (elem, v, elem, v))
    for op in rng.sample(('&', '|', '-', '^'), 2):
        probes.append('show(lambda: sorted(%s %s %s))' % (v, op, other))
        probes.append('show(lambda: sorted(%s %s %s))' % (other, op, v))
    probes.append('show(lambda: %s[0])' % v)
    probes.append('show(lambda: %s.append(1))' % v)
    rng.shuffle(probes)
    return lines + probes


class DictViews(unittest.TestCase):
    @unittest.skipUnless(HAVE_CC, 'needs gcc')
    def test_fixed_program(self):
        check_program(self, 'views_fixed', _VIEWS_FIXED)

    @unittest.skipUnless(HAVE_CC, 'needs gcc')
    def test_random_programs(self):
        for seed in range(6):
            lines = []
            for i in range(4):
                lines += _view_case(random.Random(8300 + seed * 10 + i), i)
            text = ('def show(f):\n    try:\n        print(f())\n    except Exception as e:\n        print(type(e).__name__, e)\n\n\n'
                    + in_main('\n'.join(lines)))
            check_program(self, 'views_rand%d' % seed, text)

    @unittest.skipUnless(HAVE_CC, 'needs gcc')
    def test_typed_programs_print_views(self):
        # annotated dicts, tuple keys, Counter, defaultdict: the typed path and the tuple / collections passes refuse a view
        # shown as a value; the default build takes the general path
        text = '''from collections import Counter, defaultdict


def tot(d: dict[str, int]) -> int:
    n = 0
    for k in d.keys():
        n += d[k]
    for v in d.values():
        n += v
    for k, v in d.items():
        n += v
    return n + len(d.keys()) + sum(d.values()) + max(d.values())


def main() -> None:
    d: dict[str, int] = {"a": 1, "b": 2}
    t: dict[tuple[int, int], int] = {(1, 2): 3}
    print(tot(d), sorted(d.items()), list(d.keys()), "a" in d.keys())
    print(t.keys(), t.items(), t.values())
    print(d.keys() & {"a"}, d.keys() == {"a", "b"})
    c = Counter("abca")
    print(c.keys(), c.values(), c.items())
    g = defaultdict(list)
    g["x"].append(1)
    print(g.keys(), g.items())
    ks = d.keys()
    for k in ks:
        print(k)
    print(ks)


main()
'''
        check_program(self, 'views_typed', text)

    @unittest.skipUnless(HAVE_CC, 'needs gcc')
    def test_typed_path_refuses_a_view_by_name_and_keeps_its_loops(self):
        shown = 'def main() -> None:\n    d: dict[str, int] = {"a": 1}\n    print(d.items())\n\n\nmain()\n'
        looped = ('def main() -> None:\n    d: dict[str, int] = {"a": 1, "b": 2}\n    n = 0\n    for k in d.keys():\n'
                  '        n += d[k]\n    for k, v in d.items():\n        n += v\n    print(n, len(d.keys()), sorted(d.items()))\n\n\nmain()\n')
        with tempfile.TemporaryDirectory(prefix='ail-gaps2-') as directory:
            _, built = _build(directory, 'typed_shown', shown, False, {'AIL_NO_GENERAL': '1'})
            self.assertNotEqual(built.returncode, 0)
            self.assertIn('dict.items used as a value', built.stdout + built.stderr)
            exe, built = _build(directory, 'typed_loop', looped, False, {'AIL_NO_GENERAL': '1'})
            self.assertEqual(built.returncode, 0, built.stdout + built.stderr)
            got = subprocess.run([str(exe)], capture_output=True, text=True, timeout=60)
            self.assertEqual(got.stdout, '6 2 [(\'a\', 1), (\'b\', 2)]\n')

    @unittest.skipUnless(HAVE_CC, 'needs gcc')
    def test_general_loop_over_keys_keeps_the_indexed_loop(self):
        text = ('def total(d):\n    n = 0\n    for k in d.keys():\n        n += d[k]\n    for v in d.values():\n        n += v\n'
                '    return n\n\n\ndef main():\n    print(total({"a": 1, "b": 2}))\n\n\nmain()\n')
        with tempfile.TemporaryDirectory(prefix='ail-gaps2-') as directory:
            _, built = _build(directory, 'loop', text, True, extra_args=('--debug-dir', str(Path(directory) / 'dbg')))
            self.assertEqual(built.returncode, 0, built.stdout + built.stderr)
            c = (Path(directory) / 'dbg' / 'program.c').read_text(encoding='utf-8', errors='replace')
            body = c[c.index('static ail_st pf_total(ail_ctx *cx, ail_obj *out, ail_obj pv_d) {'):]
            body = body[:body.index('\n}\n')]
            self.assertEqual(body.count('>= _v->n) break;'), 2, body)    # the snapshot list walked by index, once per loop
            self.assertNotIn('ail_it_next', body)
            self.assertNotIn('ail_iter(', body)


# ---- 3. str methods given an argument of the wrong type (C111) ------------------------------------------------
# `'a1'.count(1)` was 3 and `'a1'.index(1)` 0 when the receiver's kind was not known; find, rfind, replace, strip,
# removeprefix ... read the argument as a str without a check. Each program passes the arguments through a function.

STR_ARGS = "def run(s, name):\n    out = []\n    for arg in (1, 2.5, [1], b'a'):\n        try:\n            if name == 'count': r = s.count(arg)\n            elif name == 'index': r = s.index(arg)\n            elif name == 'rindex': r = s.rindex(arg)\n            elif name == 'find': r = s.find(arg)\n            elif name == 'rfind': r = s.rfind(arg)\n            elif name == 'startswith': r = s.startswith(arg)\n            elif name == 'endswith': r = s.endswith(arg)\n            elif name == 'split': r = s.split(arg)\n            elif name == 'rsplit': r = s.rsplit(arg)\n            elif name == 'replace': r = s.replace(arg, 'x')\n            elif name == 'replace2': r = s.replace('a', arg)\n            elif name == 'strip': r = s.strip(arg)\n            elif name == 'lstrip': r = s.lstrip(arg)\n            elif name == 'rstrip': r = s.rstrip(arg)\n            elif name == 'join': r = s.join(arg)\n            elif name == 'join2': r = s.join([arg])\n            elif name == 'in': r = arg in s\n            elif name == 'partition': r = s.partition(arg)\n            elif name == 'rpartition': r = s.rpartition(arg)\n            elif name == 'removeprefix': r = s.removeprefix(arg)\n            elif name == 'removesuffix': r = s.removesuffix(arg)\n            elif name == 'ljust': r = s.ljust(5, arg)\n            elif name == 'center': r = s.center(5, arg)\n            elif name == 'zfill': r = s.zfill(arg)\n            elif name == 'ljust2': r = s.ljust(arg)\n            elif name == 'cnt2': r = s.count('a', arg)\n            elif name == 'split2': r = s.split('a', arg)\n            elif name == 'startswith2': r = s.startswith('a', arg)\n            elif name == 'translate': r = s.translate(arg)\n\n            elif name == 'expandtabs': r = s.expandtabs(arg)\n            elif name == 'splitlines': r = s.splitlines(arg)\n            else: r = '?'\n            out.append(repr(r))\n        except (TypeError, ValueError, AttributeError) as e:\n            out.append(type(e).__name__ + ':' + str(e))\n    return out\nNAMES = ['count','index','rindex','find','rfind','startswith','endswith','split','rsplit','replace','replace2','strip','lstrip','rstrip','join','join2','in','partition','rpartition','removeprefix','removesuffix','ljust','center','zfill','ljust2','cnt2','split2','startswith2','expandtabs','splitlines']\ndef main():\n    for n in NAMES:\n        print(n)\n        for s in ('a1 a', 'a1 a'[:2]+'a'):\n            for x in run(s, n): print('  ', x)\nmain()\n"

# ---- 4. a method whose argument count differs by receiver type (C112) ------------------------------------------
# `d.pop()` on a dict, a Counter or `{}` was AttributeError (the guard dropped the type the handler refused for its
# argument count); every owner of the name now gets CPython's own count text.

ARITY = "from collections import deque, Counter\ndef pp0(v):\n    return v.pop()\ndef pp1(v):\n    return v.pop(0)\ndef pp2(v):\n    return v.pop(0, 5)\ndef cnt1(v):\n    return v.count(1)\ndef cnt2(v):\n    return v.count(1, 0)\ndef idx2(v):\n    return v.index(1, 0)\ndef run(f, v):\n    try:\n        r = f(v)\n        return repr(r)\n    except (TypeError, IndexError, KeyError, ValueError, AttributeError) as e:\n        return type(e).__name__ + ':' + str(e)\n\ndef main():\n    which = ['pop0', 'pop1', 'pop2', 'count1', 'count2', 'index2']\n    fs = [pp0, pp1, pp2, cnt1, cnt2, idx2]\n    for name, f in zip(which, fs):\n        mk = 0\n        for v in ([1, 2], {0: 'a', 1: 'b'}, {1, 2}, deque([1, 2]), Counter('ab'), 'a1', (1, 2)):\n            print(name, mk, run(f, v))\n            mk += 1\n\nmain()\n"

POP0 = 'from collections import deque, Counter\n\n\ndef f_pop(x):\n    return x.pop()\n\n\ndef show(i, x):\n    try:\n        f_pop(x)\n        print(i, "ok")\n    except Exception as e:\n        print(i, type(e).__name__, e)\n\n\ndef main():\n    n = 0\n    for x in ({}, Counter("ab"), {1: 2}, [], deque(), {1}):\n        show(n, x)\n        n += 1\n\n\nmain()\n'

# ---- 5. set.pop() takes the first element in iteration order (C113) -------------------------------------------

SET_POP = "def gen(s):\n    return s.pop()\n\n\ndef main():\n    a = {1, 2}\n    print(a.pop(), a)\n    c = {5}\n    print(c.pop(), c)\n    print(gen({1, 2}), gen({2, 4, 6}))\n    d = set()\n    for i in range(6):\n        d.add(i * 3)\n    out = []\n    while d:\n        out.append(d.pop())\n    print(out)\n    e = {3, 1, 2}\n    e.discard(3)\n    e.add(3)\n    print(e.pop(), e.pop(), e.pop())\n    f = {'only'}\n    print(f.pop(), len(f))\n    try:\n        gen(set())\n    except KeyError as ex:\n        print('KE', ex)\n\n\nmain()\n"

# a model of the insertion order is kept in a list; every pop must return the first element of the model (the general
# path through a function, a local set of ints and of strs in the default build); the last lines drain a large set
SET_POP_MODEL = "def lcg(x):\n    return (x * 1103515245 + 12345) % 2147483648\n\ndef run_int(seed, n):\n    s = set()\n    model = []\n    x = seed\n    bad = 0\n    for step in range(n):\n        x = lcg(x)\n        op = (x >> 8) % 7\n        v = (x >> 12) % 40\n        if op <= 2:\n            if v not in s:\n                model.append(v)\n            s.add(v)\n        elif op == 3:\n            if v in s:\n                model.remove(v)\n            s.discard(v)\n        elif op <= 5:\n            if s:\n                a = s.pop()\n                b = model[0]\n                model.remove(a)\n                if a != b:\n                    bad += 1\n        else:\n            if len(s) != len(model):\n                bad += 100\n            if list(s) != model:\n                bad += 1000\n    return bad, len(s)\n\ndef run_str(seed, n):\n    s = set()\n    model = []\n    x = seed\n    bad = 0\n    for step in range(n):\n        x = lcg(x)\n        op = (x >> 8) % 7\n        v = 'k' + str((x >> 12) % 40)\n        if op <= 2:\n            if v not in s:\n                model.append(v)\n            s.add(v)\n        elif op == 3:\n            if v in s:\n                model.remove(v)\n            s.discard(v)\n        elif op <= 5:\n            if s:\n                a = s.pop()\n                b = model[0]\n                model.remove(a)\n                if a != b:\n                    bad += 1\n        else:\n            if list(s) != model:\n                bad += 1000\n    return bad, len(s)\n\ndef gen_pop(s):\n    return s.pop()\n\ndef run_gen(seed, n):\n    s = set()\n    model = []\n    x = seed\n    bad = 0\n    for step in range(n):\n        x = lcg(x)\n        op = (x >> 8) % 7\n        v = (x >> 12) % 40\n        if op <= 2:\n            if v not in s:\n                model.append(v)\n            s.add(v)\n        elif op == 3:\n            if v in s:\n                model.remove(v)\n            s.discard(v)\n        elif op <= 5:\n            if s:\n                a = gen_pop(s)\n                b = model[0]\n                model.remove(a)\n                if a != b:\n                    bad += 1\n        else:\n            if list(s) != model:\n                bad += 1000\n    return bad, len(s)\n\ndef drain(n):\n    s = set()\n    for i in range(n):\n        s.add(i * 7 + 3)\n    t = 0\n    c = 0\n    while s:\n        t += s.pop()\n        c += 1\n    return t, c\n\ndef work(n):\n    s = {0}\n    seen = 0\n    total = 0\n    while s and seen < n:\n        x = s.pop()\n        seen += 1\n        total += x\n        s.add(x + 1)\n        s.add(x + 2)\n        s.discard(x + 1)\n    return total, len(s)\n\ndef main():\n    bad = 0\n    for seed in range(1, 40):\n        bad += run_int(seed, 400)[0] + run_str(seed, 400)[0] + run_gen(seed, 400)[0]\n    print(bad)\n    print(drain(100000))\n    print(work(20000))\n\nmain()\n"

SET_POP_TYPED = "def run(seed, n):\n    s = set()\n    t = set()\n    ms = []\n    mt = []\n    x = seed\n    bad = 0\n    for step in range(n):\n        x = (x * 1103515245 + 12345) % 2147483648\n        op = (x >> 8) % 6\n        v = (x >> 12) % 30\n        k = 'k' + str(v)\n        if op <= 2:\n            if v not in s:\n                ms.append(v)\n                mt.append(k)\n            s.add(v)\n            t.add(k)\n        elif op == 3:\n            if v in s:\n                ms.remove(v)\n                mt.remove(k)\n            s.discard(v)\n            t.discard(k)\n        elif len(s) > 0:\n            a = s.pop()\n            b = t.pop()\n            if a != ms[0] or b != mt[0]:\n                bad += 1\n            ms.pop(0)\n            mt.pop(0)\n        if step % 50 == 0:\n            q1 = []\n            for q in s:\n                q1.append(q)\n            q2 = []\n            for q in t:\n                q2.append(q)\n            if q1 != ms or q2 != mt:\n                bad += 1000\n    return bad\n\ndef main():\n    tot = 0\n    for seed in range(1, 60):\n        tot += run(seed, 600)\n    print(tot)\n\nmain()\n"


class StrArgs(unittest.TestCase):
    @unittest.skipUnless(HAVE_CC, 'needs gcc')
    def test_wrong_argument_type(self):
        check_program(self, 'strargs', STR_ARGS)


class ArityByType(unittest.TestCase):
    @unittest.skipUnless(HAVE_CC, 'needs gcc')
    def test_pop_count_index_arity(self):
        check_program(self, 'arity', ARITY)

    @unittest.skipUnless(HAVE_CC, 'needs gcc')
    def test_pop_without_argument(self):
        check_program(self, 'pop0', POP0)


class SetPop(unittest.TestCase):
    @unittest.skipUnless(HAVE_CC, 'needs gcc')
    def test_first_in_iteration_order(self):
        check_program(self, 'setpop', SET_POP)

    @unittest.skipUnless(HAVE_CC, 'needs gcc')
    def test_against_a_model(self):
        with tempfile.TemporaryDirectory(prefix='ail-gaps2-') as directory:
            tail = _cpython(directory, 'model', SET_POP_MODEL)[0].split(b'\n')[1:]     # the drain lines do not depend on the order
            for name, text in (('model', SET_POP_MODEL), ('typed', SET_POP_TYPED)):
                for general in (True, False):
                    got, err = _build_run(directory, '%s%d' % (name, general), text, general)
                    self.assertIsNotNone(got, err)
                    self.assertEqual(got[1], 0, got)
                    lines = got[0].split(b'\n')
                    self.assertEqual(lines[0], b'0', got[0])
                    if name == 'model':
                        self.assertEqual(lines[1:], tail, got[0])


if __name__ == '__main__':
    unittest.main()

"""Silent differences closed by refusal or by a fix, round 1 (DIFFERENCES C106, C107, C109, C110, C102), against CPython 3.12.

1. A dict view kept in a name, a field, an item or a container (`ks = d.keys()`) is a snapshot on both paths, so it showed
   the old contents after the dict changed and a loop over it did not raise "dictionary changed size during iteration"
   (C106, C107). The compiler now refuses a kept view that may be read after a change of a dict, is handed on (returned,
   stored, passed to a function of the program) or sits in a field / item / container; a view that is made and used at once,
   or kept in a local name that is only read before any change, builds as before and equals CPython.

2. The ordering operators `<`, `<=`, `>`, `>=` with a keys or items view and a set or another such view are the subset tests
   of CPython; with a values view or a list they raise a TypeError that names the operator and both types (C109).

3. A view of an `OrderedDict` (`o.keys()`, `.values()`, `.items()`) used as a value: CPython shows `odict_keys([...])`; the class
   the general path uses for an `OrderedDict` held in a field or at module level gave a list. A program that shows, returns or
   keeps such a view is refused by name; walking it (`for`, `list`, `sorted`, `len`, `join`, `sum`) is unchanged (C110).

Programs are built with the general path forced and with the default build; stdout and the exit status must match CPython,
a refused program must fail to build with the construct named.
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


def _cpython(directory, name, text):
    src = Path(directory) / (name + '_cpython.py')
    src.write_text(text, encoding='utf-8')
    done = subprocess.run([sys.executable, '-B', str(src)], capture_output=True, timeout=120,
                          env=dict(os.environ, PYTHONUTF8='1'))
    return done.stdout.replace(b'\r\n', b'\n'), done.returncode, _last_line(done.stderr)


def _last_line(err):
    lines = [x for x in err.decode('utf-8', 'replace').splitlines() if x.strip()]
    return lines[-1] if lines else ''


def _build(directory, name, text, general):
    src = Path(directory) / (name + '.ail')
    src.write_text(text, encoding='utf-8')
    exe = Path(directory) / ('exe_' + name + ('_g' if general else '_d'))
    env = dict(os.environ, AIL_NO_CACHE='1', AIL_QUIET_FALLBACK='1')
    env.pop('AIL_NO_GENERAL', None)
    if general:
        env['AIL_UNIFIED_FORCE'] = '1'
    cmd = [sys.executable, '-B', CHATGPT, 'compile', src.name, '--syntax', 'python', '-o', exe.name]
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
    with tempfile.TemporaryDirectory(prefix='ail-silent1-') as directory:
        want = _cpython(directory, name, text)
        test.assertEqual(want[1], rc, text)
        for general in modes:
            got, err = _build_run(directory, name, text, general)
            test.assertIsNotNone(got, '%s (general=%s)\n%s' % (text[:3000], general, err))
            test.assertEqual(got, want, '%s (general=%s)\n%s' % (text[:3000], general, err))


def check_refused(test, name, text, words, modes=(True, False)):
    """The program does not build in either mode, and the message contains every word of `words`."""
    with tempfile.TemporaryDirectory(prefix='ail-silent1-') as directory:
        for general in modes:
            _, built = _build(directory, '%s%d' % (name, general), text, general)
            test.assertNotEqual(built.returncode, 0, '%s built (general=%s)' % (name, general))
            for word in words:
                test.assertIn(word, built.stdout + built.stderr, '%s (general=%s)' % (name, general))


# ---- 1. a kept dict view (C106, C107) ----------------------------------------------------------------------------------

KEPT_REFUSED = {
    'snapshot_len': 'd = {"a": 1, "b": 2}\nv = d.keys()\nd["c"] = 3\nprint(len(v), v)\n',
    'loop_grow': 'd = {"a": 1, "b": 2}\nks = d.keys()\nfor k in ks:\n    d[k + "z"] = 1\nprint(len(d))\n',
    'values_pop': 'd = {1: 2}\ne = d\nv = d.values()\ne.pop(1)\nprint(list(v), v)\n',
    'items_clear': 'd = {"a": 1}\nit = d.items()\nd.clear()\nprint(list(it))\n',
    'field': ('class C:\n    def __init__(self):\n        self.d = {"a": 1}\n        self.v = self.d.values()\n'
              '    def add(self):\n        self.d["b"] = 2\n\n\nc = C()\nc.add()\nprint(list(c.v))\n'),
    'item': 'd = {"a": 1}\nh = {}\nh["k"] = d.keys()\nd["b"] = 2\nprint(len(h["k"]))\n',
    'in_list': 'd = {"a": 1}\nxs = [d.keys(), d.values()]\nd["b"] = 2\nprint(len(xs[0]), len(xs[1]))\n',
    'unpacked': 'd = {"a": 1}\nk, v = d.keys(), d.values()\nd["b"] = 2\nprint(len(k), len(v))\n',
    'walrus': 'd = {"a": 1}\nif (k := d.keys()):\n    d["b"] = 2\n    print(len(k))\n',
    'returned_name': 'd = {"a": 1}\n\n\ndef f():\n    ks = d.keys()\n    return ks\n\n\nprint(list(f()))\n',
    'mutated_by_call': ('d = {"a": 1}\n\n\ndef grow(m):\n    m["z"] = 1\n\n\nv = d.keys()\ngrow(d)\nprint(len(v))\n'),
    'method_mutates': ('class R:\n    def __init__(self):\n        self.d = {}\n    def add(self, k):\n        self.d[k] = 1\n\n\n'
                       'r = R()\nr.add("a")\nks = r.d.keys()\nr.add("b")\nprint(sorted(ks))\n'),
    'loop_rebind': 'd = {}\nfor i in range(3):\n    it = d.items()\n    d[i] = i\n    print(len(it))\n',
    'passed_on': 'd = {"a": 1}\nks = d.keys()\nxs = []\nxs.append(ks)\nd["b"] = 2\nprint(len(xs[0]))\n',
    'annotated': 'd = {"a": 1}\nks: object = d.keys()\nd["b"] = 2\nprint(len(ks))\n',
}

# built as before and equal to CPython: a view made and used at once, or kept in a local that is read before any change
KEPT_ALLOWED = {
    'used_at_once': ('d = {"a": 1, "b": 2}\nfor k in list(d.keys()):\n    d[k + "z"] = 1\n'
                     'print(sorted(d), len(d.items()), sorted(d.keys() & {"a"}))\nprint([k for k in d.keys()], [x for x in d.values()])\n'
                     '\n\ndef f():\n    return d.keys()\n\n\nprint(sorted(f()))\n'),
    'read_only': ('d = {"a": 1, "b": 2}\nks = d.keys()\nvs = d.values()\nprint(ks, vs, len(ks), sorted(ks), "a" in ks)\n'
                  '\n\ndef tot(x):\n    return sum(x.values())\n\n\nprint(tot(d), list(vs))\nfor k in ks:\n    print(k)\n'
                  'it = d.items()\nn = [(k, v) for k, v in it]\nprint(n, it == {("a", 1), ("b", 2)})\n'),
    'changed_before': ('def run():\n    d = {"a": 1}\n    d["b"] = 2\n    d.update({"c": 3})\n    ks = d.keys()\n    vs = d.values()\n'
                       '    print(sorted(ks), list(vs), len(ks))\n    return len(d)\n\n\nprint(run())\n'),
    'copy_then_change': ('d = {"a": 1}\nks = list(d.keys())\nd["b"] = 2\nprint(ks, sorted(d.keys()))\n'
                         'it = tuple(d.items())\nd["c"] = 3\nprint(it)\n'),
    'literal_display': 'xs = [{"a": 1}.keys(), {"b": 2}.values()]\nprint(xs, len(xs[0]))\nx = {"a": 1}.items()\nx.pop(1) if False else None\nprint(x)\n',
    'view_then_empty': 'd = {}\nv = d.keys()\nprint(v, len(v), list(d.values()), {}.items())\n',
}


@unittest.skipUnless(HAVE_CC, 'needs gcc')
class KeptViews(unittest.TestCase):
    def test_refused_by_name(self):
        for name, text in sorted(KEPT_REFUSED.items()):
            check_refused(self, 'kept_' + name, text, ['dict view kept'])

    def test_still_builds_and_matches_cpython(self):
        for name, text in sorted(KEPT_ALLOWED.items()):
            check_program(self, 'ok_' + name, text)

    def test_loop_over_a_stored_view_raises_in_cpython(self):
        # the reference behaviour the refusal stands in for
        with tempfile.TemporaryDirectory(prefix='ail-silent1-') as directory:
            got = _cpython(directory, 'ref', KEPT_REFUSED['loop_grow'])
        self.assertEqual(got[1], 1)
        self.assertIn('dictionary changed size during iteration', got[2])


# ---- 2. ordering of dict views (C109) ----------------------------------------------------------------------------------

VIEW_ORDER_1 = 'd = {"a": 1, "b": 2}\ne = {}\ns = {"a", "b", "c"}\nprint(d.keys() < s, d.keys() <= s, d.keys() > s, d.keys() >= s)\nprint(s > d.keys(), s >= d.keys(), s < d.keys(), s <= d.keys())\nprint(d.keys() <= d.keys(), d.keys() < d.keys(), d.keys() >= {"a", "b"}, d.keys() > {"a"})\nprint(d.items() < {("a", 1), ("b", 2), ("c", 3)}, d.items() <= {("a", 2)}, d.items() >= {("a", 1)})\nprint(e.keys() < s, e.keys() <= e.keys(), e.keys() < set(), e.keys() <= frozenset())\nprint(d.keys() < frozenset(["a", "b", "q"]), {"x": 1}.keys() < d.keys())\ndef op(a, b, k):\n    if k == 0:\n        return a < b\n    if k == 1:\n        return a <= b\n    if k == 2:\n        return a > b\n    return a >= b\n\n\ndef cmp(a, b):\n    return a < b, a <= b, a > b, a >= b\nprint(cmp(d.keys(), {"a"}), cmp({"a", "z"}, d.keys()), cmp(d.items(), d.items()))\nfor args in ((d.values(), d.values()), (d.keys(), [1]), ([1], d.keys()), (d.values(), {"a"}), (d.keys(), "ab"), (d.items(), None)):\n    for k in range(4):\n        try:\n            print(op(args[0], args[1], k))\n        except TypeError as ex:\n            print(ex)\nbig = {i: i for i in range(300)}\nprint(big.keys() < set(range(301)), big.keys() <= set(range(299)), set(range(300)) >= big.keys())\nprint(1 < 2 < 3, [1] < [2], "a" < "b")\n'

VIEW_ORDER_2 = 'from collections import Counter, defaultdict\nd = {"a": 1, "b": 2}\nks = d.keys()\nit = d.items()\nprint(ks < {"a", "b", "c"}, {"a"} < ks, ks <= ks, {"a", "b"} <= ks, ks >= {"b"}, it > {("a", 1)}, it >= it)\nprint({"a"} < ks < {"a", "b", "c"}, ks > {"a"} > set())\nc = Counter("aab")\nprint(c.keys() < {"a", "b", "z"}, c.keys() >= {"a"})\ng = defaultdict(list)\ng["x"].append(1)\nprint(g.keys() <= {"x", "y"}, g.items() > set())\nclass W:\n    def __init__(self, v):\n        self.v = v\n    def sub(self, other):\n        return self.v < other\nprint(W(d.keys()).sub({"a", "b", "q"}), W({"a"}).sub(d.keys()))\nfor bad in (lambda: d.values() < d.values(), lambda: d.keys() < [1, 2, 3], lambda: ks <= "ab", lambda: d.items() > 5):\n    try:\n        print(bad())\n    except TypeError as e:\n        print(e)\nnested = {(1, 2): [3], (4, 5): [6]}\nprint(nested.keys() < {(1, 2), (4, 5), (0, 0)}, nested.items() <= {((1, 2), 7)})\n'

# no view in the program: the C it gets must not contain the view comparison
NO_VIEW = 'xs = [1, 2]\nys = {3}\nprint(xs < [3], ys > {1}, 1 <= 2, "a" >= "b")\n'


@unittest.skipUnless(HAVE_CC, 'needs gcc')
class ViewOrder(unittest.TestCase):
    def test_keys_items_values_against_sets_and_each_other(self):
        check_program(self, 'vorder1', VIEW_ORDER_1)

    def test_names_fields_counters_defaultdicts_chains(self):
        check_program(self, 'vorder2', VIEW_ORDER_2)

    def test_only_programs_with_a_view_get_the_comparison(self):
        with tempfile.TemporaryDirectory(prefix='ail-silent1-') as directory:
            for name, text, has in (('plain', NO_VIEW, False), ('view', 'd = {1: 2}\nprint(d.keys() < {1, 2})\n', True)):
                src = Path(directory) / (name + '.ail')
                src.write_text(text, encoding='utf-8')
                env = dict(os.environ, AIL_NO_CACHE='1', AIL_QUIET_FALLBACK='1', AIL_UNIFIED_FORCE='1')
                built = subprocess.run([sys.executable, '-B', CHATGPT, 'compile', src.name, '--syntax', 'python', '-o', 'exe_' + name,
                                        '--debug-dir', 'dbg_' + name], cwd=directory, capture_output=True, text=True, timeout=900, env=env)
                self.assertEqual(built.returncode, 0, built.stdout + built.stderr)
                c_text = (Path(directory) / ('dbg_' + name) / 'program.c').read_text()
                self.assertEqual('ail__view_cmp' in c_text, has, name)
            check_program(self, 'plain', NO_VIEW)


# ---- 3. views of an OrderedDict (C110) ---------------------------------------------------------------------------------

OD_REFUSED = {'module_level': 'from collections import OrderedDict, defaultdict\no = OrderedDict()\no["a"] = 1\nprint(o.keys(), o.values(), o.items())\nprint(list(o.keys()), len(o.keys()))\n', 'local': 'from collections import OrderedDict\ndef main():\n    o = OrderedDict()\n    o["a"] = 1\n    print(o.keys(), o.values(), o.items())\nmain()\n', 'field_returned': 'from collections import OrderedDict\nclass Cache:\n    def __init__(self):\n        self.o = OrderedDict()\n    def show(self):\n        return self.o.items()\nc = Cache()\nc.o["x"] = 1\nprint(c.show(), c.o.keys())\nprint(list(c.o.keys()), sorted(c.o.values()), len(c.o.items()))\nfor k, v in c.o.items():\n    print(k, v)\n',
              'stored': 'from collections import OrderedDict\no = OrderedDict()\nks = o.keys()\no["a"] = 1\nprint(len(ks))\n'}
OD_WALKED = 'from collections import OrderedDict\nclass Cache:\n    def __init__(self):\n        self.o = OrderedDict()\n    def put(self, k, v):\n        self.o[k] = v\n        self.o.move_to_end(k)\nc = Cache()\nc.put("x", 1)\nc.put("y", 2)\nc.put("x", 3)\nprint(list(c.o.keys()), sorted(c.o.values()), len(c.o.items()), c.o, "x" in c.o.keys())\nfor k, v in c.o.items():\n    print(k, v)\nprint([k for k in c.o.keys()], ",".join(c.o.keys()), sum(c.o.values()), list(reversed(list(c.o.items()))))\n'


@unittest.skipUnless(HAVE_CC, 'needs gcc')
class OrderedDictViews(unittest.TestCase):
    def test_a_shown_view_is_refused_not_printed_as_a_list(self):
        for name, text in sorted(OD_REFUSED.items()):
            check_refused(self, 'od_' + name, text, ['OrderedDict'])

    def test_walked_views_equal_cpython(self):
        check_program(self, 'od_walked', OD_WALKED)


if __name__ == '__main__':
    unittest.main()

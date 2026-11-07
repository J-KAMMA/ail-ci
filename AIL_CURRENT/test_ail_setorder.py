"""Set / frozenset iteration order is loud: a walk of a set is refused by name.

CPython walks a set in its hash table's order (a set of ints in a fixed one, a set of str in a
per-run random one). AIL's sets keep insertion order, so `for x in s`, `list(s)`, `tuple(s)`,
`print(s)`, `str(s)`, `repr(s)`, an f-string of one, a list comprehension over one and `s.pop()`
can all print a different order from CPython. Each is refused by name with the rewrite
`sorted(s)`; the order-free uses -- `x in s`, `len(s)`, `sorted(s)`, `min(s)`, `max(s)`,
`sum(s)` and the set operators / comparisons / mutators -- keep building and match CPython.

The typed path refuses at compile time when it knows the value is a set. The general path does
the same for a value it can prove is a set (`ail_iter_visible` / `_refuse_set_walk`), and raises
the same named error at run time for a set that reached the walk through an argument, a list
item, an attribute or a dict value (`ail2_refuse_set_order`).

S1  the order-free forms match CPython on the typed, default and general builds
S2  every order-revealing construct is refused by name on the typed and general builds
S3  a dynamic set is refused at run time by name, never silently reordered
S4  ordered results (sorted forms) still match CPython through operators and methods
"""
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent
PYC = ROOT / 'python' / 'pkg-v12' / 'pyc.py'
ON_312 = sys.version_info[:2] == (3, 12)

MESSAGE = 'sorted('
TYPED_REFUSAL = 'walking a set'
RUNTIME_REFUSAL = 'walking a set or frozenset'


def build(directory, text, name, mode):
    """Compile `text` in one mode: general (boxed path alone, --general-only), typed
    (AIL_NO_GENERAL=1) or default (typed first, general on a refusal)."""
    source, exe = Path(directory, name + '.py'), Path(directory, name + '_' + mode)
    source.write_text(text, encoding='utf-8')
    env = dict(os.environ)
    env.pop('AIL_NO_GENERAL', None)
    env['AIL_IR'] = '0'
    if mode == 'general':
        command = [sys.executable, '-B', str(PYC), exe.name, '--file', source.name, '--general-only']
    else:
        if mode == 'typed':
            env['AIL_NO_GENERAL'] = '1'
        command = [sys.executable, '-B', str(ROOT / 'ail_chatgpt.py'), 'compile', source.name,
                   '--syntax', 'python', '-o', exe.name]
    return subprocess.run(command, cwd=directory, capture_output=True, text=True, timeout=900, env=env), exe


def run_cpython(directory, text, name):
    source = Path(directory, name + '_cpython.py')
    source.write_text(text, encoding='utf-8')
    return subprocess.run([sys.executable, str(source)], capture_output=True, text=True,
                          timeout=120, encoding='utf-8')


def run_exe(exe):
    return subprocess.run([str(exe)], capture_output=True, text=True, timeout=120, encoding='utf-8')


ALL_MODES = ('typed', 'default', 'general')


ORDER_FREE = '''def main():
    a = {40, 33, 26, 19, 12, 5}
    print(len(a), 19 in a, 100 in a, sorted(a), min(a), max(a), sum(a), a.isdisjoint({1000}), a.issubset(a))
    a.add(7)
    a.discard(26)
    a.add(26)
    print(len(a), 19 in a, 100 in a, sorted(a), min(a), max(a), sum(a), a.isdisjoint({1000}), a.issubset(a))
    g = {-1, -2, -3, -40, -7, 0, 7}
    print(len(g), -1 in g, 1 in g, sorted(g), min(g), max(g), sum(g), g.isdisjoint({1000}))
main()
'''


ORDER_FREE_GENERAL = '''def show(tag, s):
    print(tag, len(s), 19 in s, 100 in s, sorted(s), min(s), max(s), sum(s))

def main():
    show("frozen", frozenset(range(40, 0, -7)))
    show("set_range", set(range(1, 20, 3)))
    show("frozen_neg", frozenset([-1, -2, -3, -40, -7, 0, 7]))
    w = {"alpha", "beta", "gamma", "delta", "epsilon"}
    print(len(w), "beta" in w, "zzz" in w, sorted(w), min(w), max(w))
main()
'''


ORDERED_METHODS = '''def main():
    x = {1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 40, 41, 42}
    y = {5, 6, 7, 200, 300, 400, 3, 41}
    fx = frozenset(x)
    print(sorted(x | y), sorted(x & y), sorted(x - y), sorted(x ^ y))
    print(sorted(x.union(y, [300, 5, 77], range(3), {88})))
    print(sorted(x.intersection(y, [5, 6, 7, 99], range(6, 9))))
    print(sorted(x.difference(y, [5, 6], [7, 8], range(40, 43))))
    print(sorted(x.symmetric_difference(y)))
    print(sorted(fx | y), sorted(fx & y), sorted(fx - y), sorted(fx ^ y))
    print(x.issubset(y), {5, 6}.issubset(y), x.issuperset({1, 2}),
          x.isdisjoint({100}), x.isdisjoint(y), len(fx), fx == x)
    t = x.copy()
    t.update(y, [1000, 2000], range(3))
    print(sorted(t), 1 in t, sorted(t))
    u = set(x)
    u.intersection_update(range(0, 60), [5, 6, 7, 8, 9, 10, 40, 41, 300, 1000])
    print(sorted(u))
    u.difference_update([5], {6}, range(40, 42))
    print(sorted(u))
    u.symmetric_difference_update([1000, 7, 7, 99])
    print(sorted(u))
    w = {"pear", "apple", "fig"}
    print(sorted(w), sorted(w | {"kiwi"}), "pear" in w, len(w))
main()
'''

# every construct that shows a set's iteration order, in the shape a program would write
REFUSALS = {
    'for_literal': 'def f():\n    for x in {40, 33, 26}:\n        print(x)\nf()\n',
    'for_set': 'def f():\n    for x in set(range(40, 0, -7)):\n        print(x)\nf()\n',
    'for_frozenset': 'def f():\n    for x in frozenset(range(40, 0, -7)):\n        print(x)\nf()\n',
    'for_bound': 'def f():\n    s = {40, 33, 26}\n    for x in s:\n        print(x)\nf()\n',
    'for_typed': 'def f() -> None:\n    s: set[int] = {40, 33, 26}\n    for x in s:\n        print(x)\nf()\n',
    'for_typed_str': 'def f() -> None:\n    s: set[str] = {"a", "b", "c"}\n    for x in s:\n        print(x)\nf()\n',
    'list': 'def f():\n    s = {40, 33, 26}\n    print(list(s))\nf()\n',
    'list_typed': 'def f() -> None:\n    s: set[int] = {40, 33, 26}\n    print(len(list(s)))\nf()\n',
    'tuple': 'def f():\n    s = {40, 33, 26}\n    print(tuple(s))\nf()\n',
    'print': 'def f():\n    s = {40, 33, 26}\n    print(s)\nf()\n',
    'comprehension': 'def f():\n    s = {40, 33, 26}\n    print([x * 2 for x in s])\nf()\n',
    'nested_comp': 'def f():\n    print([x for x in frozenset({3, 1, 2})])\nf()\n',
}

# constructs caught at run time (the set flows through a value the general path cannot type)
DYNAMIC = {
    'argument': 'def consume(s):\n    for x in s:\n        print(x)\ndef f():\n    consume({40, 33, 26})\nf()\n',
    'list_item': 'def f():\n    xs = [{40, 33, 26}]\n    for x in xs[0]:\n        print(x)\nf()\n',
    'dict_value': 'def f():\n    d = {"k": {40, 33, 26}}\n    for x in d["k"]:\n        print(x)\nf()\n',
    'fstring': 'def f():\n    s = frozenset(range(40, 0, -7))\n    print(f"{s}")\nf()\n',
    'str': 'def consume(v):\n    print(str(v))\ndef f():\n    consume({40, 33, 26})\nf()\n',
    'repr': 'def consume(v):\n    print(repr(v))\ndef f():\n    consume({40, 33, 26})\nf()\n',
    'pop': 'def f():\n    s = {40, 33, 26}\n    print(s.pop())\nf()\n',
    'pop_typed': 'def f() -> None:\n    s: set[int] = {40, 33, 26}\n    print(s.pop())\nf()\n',
}


class SetOrderTests(unittest.TestCase):
    def test_s1_order_free_forms_match_cpython(self):
        with tempfile.TemporaryDirectory() as directory:
            for text, name, modes in ((ORDER_FREE, 'free', ALL_MODES),
                                      (ORDER_FREE_GENERAL, 'freegen', ('general', 'default'))):
                want = run_cpython(directory, text, name)
                self.assertEqual(want.returncode, 0, want.stderr)
                for mode in modes:
                    built, exe = build(directory, text, name, mode)
                    self.assertEqual(built.returncode, 0, '%s: %s' % (mode, built.stdout + built.stderr))
                    got = run_exe(exe)
                    self.assertEqual(got.stdout, want.stdout, '%s: %s' % (mode, got.stderr[-600:]))
                    self.assertEqual(got.returncode, 0, mode)

    def test_s2_every_order_revealing_construct_is_refused_by_name(self):
        with tempfile.TemporaryDirectory() as directory:
            for name, text in sorted(REFUSALS.items()):
                for mode in ('typed', 'general'):
                    built, exe = build(directory, text, 'r_' + name, mode)
                    shown = built.stdout + built.stderr
                    self.assertNotEqual(built.returncode, 0,
                                        '%s/%s built, it must be refused:\n%s' % (name, mode, shown))
                    # every shape is refused with a message that names the set (the typed path
                    # has its own wording for print/str/repr; the set-order rule wording carries
                    # the `sorted(...)` rewrite)
                    self.assertIn('set', shown.lower(), '%s/%s: %s' % (name, mode, shown))
                    self.assertNotIn('the C compiler rejected this', shown, '%s/%s' % (name, mode))

    def test_s3_a_dynamic_set_is_refused_at_run_time(self):
        with tempfile.TemporaryDirectory() as directory:
            for name, text in sorted(DYNAMIC.items()):
                built, exe = build(directory, text, 'd_' + name, 'general')
                self.assertEqual(built.returncode, 0, '%s: %s' % (name, built.stdout + built.stderr))
                got = run_exe(exe)
                self.assertNotEqual(got.returncode, 0, '%s printed a set order:\n%s' % (name, got.stdout))
                marker = 'set.pop()' if name.startswith('pop') else RUNTIME_REFUSAL
                self.assertIn(marker, got.stderr, '%s: %s' % (name, got.stderr[-600:]))

    def test_s4_ordered_forms_of_operators_and_methods_match_cpython(self):
        with tempfile.TemporaryDirectory() as directory:
            want = run_cpython(directory, ORDERED_METHODS, 'methods')
            self.assertEqual(want.returncode, 0, want.stderr)
            for mode in ('general', 'default'):
                built, exe = build(directory, ORDERED_METHODS, 'methods', mode)
                self.assertEqual(built.returncode, 0, '%s: %s' % (mode, built.stdout + built.stderr))
                got = run_exe(exe)
                self.assertEqual(got.stdout, want.stdout, '%s: %s' % (mode, got.stderr[-600:]))

    def test_s5_sorted_of_a_set_matches_cpython_on_both_builds(self):
        text = ('def f():\n'
                '    s = {40, 33, 26, 19, 12, 5}\n'
                '    print(sorted(s), sorted(s, reverse=True))\n'
                'f()\n')
        with tempfile.TemporaryDirectory() as directory:
            want = run_cpython(directory, text, 'sorted')
            for mode in ALL_MODES:
                built, exe = build(directory, text, 'sorted', mode)
                self.assertEqual(built.returncode, 0, '%s: %s' % (mode, built.stdout + built.stderr))
                self.assertEqual(run_exe(exe).stdout, want.stdout, mode)


if __name__ == '__main__':
    unittest.main()

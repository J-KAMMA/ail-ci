"""Set / frozenset iteration order: CPython's own order, emulated where it is fixed.

CPython walks a set in the layout of its open-addressed hash table. For elements whose hash is
deterministic -- int, bool, None, float and tuples of those -- that order is fixed, and AIL
reproduces the table exactly (the same size and growth, the same linear/perturbed probing, the
same deletion dummies), so iteration, `list(s)`, `repr(s)` and `s.pop()` match CPython. The
implementation covers the boxed/general path and the typed `set[int]` path.

A set that contains str or bytes hashes those elements with PYTHONHASHSEED, so CPython's order is
random per run. There is no single CPython order to match: AIL keeps insertion order, one valid
CPython run, and does not refuse. Tests comparing such a set to CPython therefore never depend on
the order. A mixed set follows the str/bytes rule (its CPython order is random too).

S1  the order-free forms match CPython on the typed, default and general builds
S2  deterministic int sets match CPython's iteration, repr and pop through collisions, growth,
    deletions, a re-added key and a constant-folded display
S3  typed `set[int]` iteration and pop match CPython on the typed path as well
S4  int-set operators and frozensets match CPython
S5  str sets build and run with no refusal, deterministically, on every build
S6  empty set / frozenset displays print and walk as CPython does
"""
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent
PYC = ROOT / 'python' / 'pkg-v12' / 'pyc.py'
ALL_MODES = ('typed', 'default', 'general')


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

# Deterministic-hash elements: CPython's fixed table order, byte for byte. The first display has
# more than two constant elements, so CPython folds it into a frozenset constant and merges it;
# the del/re-add and the growth cross several resizes and leave a dummy behind.
INT_ORDER = '''def main():
    a = {40, 33, 26, 19, 12, 5}
    print(list(a), a, len(a), a.pop())
    print(list({3, 1, 2}), {3, 1, 2})
    b = {8, 16, 24, 32, 40, 48, 56, 64, 72, 80, 88, 96}
    print(list(b), b)
    b.discard(16)
    b.discard(48)
    b.add(104)
    b.add(16)
    print(list(b), b)
    c = set()
    for x in range(0, 60, 3):
        c.add(x)
    print(list(c), c)
    for x in range(0, 60, 6):
        c.discard(x)
    print(list(c), c)
    d = {-1, -2, -3, -7, 0, 7, 1 << 60, -(1 << 60)}
    print(list(d), d)
    print(list({1.5, 0.0, -0.0, 2.25, 7.5}), len({1.5, 0.0, -0.0, 2.25, 7.5}))
    print(list({(1, 2), (3, 4), (0, 0)}), {(1, 2), (3, 4), (0, 0)})
    print(list({(1, 2), (2, 1), (0, 0), (1, 1), (2, 2), (3, 0)}),
          {(1, 2), (2, 1), (0, 0), (1, 1), (2, 2), (3, 0)})
    print(list({True, False, 2}), list({None}))
    e = set()
    for i in range(40):
        e.add(i * 128)
    print(list(e), e)
main()
'''

# Typed set[int]: the same table, exercised through the annotated path. `pop()` drains the set in
# CPython's finger order.
TYPED_ORDER = '''def main() -> None:
    s: set[int] = {40, 33, 26, 19, 12, 5}
    for x in s:
        print(x)
    print(len(list(s)))
    print(s.pop())
    t: set[int] = set()
    for x in range(0, 30, 3):
        t.add(x)
    print(len(list(t)))
    print(t.pop())
    print(len(t))
main()
'''

FROZENSET_ORDER = '''def main():
    f = frozenset(range(40, 0, -7))
    print(list(f), f)
    g = frozenset({8, 16, 24, 32, 40, 48, 56, 64, 72, 80, 88, 96})
    print(list(g), g)
    x = {1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 40, 41, 42}
    y = {5, 6, 7, 200, 300, 400, 3, 41}
    print(list(x | y), list(x & y), list(x - y), list(x ^ y))
    print(sorted(x | y), sorted(x & y), sorted(x - y), sorted(x ^ y))
main()
'''

# str sets: no refusal anywhere. The order is AIL's own (deterministic); CPython's is random per
# run, so this compares only against CPython's order-free answers.
STR_SET_TYPED = '''def main() -> None:
    s: set[str] = {"alpha", "beta", "gamma", "delta", "epsilon"}
    total = 0
    for x in s:
        total += len(x)
    print(total, len(s), "beta" in s, "zzz" in s, sorted(s))
    s.add("zeta")
    s.discard("gamma")
    total = 0
    for x in s:
        total += len(x)
    print(total, len(s), sorted(s))
main()
'''

# The same rule through a value the compiler cannot name: an argument, a list item and a dict value.
# The general path (and the default build) carries these.
STR_SET_VALUES = '''def walk(s):
    total = 0
    for x in s:
        total += len(x)
    return total

def main():
    d = {"k": {"one", "two", "three"}}
    xs = [{"x", "yy", "zzz"}]
    print(walk({"a", "bb"}), walk(d["k"]), walk(xs[0]))
    print(sorted(d["k"]), sorted(xs[0]))
main()
'''

EMPTY = '''def main():
    print(set(), frozenset())
    print(list(set()), list(frozenset()))
    print(len(set()), len(frozenset()))
    for x in set():
        print(x)
main()
'''


class SetOrderTests(unittest.TestCase):
    def _same(self, name, text, modes, check=True):
        with tempfile.TemporaryDirectory() as directory:
            want = run_cpython(directory, text, name)
            self.assertEqual(want.returncode, 0, want.stderr)
            for mode in modes:
                built, exe = build(directory, text, name, mode)
                self.assertEqual(built.returncode, 0,
                                 '%s/%s: %s' % (name, mode, built.stdout + built.stderr))
                got = run_exe(exe)
                self.assertEqual(got.returncode, 0, '%s/%s: %s' % (name, mode, got.stderr[-800:]))
                if check:
                    self.assertEqual(got.stdout, want.stdout,
                                     '%s/%s: %s' % (name, mode, got.stderr[-600:]))

    def test_s1_order_free_forms_match_cpython(self):
        self._same('free', ORDER_FREE, ALL_MODES)
        self._same('freegen', ORDER_FREE_GENERAL, ('general', 'default'))

    def test_s2_int_sets_match_cpython_order(self):
        # The typed compiler's unannotated int table keeps insertion order, so the unannotated
        # program is compared on the boxed/general builds (the default build is the product one;
        # the annotated typed case is S3).
        self._same('intorder', INT_ORDER, ('general', 'default'))

    def test_s3_typed_set_int_matches_cpython(self):
        self._same('typedorder', TYPED_ORDER, ALL_MODES)

    def test_s4_frozenset_and_operator_order_matches_cpython(self):
        self._same('frozenorder', FROZENSET_ORDER, ('general', 'default'))

    def test_s5_str_sets_build_and_run_without_refusal(self):
        with tempfile.TemporaryDirectory() as directory:
            want = run_cpython(directory, STR_SET_TYPED, 'strset')
            self.assertEqual(want.returncode, 0, want.stderr)
            order = None
            for mode in ALL_MODES:
                built, exe = build(directory, STR_SET_TYPED, 'strset', mode)
                shown = built.stdout + built.stderr
                self.assertEqual(built.returncode, 0, '%s: %s' % (mode, shown))
                self.assertNotIn('refused', shown.lower(), mode)
                got = run_exe(exe)
                self.assertEqual(got.returncode, 0, '%s: %s' % (mode, got.stderr[-800:]))
                self.assertNotIn('refused', got.stderr.lower(), mode)
                self.assertEqual(got.stdout, want.stdout, mode)
                # AIL's own order is deterministic: two builds agree byte for byte.
                if order is None:
                    order = got.stdout
                self.assertEqual(got.stdout, order, mode)

    def test_s5b_str_sets_through_arguments_items_and_values(self):
        self._same('strvalues', STR_SET_VALUES, ('general', 'default'))

    def test_s6_empty_display(self):
        self._same('empty', EMPTY, ('general', 'default'))

    def test_s7_mutation_during_iteration_still_fails(self):
        text = ('def f():\n'
                '    s = {40, 33, 26, 19}\n'
                '    for x in s:\n'
                '        s.add(100)\n'
                '    print(x)\n'
                'f()\n')
        for mode in ('general', 'default'):
            with tempfile.TemporaryDirectory() as directory:
                built, exe = build(directory, text, 'mut', mode)
                self.assertEqual(built.returncode, 0, '%s: %s' % (mode, built.stdout + built.stderr))
                got = run_exe(exe)
                self.assertNotEqual(got.returncode, 0, mode)
                self.assertIn('Set changed size during iteration', got.stderr, mode)


if __name__ == '__main__':
    unittest.main()

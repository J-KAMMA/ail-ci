"""Two general-path bugs fixed on branch gcroots beside the rooting audit (test_ail_gcstress), as differential tests
against CPython.

1. `h[1] += [3]` (DIFFERENCES C85). An augmented assignment whose target is an item (`h[i]`, `d[k]`, `g[i][j]`) built
   a new object with the plain operator and stored it back, so a list grown with += (or *=) and a set changed with
   |= / -= / &= / ^= was a new object: another name for the old one did not see the change. CPython's list.__iadd__ /
   set.__ior__ change the object itself. The item target now takes the in-place operator, as a name and an
   attribute target already did; an int, float, str or tuple item still gets a new value.
2. A str method on a value whose kind is not known statically (DIFFERENCES C86): `w.upper()`, `w.find("a")`,
   `w.split()`, ... picked the str helper by name alone and ran it on an int, a float, None or a list (an empty
   string, -1, garbage). The receiver is now checked first: anything but a str raises CPython's AttributeError
   ("'int' object has no attribute 'upper'"); the message of the list/dict/set methods dispatched at run time
   (`.count`, `.pop`, ...) names the type the same way.

Programs are generated from fixed seeds and built with pyc.py --general-only and with the default build; stdout and
the exit status must match CPython.
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
PYC = str(ROOT / 'python' / 'pkg-v12' / 'pyc.py')
HAVE_CC = shutil.which('gcc') is not None


def _cpython(directory, name, text):
    src = Path(directory) / (name + '_cpython.py')
    src.write_text(text, encoding='utf-8')
    done = subprocess.run([sys.executable, '-B', str(src)], capture_output=True, timeout=120,
                          env=dict(os.environ, PYTHONUTF8='1'))
    return done.stdout.replace(b'\r\n', b'\n'), done.returncode


def _build_run(directory, name, text, general):
    src = Path(directory) / (name + '.py')
    src.write_text(text, encoding='utf-8')
    exe = Path(directory) / ('exe_' + name + ('_g' if general else '_d'))
    env = dict(os.environ, AIL_SURFACE='python', AIL_NO_CACHE='1', AIL_QUIET_FALLBACK='1')
    env.pop('AIL_NO_GENERAL', None)
    cmd = [sys.executable, '-B', PYC, str(exe), '--file', str(src)] + (['--general-only'] if general else [])
    built = subprocess.run(cmd, cwd=directory, capture_output=True, text=True, timeout=900, env=env)
    if built.returncode != 0:
        return None, (built.stdout + built.stderr)[-1500:]
    got = subprocess.run([str(exe)], capture_output=True, timeout=120, cwd=directory)
    return (got.stdout.replace(b'\r\n', b'\n'), got.returncode), got.stderr.decode('utf-8', 'replace')[-800:]


# ---- 1. augmented assignment to an item ----------------------------------------------------------------------------

# (initial item, right-hand side, operator): the item is held under a second name before the update
_ITEMS = (
    ('[1]', '[3]', '+='), ('[1, 2]', '(9,)', '+='), ('[1]', '[]', '+='), ('["a"]', '["b", "c"]', '+='),
    ('[0]', '2', '*='), ('[5, 6]', '0', '*='), ('{1}', '{2}', '|='), ('{1, 2}', '{2}', '-='),
    ('{1, 2, 3}', '{2, 3, 4}', '&='), ('{1, 2}', '{2, 3}', '^='), ('7', '5', '+='), ('2.5', '0.5', '+='),
    ('"s"', '"t"', '+='), ('(1,)', '(2,)', '+='), ('[[1]]', '[[2]]', '+='), ('7', '3', '*='),
)
_HOLDERS = ('list', 'dict', 'nested', 'defaultdict', 'attr', 'global_list')


def _aug_case(rng, n):
    init, rhs, op = rng.choice(_ITEMS)
    holder = rng.choice(_HOLDERS)
    if holder == 'list':
        setup = 'h = [0, %s]' % init
        target = 'h[1]'
    elif holder == 'dict':
        setup = 'h = {"k": %s}' % init
        target = 'h["k"]'
    elif holder == 'nested':
        setup = 'h = [[0, %s]]' % init
        target = 'h[0][1]'
    elif holder == 'defaultdict':
        setup = 'h = defaultdict(list)\n    h["k"] = %s' % init
        target = 'h["k"]'
    elif holder == 'attr':
        setup = 'h = Holder(%s)' % init
        target = 'h.v'
    else:
        setup = 'h = G\n    h[0] = %s' % init
        target = 'h[0]'
    via_fn = rng.random() < 0.3
    opname = {'+=': 'add', '*=': 'mul', '|=': 'or', '-=': 'sub', '&=': 'and', '^=': 'xor'}[op]
    lines = ['def case%d():' % n, '    ' + setup, '    old = %s' % target]
    if via_fn:
        # the update made inside a function, on the holder passed in
        lines.append('    bump_%s_%s(h, %s)' % (holder, opname, rhs))
    else:
        lines.append('    %s %s %s' % (target, op, rhs))
    lines.append('    new = %s' % target)
    # `is` on a number item is refused by name (DIFFERENCES C115), so a number item compares by value
    same = 'old == new' if init.replace('.', '', 1).isdigit() else 'old is new'
    lines.append('    print(%d, sorted(old) if isinstance(old, set) else old, '
                 'sorted(new) if isinstance(new, set) else new, %s)' % (n, same))
    helper = ('bump_%s_%s' % (holder, opname), target, op) if via_fn else None
    return '\n'.join(lines) + '\n', helper


def make_aug_program(seed, count=14):
    rng = random.Random(seed)
    cases, helpers = [], {}
    for n in range(count):
        text, helper = _aug_case(rng, n)
        cases.append(text)
        if helper:
            helpers[helper[0]] = helper
    head = ['from collections import defaultdict', '', '',
            'class Holder:', '    def __init__(self, v):', '        self.v = v', '', '',
            'G = [0]', '', '']
    for name in sorted(helpers):
        _, target, op = helpers[name]
        head += ['def %s(h, x):' % name, '    %s %s x' % (target, op), '', '']
    calls = '\n'.join('case%d()' % n for n in range(count))
    return '\n'.join(head) + '\n' + '\n\n'.join(cases) + '\n\n' + calls + '\n'


@unittest.skipUnless(HAVE_CC, 'no C compiler')
class AugItemDifferential(unittest.TestCase):
    def run_seed(self, seed, general):
        text = make_aug_program(seed)
        with tempfile.TemporaryDirectory(prefix='ail-gcroots-') as directory:
            want = _cpython(directory, 'aug%d' % seed, text)
            self.assertEqual(want[1], 0, text)
            got, err = _build_run(directory, 'aug%d' % seed, text, general)
            self.assertIsNotNone(got, err)
            self.assertEqual(got, want, '%s\n%s' % (text, err))

    def test_general_path_matches_cpython(self):
        for seed in range(4):
            with self.subTest(seed=seed):
                self.run_seed(seed, True)

    def test_default_build_matches_cpython(self):
        for seed in (10, 11):
            with self.subTest(seed=seed):
                self.run_seed(seed, False)

    def test_fixed_shapes(self):
        text = '''def main():
    a = [1]
    h = [a, a]
    h[1] += [3]
    print(a, h)
    d = {"k": [1]}
    alias = d["k"]
    d["k"] += [4]
    print(alias, d)
    g = [[1], [2]]
    first = g[0]
    g[0] *= 3
    print(first, g)
    s = {"a": {1}}
    sa = s["a"]
    s["a"] |= {2}
    print(sorted(sa))
    t = ([1], 2)
    inner = t[0]
    try:
        t[0] += [7]
    except TypeError:
        print("TypeError", inner)
    n = {"x": 1}
    n["x"] += 2
    xs = [1, 2.5, "s"]
    xs[0] += 10
    xs[1] += 1
    xs[2] += "t"
    print(n, xs)


main()
'''
        for general in (True, False):
            with self.subTest(general=general), tempfile.TemporaryDirectory(prefix='ail-gcroots-') as directory:
                want = _cpython(directory, 'augf', text)
                got, err = _build_run(directory, 'augf', text, general)
                self.assertIsNotNone(got, err)
                self.assertEqual(got, want, err)


# ---- 2. str methods on a value of unknown kind ---------------------------------------------------------------------

_VALUES = ('"p q"', '7', '2.5', 'None', '[1, "p"]', '(1, 2)', '{"k": 1}', '{3}', 'True', 'Thing()', '""', '"5"')
_CALLS = ('upper()', 'lower()', 'find("p")', 'rfind("q")', 'startswith("p")', 'endswith("q")', 'split()',
          'split(",")', 'rsplit()', 'splitlines()', 'strip()', 'lstrip()', 'rstrip()', 'join(["x", "y"])',
          'replace("p", "z")', 'isdigit()', 'isalpha()', 'isalnum()', 'isupper()', 'islower()', 'isspace()',
          'title()', 'capitalize()', 'swapcase()', 'partition(" ")', 'rpartition(" ")', 'ljust(4)', 'rjust(4)',
          'center(5)', 'zfill(4)', 'count("p")', 'index("p")', 'casefold()', 'isdecimal()', 'isnumeric()',
          'isidentifier()', 'isascii()', 'istitle()', 'expandtabs(2)')


def make_meth_program(seed, count=40):
    rng = random.Random(seed)
    lines = ['class Thing:', '    pass', '', '',
             'def spoiled():', '    ws = "a b".split()', '    ws.clear()']
    vals = [rng.choice(_VALUES) for _ in range(6)]
    for v in vals:
        lines.append('    ws.append(%s)' % v)
    lines += ['    return ws', '', '', 'def main():', '    ws = spoiled()', '    n = 0', '    for w in ws:']
    calls = [rng.choice(_CALLS) for _ in range(count // 6 + 1)]
    for c in calls:
        lines += ['        try:',
                  '            r = w.%s' % c,
                  '            print(n, %r, repr(r))' % c,
                  '        except AttributeError as e:',
                  '            print(n, %r, "AttributeError", e)' % c,
                  '        except (TypeError, ValueError) as e:',
                  '            print(n, %r, type(e).__name__)' % c,
                  '        n += 1']
    lines += ['', '', 'main()', '']
    return '\n'.join(lines)


@unittest.skipUnless(HAVE_CC, 'no C compiler')
class StrMethodDispatch(unittest.TestCase):
    def run_seed(self, seed, general):
        text = make_meth_program(seed)
        with tempfile.TemporaryDirectory(prefix='ail-gcroots-') as directory:
            want = _cpython(directory, 'meth%d' % seed, text)
            self.assertEqual(want[1], 0, text)
            got, err = _build_run(directory, 'meth%d' % seed, text, general)
            self.assertIsNotNone(got, err)
            self.assertEqual(got, want, '%s\n%s' % (text, err))

    def test_general_path_matches_cpython(self):
        for seed in range(4):
            with self.subTest(seed=seed):
                self.run_seed(seed, True)

    def test_default_build_matches_cpython(self):
        with self.subTest(seed=20):
            self.run_seed(20, False)

    def test_known_str_has_no_check(self):
        """A receiver known to be a str gets the helper directly, as before: the check is only for unknown kinds."""
        text = 'def main():\n    s = "a b"\n    print(s.upper(), s.find("b"), s.split())\n\n\nmain()\n'
        with tempfile.TemporaryDirectory(prefix='ail-gcroots-') as directory:
            got, err = _build_run(directory, 'known', text, True)
            self.assertIsNotNone(got, err)
            c = Path(directory, 'exe_known_g.c').read_text(encoding='utf-8')
            self.assertNotIn('ail2_no_attr(cx,', c)


if __name__ == '__main__':
    unittest.main()

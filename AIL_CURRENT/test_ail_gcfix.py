"""Two general-path bugs found by the unified-IR study (docs/design/UNIFIED_IR.md 9.5), fixed on branch gcfix.

1. `@lru_cache` / `@cache` wrapper (DIFFERENCES C83). The wrapper built its key tuple in a C local, called the cached
   body (which allocates, so a collection may run) and stored the key afterwards. A C local is not a GC root: the
   collector freed the key and the cache then held a dangling pointer (AddressSanitizer: heap-use-after-free in
   ail_obj_eq_raw on gdev g08_000, forced to the general path). The key now lives in a shadow-stack frame slot for the
   whole call. The entry count is also read again after the body, because recursion through the wrapper adds entries
   meanwhile (the stale count overwrote them and shrank the cache).
2. The per-list element-kind record (DIFFERENCES C82). pyboxed2 records 'str' as the element kind of a list that
   `str.split` / `rsplit` / `splitlines` made and keeps it for the variable, so the loop variable of `for w in ws` is compiled
   as a str (`w + "!"`, `w.count("a")`, `[c for c in w]` take the str paths). A change made through another name (the list
   passed to a function that appends an int, stored in a dict or a list, aliased) was not seen: the str code ran on an
   int, a float, a list or None and printed garbage or crashed where CPython prints a value or raises TypeError. The record is now kept only where it is provably exact (the list never escapes, nothing but str enters
   it); where it cannot be kept the name has no record and the program is refused by name or runs the dynamic way.

The differential tests build randomized programs (aliasing through arguments, dict values, list holders, direct
mutation by append / insert / extend / item and slice assignment) with pyc.py --general-only and, for a sample, the default
build, and compare stdout and exit status with CPython. The GC tests run the cached programs under a 16 KiB collection
threshold with AddressSanitizer + UBSan + LeakSanitizer (skipped when gcc has no sanitizers).
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
PYC = str(ROOT / 'python' / 'pkg-v12' / 'pyc.py')
HAVE_CC = shutil.which('gcc') is not None


def _cpython(directory, name, text):
    src = Path(directory) / (name + '_cpython.py')
    src.write_text(text, encoding='utf-8')
    done = subprocess.run([sys.executable, '-B', str(src)], capture_output=True, timeout=120,
                          env=dict(os.environ, PYTHONUTF8='1'))
    return done.stdout.replace(b'\r\n', b'\n'), done.returncode


def _build(directory, name, text, general=True, env=None, keep_c=False):
    src = Path(directory) / (name + '.py')
    src.write_text(text, encoding='utf-8')
    exe = Path(directory) / ('exe_' + name)
    full = dict(os.environ, AIL_SURFACE='python', AIL_NO_CACHE='1', AIL_QUIET_FALLBACK='1')
    full.pop('AIL_NO_GENERAL', None)
    full.update(env or {})
    cmd = [sys.executable, '-B', PYC, str(exe), '--file', str(src)] + (['--general-only'] if general else [])
    return exe, subprocess.run(cmd, cwd=directory, capture_output=True, text=True, timeout=900, env=full)


# ---- randomized aliasing programs ------------------------------------------------------------------------------------

_VALUES = ('"x"', '7', '2.5', 'None', '"yy"', '[1]', '(3, 4)', 'True', '7', '[2]', '5')
_STRS = ('"x"', '"yy"', '"z z"')
_MUT_BODIES = (
    'ys.append(%(v)s)',
    'ys.insert(%(i)d, %(v)s)',
    'ys.extend([%(v)s, %(w)s])',
    'ys[%(j)d] = %(v)s',
    'ys[%(i)d:%(i)d] = [%(v)s]',
    'ys[0:1] = [%(v)s, %(w)s]',
    'ys += [%(v)s]',
    'ys.pop()',
    'ys.reverse()',
    'ys.clear()',
    'ys.append(ys[0])',
    'pass',
)
_SOURCES = (
    '"p q r".split()',
    '"1 2 3".split()',
    '"a,b,c".split(",")',
    '"l1\\nl2\\nl3".splitlines()',
    '[5, 6]',
    '["a", "b"]',
    '[1, 2, 3]',
    'list(range(4))',
    '[]',
)
_OBSERVE = (
    'print(%(a)s)',
    'print(len(%(a)s), %(a)s[0] if %(a)s else None)',
    'for w in %(a)s:\n        try:\n            print(w.count("x"), [c for c in w])\n        except (AttributeError, TypeError):\n            print("AE")',
    'for w in %(a)s:\n        try:\n            print(w + "!")\n        except TypeError:\n            print("TE")',
    'for w in %(a)s:\n        try:\n            print(w * 2, len(w))\n        except TypeError:\n            print("TE")',
    'for w in %(a)s:\n        print(w)',
    'for w in %(a)s:\n        print(repr(w), w == "x", w is None)',
    'print([str(w) for w in %(a)s])',
    'print(%(a)s == %(b)s, %(a)s is %(b)s)',
    'print("-".join(str(w) for w in %(a)s))',
    'print(sorted(str(w) for w in %(a)s))',
    'print(f"{%(a)s}")',
)


def _mutator(rng, name):
    body = rng.choice(_MUT_BODIES) % {'v': rng.choice(_VALUES), 'w': rng.choice(_VALUES),
                                      'i': rng.randrange(0, 2), 'j': 0}
    if body.startswith('ys[') and ':' not in body.split('=')[0] and body != 'ys.append(ys[0])':
        body = 'if ys:\n        ' + body
    return 'def %s(ys):\n    %s\n' % (name, body)


def make_program(seed):
    """One program from `seed`: a list is made, reached through up to three names, changed by a random mutator through a
    random one of them, and observed through the others."""
    rng = random.Random(seed)
    lines = []
    nmut = rng.randint(1, 2)
    for k in range(nmut):
        lines.append(_mutator(rng, 'mut%d' % k))
    lines.append('')
    lines.append('def make():')
    lines.append('    return %s' % rng.choice(_SOURCES))
    lines.append('')
    paths = [('a', 'a')]
    src = rng.choice(_SOURCES[:4]) if rng.random() < 0.6 else rng.choice(_SOURCES)
    body = ['    a = %s' % src if rng.random() < 0.8 else '    a = make()']
    if rng.random() < 0.6:
        body.append('    b = a')
        paths.append(('b', 'b'))
    if rng.random() < 0.5:
        body.append('    d = {"k": a}')
        paths.append(('d["k"]', 'd["k"]'))
    if rng.random() < 0.5:
        body.append('    h = [a, a]')
        paths.append(('h[1]', 'h[1]'))
    if rng.random() < 0.3:
        body.append('    c = a[:]')
        body.append('    c = c or ["c"]')
        paths.append(('c', 'c'))
    body.append('    print(a)')
    for _ in range(rng.randint(1, 3)):
        kind = rng.random()
        target = rng.choice(paths)[0]
        if kind < 0.7:
            body.append('    mut%d(%s)' % (rng.randrange(nmut), target))
        else:
            # `h[1] += [v]` on a subscript target builds a new list on the general path (DIFFERENCES C85); only a
            # plain name can be changed with +=, so the inline form leaves that statement out
            ys = rng.choice([b for b in _MUT_BODIES if not b.startswith('ys +=')]) % {
                'v': rng.choice(_VALUES), 'w': rng.choice(_VALUES), 'i': rng.randrange(0, 2), 'j': 0}
            body.append('    if %s:\n        %s' % (target, ys.replace('ys', target)))
        who = 'a' if rng.random() < 0.7 else rng.choice(paths)[0]
        other = rng.choice(paths)[0]
        obs = rng.choice(_OBSERVE) % {'a': who, 'b': other}
        body.append('    ' + obs)
    lines.append('def main():')
    lines.extend(body)
    lines.append('')
    lines.append('')
    lines.append('main()')
    return '\n'.join(lines) + '\n'


def program_ok_in_cpython(text):
    try:
        compile(text, 'p', 'exec')
    except SyntaxError:
        return False
    return True


class AliasDifferential(unittest.TestCase):
    SEEDS_GENERAL = range(0, 24)
    SEEDS_DEFAULT = range(100, 108)

    def run_seed(self, directory, seed, general):
        text = make_program(seed)
        name = 'p%d' % seed
        want = _cpython(directory, name, text)
        exe, built = _build(directory, name + ('g' if general else 'd'), text, general=general)
        out = (built.stdout + built.stderr)
        if built.returncode:
            # a refusal by name is allowed (the record was dropped and the dynamic way is not built); a bad exit is not
            self.assertIn('not in the subset', out, (seed, out[-600:], text))
            return 'refused'
        got = subprocess.run([str(exe)], capture_output=True, timeout=60, cwd=directory)
        self.assertEqual((got.stdout.replace(b'\r\n', b'\n'), got.returncode), want,
                         '\n--- seed %d ---\n%s\n%s' % (seed, text, got.stderr.decode('utf-8', 'replace')[-300:]))
        return 'ran'

    def test_general_path_matches_cpython(self):
        with tempfile.TemporaryDirectory(prefix='ail-gcfix-') as directory:
            ran = [self.run_seed(directory, s, True) for s in self.SEEDS_GENERAL]
        self.assertGreater(ran.count('ran'), len(ran) // 2, ran)

    def test_default_build_matches_cpython(self):
        with tempfile.TemporaryDirectory(prefix='ail-gcfix-') as directory:
            for s in self.SEEDS_DEFAULT:
                self.run_seed(directory, s, False)

    def test_fixed_shapes(self):
        """The shapes that were wrong before the fix, written out."""
        cases = {
            'arg_append_int': 'def f(ys):\n    ys.append(7)\n\n\nws = "a b".split()\nf(ws)\nfor w in ws:\n    try:\n        print(w + "!")\n'
                              '    except TypeError:\n        print("TE")\n',
            'dict_value': 'def f(d):\n    d["k"].append(7)\n\n\nws = "a b".split()\nd = {"k": ws}\nf(d)\n'
                          'for w in ws:\n    try:\n        print(w + "!")\n    except TypeError:\n        print("TE")\nprint(ws)\n',
            'holder': 'ws = "a b".split()\nh = [ws]\nh[0].append(1.5)\nfor w in ws:\n    try:\n        print(w * 2)\n'
                      '    except TypeError:\n        print("TE")\n',
            'setitem_alias': 'def f(ys):\n    ys[0] = None\n\n\nws = "a b".split()\nb = ws\nf(b)\nfor w in ws:\n    print(w is None)\n',
            'slice_alias': 'def f(ys):\n    ys[0:1] = [3, 4]\n\n\nws = "a b".split()\nf(ws)\nprint(ws)\n'
                           'for w in ws:\n    try:\n        print(w.count("a"), [c for c in w])\n    except (AttributeError, TypeError):\n        print("AE")\n',
            'list_literal': 'def spoil(ys):\n    ys.append("x")\n\n\ne = [5, 6]\nspoil(e)\nprint(e)\n'
                            'f: list = [5, 6]\nspoil(f)\nprint(f)\nprint(e + f)\n',
            'global_from_def': 'ws = "a b".split()\n\n\ndef add():\n    ws.append(1)\n\n\nadd()\nfor w in ws:\n    try:\n'
                               '        print(w + "!")\n    except TypeError:\n        print("TE")\n',
            'closure': 'def f():\n    ws = "a b".split()\n\n    def g():\n        ws.append(5)\n    g()\n    for w in ws:\n'
                       '        try:\n            print(w + "!")\n        except TypeError:\n            print("TE")\n\n\nf()\n',
            'returned': 'def mk():\n    ws = "a b".split()\n    return ws\n\n\nxs = mk()\nxs.append(2.5)\nprint(xs)\n',
            'class_holder': 'class H:\n    def __init__(self, items):\n        self.items = items\n\n\ndef main():\n'
                            '    ws = "a b".split()\n    h = H(ws)\n    h.items.append(None)\n    for w in ws:\n        try:\n'
                            '            print(w + "!")\n        except TypeError:\n            print("TE")\n\n\nmain()\n',
            'readonly_callee': 'def total(ys):\n    n = 0\n    for y in ys:\n        n += len(y)\n    return n\n\n\n'
                               'ws = "a bb".split()\nprint(total(ws))\nfor w in ws:\n    print(w + "!", w.count("b"))\n',
            'str_appends': 'ws = "a b".split()\nws.append("c" + str(1))\nws.insert(0, f"{1}")\nws.extend(["d"])\nws[0] = "z"\n'
                           'ws[1:2] = ["p", "q"]\nws.sort()\nws.reverse()\nfor w in ws:\n    print(w + "!", w.count("a"))\n',
            'unspoiled_split': 'ws = "a b c".split()\nws.append("d")\nfor w in ws:\n    print(w + "!", w.count("a"))\n',
        }
        with tempfile.TemporaryDirectory(prefix='ail-gcfix-') as directory:
            for name, text in cases.items():
                want = _cpython(directory, name, text)
                for general in (True, False):
                    exe, built = _build(directory, '%s_%d' % (name, general), text, general=general)
                    if built.returncode:
                        # a program whose list record is exact (nothing but strs enter it, no unsafe alias) must still build
                        self.assertNotIn(name, ('readonly_callee', 'str_appends', 'unspoiled_split', 'list_literal'),
                                         built.stdout + built.stderr)
                        self.assertIn('not in the subset', built.stdout + built.stderr, name)
                        continue
                    got = subprocess.run([str(exe)], capture_output=True, timeout=60, cwd=directory)
                    with self.subTest(case=name, general=general):
                        self.assertEqual((got.stdout.replace(b'\r\n', b'\n'), got.returncode), want)


# ---- the @lru_cache key ---------------------------------------------------------------------------------------------

LRU_PROGRAM = '''from functools import lru_cache, cache
import functools


@lru_cache(maxsize=None)
def grid(a: int, b: int) -> int:
    if a == 0 or b == 0:
        return 1
    s = str(a) + ":" + str(b)
    return (grid(a - 1, b) + grid(a, b - 1) + len(s)) % 1000003


@cache
def words(n: int, tag: str) -> list:
    out = []
    for i in range(n):
        out.append(tag + str(i) * 3)
    return out


@functools.lru_cache(maxsize=128)
def pairs(k: str) -> tuple:
    return (k, [k + "x", k + "y"], {k: len(k)})


@lru_cache(maxsize=None)
def zero() -> list:
    return [str(i) for i in range(50)]


@lru_cache(maxsize=None)
def collatz(n: int) -> int:
    if n == 1:
        return 0
    t = [n, n + 1, n + 2]
    nxt = n // 2 if n % 2 == 0 else 3 * n + 1
    return 1 + collatz(nxt) + (t[0] - n)


@lru_cache(maxsize=None)
def fib(n: int) -> int:
    if n < 2:
        return n
    return fib(n - 1) + fib(n - 2)


def main() -> None:
    print(grid(14, 14))
    tot = 0
    for i in range(40):
        w = words(i % 17, "t" + str(i % 5))
        tot += len(w) + len(w[-1]) if w else 0
    print(tot)
    acc = 0
    for k in ["k%d" % (i % 23) for i in range(300)]:
        p = pairs(k)
        acc += len(p[1][0]) + p[2][k]
    print(acc)
    print(len(zero()), zero()[49])
    print(max(collatz(i) for i in range(1, 200)))
    print(words(3, "t1") == words(3, "t1"), words(3, "t1") is words(3, "t1"))
    print(fib(90))


main()
'''

SAN = ['-fsanitize=address,undefined', '-fno-sanitize-recover=undefined', '-g', '-fno-omit-frame-pointer']


def _sanitizers_work():
    if not HAVE_CC:
        return False
    with tempfile.TemporaryDirectory(prefix='ail-san-') as d:
        c = Path(d, 't.c')
        c.write_text('int main(void){return 0;}\n')
        r = subprocess.run(['gcc'] + SAN + [str(c), '-o', str(Path(d, 't'))], capture_output=True)
        return r.returncode == 0 and subprocess.run([str(Path(d, 't'))], capture_output=True).returncode == 0


@unittest.skipUnless(HAVE_CC and _sanitizers_work(), 'no C compiler with sanitizers')
class LruKeyRoot(unittest.TestCase):
    def test_cached_programs_under_sanitizers_and_gc_stress(self):
        with tempfile.TemporaryDirectory(prefix='ail-gcfix-') as directory:
            want = _cpython(directory, 'lru', LRU_PROGRAM)
            exe, built = _build(directory, 'lru', LRU_PROGRAM, general=True,
                                env={'AIL_EXTRA_CFLAGS': ' '.join(SAN)})
            self.assertEqual(built.returncode, 0, (built.stdout + built.stderr)[-1500:])
            env = dict(os.environ, ASAN_OPTIONS='detect_leaks=1', UBSAN_OPTIONS='halt_on_error=1')
            got = subprocess.run([str(exe)], capture_output=True, timeout=120, cwd=directory, env=env)
            self.assertEqual((got.stdout.replace(b'\r\n', b'\n'), got.returncode), want, got.stderr.decode()[-800:])
            # the same program with a 16 KiB collection threshold: a collection runs inside nearly every cached body
            c = Path(directory, 'exe_lru.c')
            self.assertTrue(c.exists())
            text = c.read_text(encoding='utf-8')
            stressed = text.replace('#define AIL_GC_INITIAL_THRESHOLD (8u * 1024u * 1024u)',
                                    '#define AIL_GC_INITIAL_THRESHOLD (16384u)')
            self.assertNotEqual(stressed, text)
            sc = Path(directory, 'stress.c')
            sc.write_text(stressed, encoding='utf-8')
            r = subprocess.run(['gcc', '-O1'] + SAN + ['-pthread', '-w', str(sc), '-lm', '-o', str(Path(directory, 'stress'))],
                               capture_output=True, text=True)
            self.assertEqual(r.returncode, 0, r.stderr[-800:])
            got = subprocess.run([str(Path(directory, 'stress'))], capture_output=True, timeout=300, cwd=directory, env=env)
            self.assertEqual((got.stdout.replace(b'\r\n', b'\n'), got.returncode), want, got.stderr.decode()[-800:])

    def test_wrapper_roots_the_key_and_rereads_the_count(self):
        with tempfile.TemporaryDirectory(prefix='ail-gcfix-') as directory:
            exe, built = _build(directory, 'lruc', LRU_PROGRAM, general=True)
            self.assertEqual(built.returncode, 0, (built.stdout + built.stderr)[-800:])
            c = Path(directory, 'exe_lruc.c').read_text(encoding='utf-8')
            m = re.search(r'static ail_st pf_fib\(ail_ctx \*cx, ail_obj \*out, ail_obj pv_n\) \{(.*?)\n\}\n', c, re.S)
            self.assertTrue(m, 'no wrapper found')
            body = m.group(1)
            self.assertIn('AIL_FRAME_ENTER(cx, f, 1);', body)
            self.assertNotIn('ail_obj _key', body)
            self.assertEqual(body.count('.tag == AIL_T_UNBOUND'), 2, body)


class NoLruNoChange(unittest.TestCase):
    """A program that uses neither feature gets the same C: the wrapper text appears only with a cache decorator."""

    def test_no_wrapper_without_a_cache(self):
        with tempfile.TemporaryDirectory(prefix='ail-gcfix-') as directory:
            text = 'def f(n):\n    return n + 1\n\n\nprint(f(2))\n'
            exe, built = _build(directory, 'plain', text, general=True)
            self.assertEqual(built.returncode, 0, built.stderr[-500:])
            c = Path(directory, 'exe_plain.c').read_text(encoding='utf-8')
            self.assertNotIn('_impl(', c)


if __name__ == '__main__':
    unittest.main()

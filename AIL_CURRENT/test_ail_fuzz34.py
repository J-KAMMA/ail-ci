"""Differential fuzz round 34: generator expressions must stay lazy, compared with CPython on both builds.

Found with small programs compared against CPython:

1. A generator expression was materialised as a list where it was made, so a list mutated after
   creation was not seen: `g = (x for x in xs); xs.append(3); list(g)` printed the old items.
   The general path now lowers each generator expression to a generator function: its outermost
   iterable is evaluated at creation, later iterables, conditions and the element at consumption.
2. A generator expression whose element is a tuple was lowered by the tuple pass to an eager list
   comprehension, losing the same laziness (nested loops over two lists mutated after creation).
3. An enclosing function local read by the generator was copied when it was made, so a later
   rebinding was invisible: `n = 2; g = (i + n for i in range(3)); n = 10; list(g)` printed the
   old n. The local is now passed as a getter, which the general path's closure cells keep live.
"""
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent

LAZY = r'''def basic():
    xs = [1, 2]
    g = (x * x for x in xs)
    xs.append(3)
    xs.append(4)
    return list(g)


def pairs():
    xs = [1, 2]
    ys = [10, 20]
    g = ((x, y) for x in xs for y in ys)
    xs.append(3)
    ys.append(30)
    return list(g)


def diagonal():
    zs = [1, 2]
    g = ((i, j) for i in zs for j in range(i, 4))
    zs.append(3)
    return list(g)


def next_then_mutate():
    xs = [1, 2]
    g = (x * 10 for x in xs)
    out = [next(g)]
    xs.append(3)
    out.append(next(g))
    out.append(next(g))
    return out


print(basic())
print(pairs())
print(diagonal())
print(next_then_mutate())
'''

LATE_LOCAL = r'''def rebind_list():
    xs = [1, 2]
    g = (x * len(xs) for x in [1, 2])
    xs = [1, 2, 3]
    return list(g)


def rebind_int():
    n = 2
    g = (i + n for i in range(3))
    n = 10
    return list(g)


def loop_binds():
    gens = []
    for i in range(3):
        gens.append((i + j for j in range(2)))
    return [list(g) for g in gens]


def escapes():
    xs = [1, 2]
    return (x * len(xs) for x in [1, 2, 3])


print(rebind_list())
print(rebind_int())
print(loop_binds())
print(list(escapes()))
'''

EXHAUST = r'''def drain(g):
    out = []
    while True:
        try:
            out.append(next(g))
        except StopIteration:
            return out


g = (x * x for x in range(4))
print(drain(g))
print(drain(g))
print(sum(x for x in []))
print(any(x > 2 for x in [1, 2]))
print(all(x > 0 for x in [1, 2, 3]))
print(list(c for c in "abc"))
print(sorted(v for v in {3: "c", 1: "a", 2: "b"}))
'''


def _cpython(directory, name, text):
    src = Path(directory) / (name + '.py')
    src.write_text(text, encoding='utf-8')
    got = subprocess.run([sys.executable, str(src)], capture_output=True, timeout=120, cwd=directory)
    return got.stdout.replace(b'\r\n', b'\n'), got.returncode


def _build_and_run(directory, name, text, general):
    src = Path(directory) / (name + '.ail')
    src.write_text(text, encoding='utf-8')
    exe = Path(directory) / ('exe_' + name)
    env = dict(os.environ, AIL_NO_CACHE='1', AIL_QUIET_FALLBACK='1')
    env.pop('AIL_NO_GENERAL', None)
    if general:
        env['AIL_UNIFIED_FORCE'] = '1'
    else:
        env.pop('AIL_UNIFIED_FORCE', None)
    built = subprocess.run([sys.executable, '-B', str(ROOT / 'ail_chatgpt.py'), 'compile', src.name,
                            '--syntax', 'python', '-o', exe.name], cwd=directory,
                           capture_output=True, text=True, timeout=900, env=env)
    if built.returncode != 0:
        return None, (built.stdout + built.stderr)[-3000:]
    got = subprocess.run([str(exe)], capture_output=True, timeout=120, cwd=directory)
    return (got.stdout.replace(b'\r\n', b'\n'), got.returncode), got.stderr.decode('utf-8', 'replace')[-1500:]


class Fuzz34Tests(unittest.TestCase):
    def check(self, slug, text):
        with tempfile.TemporaryDirectory(prefix='ail-fuzz34-') as directory:
            want, rc = _cpython(directory, slug, text)
            for general in (True, False):
                got, err = _build_and_run(directory, '%s_%s' % (slug, 'g' if general else 'd'), text, general)
                self.assertIsNotNone(got, '%s (general=%s)\n%s' % (text[:2000], general, err))
                self.assertEqual(got, (want, rc), '%s (general=%s)\n%s' % (text[:2000], general, err))

    def test_generator_expression_is_lazy(self):
        self.check('genexp_lazy', LAZY)

    def test_local_rebound_after_generator_expression(self):
        self.check('genexp_late', LATE_LOCAL)

    def test_generator_expression_exhaustion(self):
        self.check('genexp_exhaust', EXHAUST)


if __name__ == '__main__':
    unittest.main()

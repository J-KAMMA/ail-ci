"""Branch cov3: a generator expression nested in another generator expression, compared with CPython 3.12.

The general path used to refuse every nested generator.  The inner generator is materialised
eagerly, which is observationally the same point in the program when its immediate consumer reads
every element: `sum(inner)`, `" ".join(inner)`, the list constructors, `sorted`, `min`/`max`,
`bytes` and `dict` (a plain name that is not bound anywhere in the module, as the single
positional argument and with no keywords), and `str.join` on a string literal or f-string.  The
enclosing generator must be consumed by the *same* kind of call: the eager lowering computes it in
full where it is written, so a for-loop source, a tuple unpacking, an assignment or a call that
evaluates another argument first (`sum(outer, start)`) would run side effects CPython defers or
runs in a different order.  Any other nesting keeps the named refusal (a user callee, a nested
generator used as an iterable, a local binding that hides the builtin, a variable `.join` receiver,
a second argument such as `sum(inner, start)`, `next()`), because materialising it early would run
(or skip) side effects CPython only runs at iteration time.

PROGRAMS are compiled with AIL_UNIFIED_FORCE=1 (the general path) and with the default build (which
falls back to it), and must print what CPython prints.
"""
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent
CHATGPT = str(ROOT / 'ail_chatgpt.py')
MESSAGE = 'a generator expression nested inside another generator expression'

MATCHING = {
    'join': r'''
rows = [["a", "bb"], ["ccc"], ["d", "e", "f"]]
print("\n".join(" ".join(x for x in row) for row in rows))
print(repr("|".join(",".join(str(x) for x in row) for row in [[], [1], [2, 3]])))
print("".join("".join(c for c in w) for w in ["ab", "", "c"]))
''',
    'sum_width': r'''
data = [[1, 2, 3], [10], [], [-4, 5]]
print("".join(f"{sum(v for v in row):>5}" for row in data))
print("|".join(f"{min(v for v in row)}:{max(v for v in row)}" for row in data if row))
print(sum(sum(v for v in row) for row in data))
''',
    'routes': r'''
def render(rows):
    return "\n".join(" ".join(str(v) for v in row) for row in rows)

class Holder:
    def __init__(self):
        self.rows = [[7, 8], [9]]

base = [[1, 2], [3]]
alias = base
h = Holder()
d = {"k": [[4, 5], [6]]}
print(render(alias))
print(render(h.rows))
print(render(d["k"]))
pairs = [[[1], [2]], [[3]]]
print("|".join(",".join(str(x) for x in pair[0]) for pair in pairs))
''',
    'consumers': r'''
rows = [[3, 1, 2], [5], [4, 4]]
print(";".join(str(sum(x for x in r)) for r in rows))
print(";".join(str(min(x for x in r)) for r in rows))
print(";".join(str(max(x for x in r)) for r in rows))
print(";".join(str(sorted(x for x in r)) for r in rows))
print(";".join(str(tuple(x for x in r)) for r in rows))
print(";".join(str(list(x for x in r)) for r in rows))
print(";".join(str(sorted(set(x for x in r))) for r in rows))
print(";".join(str(sorted(dict((x, x) for x in r).items())) for r in rows))
print(";".join(str(bytes(x for x in r)) for r in rows))
''',
    'order': r'''
log = []
def tag(x):
    log.append(x)
    return x
rows = [[1, 2], [3]]
out = "|".join(" ".join(str(tag(v)) for v in tag(row)) for row in rows)
print(out)
print(log)
''',
    'fstring_receiver': r'''
rows = [["a", "b"], ["c"]]
sep = "-"
print(f"{sep}".join("".join(ch for ch in w) for w in rows[0]))
print("\n".join(f"{str(len(row))}".join(str(v) for v in row) for row in rows))
''',
    'conditions': r'''
rows = [[1, 2], [3]]
print("|".join(str(sum(v for v in row) if len(row) > 1 else -1) for row in rows))
print("|".join(str(sum(v for v in row)) for row in rows if sum(w for w in row) > 1))
print("|".join(str(sum(v for v in row)) for row in rows for _ in range(2)))
''',
    'outer_consumers': r'''
rows = [[3, 1, 2], [5], [], [-4, 5]]
print(list(sum(x for x in r) for r in rows))
print(tuple(sum(x for x in r) for r in rows))
print(sorted(sum(x for x in r) for r in rows))
print(sum(sum(x for x in r) for r in rows))
print(min(sum(x for x in r) for r in rows))
print(max(sum(x for x in r) for r in rows))
print(sorted(dict((i, sum(x for x in r)) for i, r in enumerate(rows)).items()))
state = []
print(list(sum(state.append(w) or w for w in row) for row in rows[1:3]))
print(state)
''',
    'deep_nesting': r'''
rows = [[1, 2], [3], []]
print(list(list(x for x in r) for r in rows))
print(list(tuple(sum(y for y in row) for row in group) for group in [[[1, 2]], [[3], []]]))
print(sum(sum(sum(z for z in pair) for pair in group) for group in [[[-1, -2]], [[]]]))
''',
}

REFUSED = {
    'custom_callee': r'''
def take(it):
    return sum(it)
rows = [[1, 2], [3]]
print("|".join(str(take(v for v in row)) for row in rows))
''',
    'nested_iterable': r'''
rows = [[1, 2], [3]]
print("|".join(str(x) for x in (y for row in rows for y in row)))
''',
    'shadowed_sum': r'''
def take(it):
    return sum(it)
def f(sum, rows):
    return "|".join(str(sum(v for v in row)) for row in rows)
print(f(take, [[1, 2], [3]]))
''',
    'variable_sep': r'''
sep = "-"
rows = [["a", "b"], ["c"]]
print("|".join(sep.join(x for x in row) for row in rows))
''',
    'callable_variable': r'''
def consume(it):
    return list(it)
rows = [[1, 2], [3]]
f = consume
print("|".join(str(f(v for v in row)) for row in rows))
''',
    'next_inner': r'''
rows = [[1, 2], [3]]
print(next(sum(v for v in row) for row in rows))
''',
    'extra_argument': r'''
rows = [[1, 2], [3]]
print("|".join(str(sum((v for v in row), start=0)) for row in rows))
''',
    'outer_for_break': r'''
state = []
rows = [[1], [2], [3]]
for v in (sum(state.append(w) or w for w in row) for row in rows):
    break
print(state)
''',
    'outer_extra_argument': r'''
def tag(x, name):
    print(name, x)
    return x
rows = [[1, 2], [3]]
print(sum((sum(tag(v, "in") for v in row) for row in rows), tag(100, "start")))
''',
    'outer_assignment': r'''
rows = [[1], [2]]
g = (sum(x for x in r) for r in rows)
print(next(g))
''',
    'outer_unpacking': r'''
rows = [[1], [2]]
a, b = (sum(x for x in r) for r in rows)
print(a, b)
''',
}


def cpython(directory, name, text):
    src = Path(directory) / (name + '_cpython.py')
    src.write_text(text, encoding='utf-8')
    return subprocess.run([sys.executable, '-B', str(src)], capture_output=True, timeout=120,
                          env=dict(os.environ, PYTHONUTF8='1', PYTHONWARNINGS='ignore'))


def build(directory, name, text, general):
    src = Path(directory) / (name + '.py')
    src.write_text(text, encoding='utf-8')
    exe = Path(directory) / ('exe_' + name + ('_g' if general else '_d'))
    env = dict(os.environ, AIL_NO_CACHE='1', AIL_QUIET_FALLBACK='1')
    env.pop('AIL_NO_GENERAL', None)
    if general:
        env['AIL_UNIFIED_FORCE'] = '1'
    else:
        env.pop('AIL_UNIFIED_FORCE', None)
    return exe, subprocess.run([sys.executable, '-B', CHATGPT, 'compile', src.name,
                                '--syntax', 'python', '-o', exe.name], cwd=directory,
                               capture_output=True, text=True, timeout=900, env=env)


class Cov3Tests(unittest.TestCase):
    def test_nested_genexp_matches_cpython(self):
        with tempfile.TemporaryDirectory(prefix='ail-cov3-') as directory:
            for slug, text in MATCHING.items():
                want = cpython(directory, slug, text)
                for general in (True, False):
                    exe, built = build(directory, '%s_%s' % (slug, 'g' if general else 'd'), text, general)
                    self.assertEqual(built.returncode, 0, (slug, general, built.stdout + built.stderr))
                    got = subprocess.run([str(exe)], capture_output=True, timeout=120, cwd=directory)
                    self.assertEqual(got.stdout.replace(b'\r\n', b'\n'), want.stdout,
                                     (slug, general, got.stderr[-800:]))
                    self.assertEqual(got.returncode, want.returncode,
                                     (slug, general, got.stderr[-800:]))

    def test_unsafe_nesting_is_refused_by_name(self):
        with tempfile.TemporaryDirectory(prefix='ail-cov3-') as directory:
            for slug, text in REFUSED.items():
                for general in (True, False):
                    _, built = build(directory, '%s_%s' % (slug, 'g' if general else 'd'), text, general)
                    output = built.stdout + built.stderr
                    self.assertNotEqual(built.returncode, 0, (slug, general, output[-1200:]))
                    self.assertIn(MESSAGE, output, (slug, general, output[-1200:]))


if __name__ == '__main__':
    unittest.main()

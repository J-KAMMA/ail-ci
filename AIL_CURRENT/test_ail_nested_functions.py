"""Nested functions (python/pkg-v12/nestfn.py and the lifting in pyfunc.py), against CPython 3.12.

A nested `def` that rebinds a captured name with `nonlocal`, changes a captured container, calls a sibling
nested function, is cached with functools.cache / lru_cache, or is handed over as `key=` / to map / filter,
is lifted to the module level with an environment object shared by the enclosing function and its nested
functions; one that only reads what it captures is lifted with the captured values as leading arguments.

N1  fixed programs: the typed path alone (AIL_NO_GENERAL=1), with AIL_IR=0 and AIL_IR=1, prints what
    CPython prints, and so does the general path (pyc.py --general-only on the same surface text)
N2  shapes the typed path refuses by name (an environment field whose type cannot be told, a container
    kind a class field cannot hold) are still built by the default build (general path) with CPython's output
N3  random programs (`gen_program`): counters rebound with nonlocal, lists and dicts changed in place, sibling
    calls, self recursion with a decreasing argument, a cached helper, late binding of a name the enclosing
    function rebinds between calls: CPython == typed path (IR 0 and 1) == general path
N4  the rewrite keeps every original line at its number, and leaves a program without such a nested
    function byte for byte as written
N5  functions as values on the general path (boxclosure.py): returned and stored closures, lambdas with
    defaults, late binding over a loop variable, calls through a value and CPython's arity TypeError
N6  ASan + UBSan on the C of the environments (typed path, with LeakSanitizer) and of the closures under
    collections (general path); AIL_SKIP_SANITIZERS=1 skips it
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
PYC = ROOT / 'python' / 'pkg-v12' / 'pyc.py'
HAVE_CC = shutil.which('gcc') is not None
SEEDS = int(os.environ.get('AIL_NESTED_SEEDS', '12'))
sys.path.insert(0, str(ROOT))


def surface(text):
    import ail_syntax
    return ail_syntax.fold_constants(ail_syntax.python_surface(text))


def build(directory, text, name, ir='0', typed_only=True):
    source, exe = Path(directory, name + '.py'), Path(directory, name + ('_t' if typed_only else '_d') + ir)
    source.write_text(text, encoding='utf-8')
    env = dict(os.environ, AIL_NO_CACHE='1', AIL_IR=ir)
    if typed_only:
        env['AIL_NO_GENERAL'] = '1'
    else:
        env.pop('AIL_NO_GENERAL', None)
    res = subprocess.run([sys.executable, '-B', str(ROOT / 'ail_chatgpt.py'), 'compile', source.name, '--syntax',
                          'python', '-o', exe.name], cwd=directory, capture_output=True, text=True, timeout=900,
                         env=env)
    return res, exe


def build_general(directory, text, name):
    source, exe = Path(directory, name + '_g.ail'), Path(directory, name + '_g')
    source.write_text(surface(text), encoding='utf-8')
    env = dict(os.environ, AIL_IR='0', AIL_NO_CACHE='1', AIL_SURFACE='python')
    env.pop('AIL_NO_GENERAL', None)
    res = subprocess.run([sys.executable, '-B', str(PYC), exe.name, '--file', source.name, '--general-only'],
                         cwd=directory, capture_output=True, text=True, timeout=900, env=env)
    return res, exe


def run_cpython(directory, text, name, stdin=''):
    source = Path(directory, name + '_cpython.py')
    source.write_text(text, encoding='utf-8')
    return subprocess.run([sys.executable, str(source)], capture_output=True, text=True, timeout=300,
                          encoding='utf-8', input=stdin)


def run_exe(exe, stdin=''):
    return subprocess.run([str(exe)], capture_output=True, text=True, timeout=300, encoding='utf-8', input=stdin)


DFS = '''import sys


def main() -> None:
    n = 9
    adj: list[list[int]] = [[] for _ in range(n)]
    ea = [0, 1, 2, 3, 4, 6, 7, 8, 2]
    eb = [1, 2, 0, 4, 5, 7, 8, 6, 3]
    for i in range(len(ea)):
        adj[ea[i]].append(eb[i])
        adj[eb[i]].append(ea[i])
    seen = [False] * n
    order: list[int] = []
    count = 0
    depth_max = 0

    def dfs(u: int, depth: int) -> None:
        nonlocal count, depth_max
        seen[u] = True
        order.append(u)
        count += 1
        if depth > depth_max:
            depth_max = depth
        for v in adj[u]:
            if not seen[v]:
                dfs(v, depth + 1)

    comps = 0
    for s in range(n):
        if not seen[s]:
            comps += 1
            dfs(s, 0)
    print(comps, count, depth_max)
    for u in order:
        print(u)


main()
'''

BEST = '''def solve(items: list[int], cap: int) -> int:
    best = 0
    picked = [0] * len(items)
    calls = 0

    def go(i: int, used: int, value: int) -> None:
        nonlocal best, calls
        calls += 1
        if used > cap:
            return
        if value > best:
            best = value
        if i == len(items):
            return
        picked[i] = 1
        go(i + 1, used + items[i], value + items[i] * 3 - i)
        picked[i] = 0
        go(i + 1, used, value)

    go(0, 0, 0)
    print("calls", calls)
    return best


def main() -> None:
    print(solve([5, 3, 8, 2, 7, 4], 15))
    print(solve([1, 1, 1], 2))
    print(solve([], 3))


main()
'''

SIBLINGS = '''def main() -> None:
    log: list[int] = []
    total = 0

    def even(n: int) -> bool:
        log.append(n)
        if n == 0:
            return True
        return odd(n - 1)

    def odd(n: int) -> bool:
        nonlocal total
        total += n
        if n == 0:
            return False
        return even(n - 1)

    def both(n: int) -> int:
        return (1 if even(n) else 0) + (2 if odd(n) else 0)

    for k in range(6):
        print(k, both(k), total)
    print(len(log), log[-1])


main()
'''

CACHED = '''from functools import lru_cache, cache


def count_paths(grid: list[str]) -> int:
    h = len(grid)
    w = len(grid[0])
    calls = [0]

    @lru_cache(maxsize=None)
    def ways(r: int, c: int) -> int:
        calls[0] += 1
        if r >= h or c >= w or grid[r][c] == "#":
            return 0
        if r == h - 1 and c == w - 1:
            return 1
        return ways(r + 1, c) + ways(r, c + 1)

    result = ways(0, 0)
    print("calls", calls[0])
    return result


def fib_all(n: int) -> list[int]:
    @cache
    def fib(k: int) -> int:
        return k if k < 2 else fib(k - 1) + fib(k - 2)

    return [fib(i) for i in range(n)]


def words(text: str) -> int:
    @lru_cache(maxsize=None)
    def score(word: str) -> int:
        return sum(ord(ch) for ch in word) % 97

    total = 0
    for w in text.split():
        total += score(w)
    return total


def main() -> None:
    print(count_paths(["....", ".#..", "...#", "#..."]))
    print(count_paths(["..", ".."]))
    print(fib_all(40)[-1], len(fib_all(10)))
    print(words("a bb a ccc bb a"))


main()
'''

CALLBACKS = '''def main() -> None:
    weights: dict[str, int] = {"a": 3, "b": 1, "c": 2, "d": 3}
    names: list[str] = ["d", "a", "c", "b"]
    bias = 0
    seen: list[str] = []

    def weight(k: str) -> int:
        seen.append(k)
        return weights[k] * 10 + bias

    def neg(x: int) -> int:
        return -x - bias

    keys = sorted(names, key=weight)
    for k in keys:
        print(k)
    bias = 5
    xs = [4, 1, 3, 9]
    xs.sort(key=neg)
    for x in xs:
        print(x)
    print(len(seen))


main()
'''

LATE = '''def main() -> None:
    k = 1
    out: list[int] = []

    def add(x: int) -> None:
        out.append(x * k)

    add(5)
    k = 10
    add(5)
    k = k + 1
    for i in range(3):
        add(i)
    print(*out)

    step = 2
    acc = 0

    def bump() -> int:
        nonlocal acc
        acc += step
        return acc

    print(bump(), bump())
    step = 7
    acc = acc * 100
    print(bump(), acc)


main()
'''

LATE_BOUND = '''def main() -> None:
    head = [-1] * 5
    to: list[int] = []
    nxt: list[int] = []

    def add_edge(u: int, v: int) -> None:
        to.append(v)
        nxt.append(head[u])
        head[u] = len(to) - 1

    for i in range(5):
        add_edge(i, (i + 1) % 5)
        add_edge((i + 1) % 5, i)
    timer = 0
    disc = [0] * 5

    def visit(u: int) -> None:
        nonlocal timer
        timer += 1
        disc[u] = timer
        e = head[u]
        while e != -1:
            if disc[to[e]] == 0:
                visit(to[e])
            e = nxt[e]

    visit(0)
    print(*disc)
    print(timer, len(to))


main()
'''

METHOD = '''class Board:
    def __init__(self, cells: list[int]) -> None:
        self.cells = cells
        self.moves = 0

    def flood(self, start: int) -> int:
        filled = [False] * len(self.cells)
        size = 0

        def fill(i: int) -> None:
            nonlocal size
            if i < 0 or i >= len(self.cells) or filled[i] or self.cells[i] != self.cells[start]:
                return
            filled[i] = True
            size += 1
            self.moves += 1
            fill(i - 1)
            fill(i + 1)

        fill(start)
        return size


def main() -> None:
    b = Board([1, 1, 2, 2, 2, 1, 1, 1, 3])
    print(b.flood(3), b.flood(6), b.flood(0), b.moves)


main()
'''

GRID = '''def main() -> None:
    rows = ["#.##..", "#..#.#", "##....", "..##.#"]
    h, w = len(rows), len(rows[0])
    mark: list[list[int]] = [[0] * w for _ in range(h)]
    label = 0

    def paint(r: int, c: int) -> int:
        if r < 0 or r >= h or c < 0 or c >= w or rows[r][c] != "." or mark[r][c] != 0:
            return 0
        mark[r][c] = label
        return 1 + paint(r + 1, c) + paint(r - 1, c) + paint(r, c + 1) + paint(r, c - 1)

    sizes: list[int] = []
    for r in range(h):
        for c in range(w):
            if rows[r][c] == "." and mark[r][c] == 0:
                label += 1
                sizes.append(paint(r, c))
    print(label, *sizes)
    for r in range(h):
        print(*mark[r])


main()
'''

READONLY = '''def main() -> None:
    table = [3, 1, 4, 1, 5, 9, 2, 6]
    names = ["x", "y", "z"]

    def at(i: int) -> int:
        return table[i % len(table)] * len(names)

    total = 0
    for i in range(20):
        total += at(i)
    print(total, at(3))


main()
'''

FIXED = {'dfs': DFS, 'best': BEST, 'siblings': SIBLINGS, 'cached': CACHED, 'callbacks': CALLBACKS,
         'late': LATE, 'late_bound': LATE_BOUND, 'method': METHOD, 'grid': GRID, 'readonly': READONLY}

# the typed path refuses these by name (a field type the rewrite cannot tell, a set inside a list as a
# class field); the default build takes them on the general path
GENERAL_ONLY = {
    'unknown_field': '''def main() -> None:
    data = make()
    hits = 0

    def probe(i: int) -> None:
        nonlocal hits
        if data[i] > 2:
            hits += 1
            data[i] = 0

    for i in range(len(data)):
        probe(i)
    print(hits, data)


def make():
    return [1, 5, 3, 0, 7]


main()
''',
    'set_rows': '''def main() -> None:
    adj: list[set[int]] = [set() for _ in range(5)]
    for a, b in [(0, 1), (1, 2), (3, 4)]:
        adj[a].add(b)
        adj[b].add(a)
    comp = [-1] * 5

    def mark(u: int, c: int) -> None:
        comp[u] = c
        for v in sorted(adj[u]):
            if comp[v] == -1:
                mark(v, c)

    c = 0
    for u in range(5):
        if comp[u] == -1:
            mark(u, c)
            c += 1
    print(c, comp)


main()
''',
}


@unittest.skipUnless(HAVE_CC, 'needs gcc')
class Fixed(unittest.TestCase):
    def test_typed_and_general_paths_print_what_cpython_prints(self):
        with tempfile.TemporaryDirectory(prefix='ail-nested-') as tmp:
            for name, text in FIXED.items():
                with self.subTest(name=name):
                    want = run_cpython(tmp, text, name)
                    self.assertEqual(want.returncode, 0, want.stderr)
                    for ir in ('0', '1'):
                        res, exe = build(tmp, text, name, ir=ir)
                        self.assertEqual(res.returncode, 0, '%s IR=%s: %s' % (name, ir, res.stderr[-2000:]))
                        got = run_exe(exe)
                        self.assertEqual((got.returncode, got.stdout), (0, want.stdout), '%s IR=%s' % (name, ir))
                    res, exe = build_general(tmp, text, name)
                    self.assertEqual(res.returncode, 0, '%s general: %s' % (name, res.stderr[-2000:]))
                    got = run_exe(exe)
                    self.assertEqual((got.returncode, got.stdout), (0, want.stdout), '%s general' % name)

    def test_shapes_the_typed_path_refuses_are_built_on_the_general_path(self):
        with tempfile.TemporaryDirectory(prefix='ail-nested-') as tmp:
            for name, text in GENERAL_ONLY.items():
                with self.subTest(name=name):
                    want = run_cpython(tmp, text, name)
                    res, exe = build(tmp, text, name)
                    self.assertEqual(res.returncode, 3, res.stderr)
                    self.assertIn('not in the subset', res.stderr)
                    res, exe = build(tmp, text, name, typed_only=False)
                    self.assertEqual(res.returncode, 0, res.stderr[-2000:])
                    self.assertIn('general path', res.stderr)
                    got = run_exe(exe)
                    self.assertEqual((got.returncode, got.stdout), (want.returncode, want.stdout), name)

    def test_an_untold_field_type_is_refused_by_the_shared_name(self):
        with tempfile.TemporaryDirectory(prefix='ail-nested-') as tmp:
            res, _ = build(tmp, GENERAL_ONLY['unknown_field'], 'unknown_field')
            self.assertIn("the type of 'data'", res.stderr)
            self.assertIn("'probe'", res.stderr)


def gen_program(seed):
    """A random enclosing function with shared counters, a list, a dict and 2-4 nested functions."""
    rng = random.Random(seed)
    n_fn = rng.randint(2, 4)
    lines = ['from functools import lru_cache', '', '', 'def run(n: int) -> None:',
             '    c0 = 0', '    c1 = %d' % rng.randint(-3, 3), '    xs: list[int] = []',
             '    d: dict[int, int] = {}', '    k = %d' % rng.randint(1, 4), '']
    for i in range(n_fn):
        cached = i == 0 and rng.random() < 0.4
        if cached:
            lines.append('    @lru_cache(maxsize=None)')
            lines.append('    def f%d(a: int) -> int:' % i)
            lines.append('        if a <= 1:')
            lines.append('            return a + k')
            lines.append('        return f%d(a - 1) + f%d(a - 2) %% 1000' % (i, i))
            lines.append('')
            continue
        lines.append('    def f%d(a: int) -> int:' % i)
        lines.append('        nonlocal c0, c1')
        body = []
        recursed = False
        for _ in range(rng.randint(2, 5)):
            r = rng.random()
            if r < 0.2:
                body.append('c0 += a %% %d' % rng.randint(2, 7))
            elif r < 0.35:
                body.append('c1 = c1 * 2 - a if c1 < 1000 else c1 // 3')
            elif r < 0.5:
                body.append('xs.append(a * k + c0)')
            elif r < 0.6:
                body.append('d[a % 5] = d.get(a % 5, 0) + c1')
            elif r < 0.7:
                body.append('if xs:\n            xs[len(xs) // 2] += 1')
            elif r < 0.85 and i > 0:
                j = rng.randrange(i)
                body.append('c0 += f%d(a %% 7)' % j)
            elif not recursed:
                recursed = True
                body.append('if a > 0:\n            c1 += f%d(a - 1) %% 50' % i)
            else:
                body.append('c0 -= 1')
        for b in body:
            lines.append('        ' + b)
        lines.append('        return c0 + c1 + len(xs)')
        lines.append('')
    lines.append('    for i in range(n):')
    for _ in range(rng.randint(2, 4)):
        r = rng.random()
        j = rng.randrange(n_fn)
        if r < 0.5:
            lines.append('        print(f%d(i %% 9), c0, c1)' % j)
        elif r < 0.7:
            lines.append('        k = k + 1 if k < 9 else 1')
        elif r < 0.85:
            lines.append('        c0 = c0 % 101')
        else:
            lines.append('        xs.append(f%d(i %% 5))' % j)
    lines.append('    print(c0, c1, k, len(xs), sum(xs) % 100003)')
    lines.append('    for key in sorted(d):')
    lines.append('        print(key, d[key])')
    lines.append('')
    lines.append('')
    lines.append('run(%d)' % rng.randint(3, 9))
    return '\n'.join(lines) + '\n'


@unittest.skipUnless(HAVE_CC, 'needs gcc')
class Random(unittest.TestCase):
    def test_random_programs_agree_with_cpython(self):
        with tempfile.TemporaryDirectory(prefix='ail-nested-rand-') as tmp:
            for seed in range(SEEDS):
                text = gen_program(seed)
                name = 'r%d' % seed
                with self.subTest(seed=seed):
                    want = run_cpython(tmp, text, name)
                    self.assertEqual(want.returncode, 0, want.stderr + text)
                    for ir in ('0', '1'):
                        res, exe = build(tmp, text, name, ir=ir)
                        self.assertEqual(res.returncode, 0, 'seed %d IR=%s: %s\n%s' % (seed, ir, res.stderr[-1500:], text))
                        got = run_exe(exe)
                        self.assertEqual(got.stdout, want.stdout, 'seed %d IR=%s\n%s' % (seed, ir, text))
                    res, exe = build_general(tmp, text, name)
                    self.assertEqual(res.returncode, 0, 'seed %d general: %s' % (seed, res.stderr[-1500:]))
                    got = run_exe(exe)
                    self.assertEqual(got.stdout, want.stdout, 'seed %d general\n%s' % (seed, text))


# functions as values on the general path (boxclosure.py): returned and stored closures with cells,
# lambdas with defaults, late binding, calls through a value, CPython's arity TypeError
CLOSURES = 'def make_counter(start):\n    count = start\n\n    def inc() -> int:\n        nonlocal count\n        count += 1\n        return count\n\n    return inc\n\n\ndef make_adders():\n    fs = []\n    for i in range(3):\n        fs.append(lambda x: x + i)\n    return fs\n\n\ndef compose(f, g):\n    return lambda x: f(g(x))\n\n\ndef twice(x):\n    return 2 * x\n\n\ndef apply_all(funcs, v):\n    out = []\n    for fn in funcs:\n        out.append(fn(v))\n    return out\n\n\ndef outer():\n    log = []\n\n    def note(msg, times=1):\n        for _ in range(times):\n            log.append(msg)\n        return len(log)\n\n    cb = note\n    cb("a")\n    cb("b", 2)\n    return log\n\n\ndef main() -> None:\n    c = make_counter(10)\n    d = make_counter(0)\n    print(c(), c(), d(), c())\n    adders = make_adders()\n    print([f(10) for f in adders])\n    late = [lambda: i for i in range(3)]\n    bound = [lambda i=i: i for i in range(3)]\n    print([f() for f in late], [f() for f in bound])\n    h = compose(twice, lambda y: y + 1)\n    print(h(5), compose(h, h)(1))\n    ops = {"+": lambda a, b: a + b, "*": lambda a, b: a * b}\n    print(ops["+"](3, 4), ops["*"](3, 4))\n    print(apply_all([twice, abs_neg, lambda z: z * z], -3))\n    print(outer())\n    counters = {}\n    for w in "a b a c a b".split():\n        if w not in counters:\n            counters[w] = make_counter(0)\n        counters[w]()\n    for w in sorted(counters):\n        print(w, counters[w]() - 1)\n    try:\n        c(1)\n    except TypeError as e:\n        print("TypeError", e)\n\n\ndef abs_neg(v):\n    return -abs(v)\n\n\nmain()\n'


@unittest.skipUnless(HAVE_CC, 'needs gcc')
class Closures(unittest.TestCase):
    def test_function_values_on_the_general_path(self):
        with tempfile.TemporaryDirectory(prefix='ail-closure-') as tmp:
            want = run_cpython(tmp, CLOSURES, 'closures')
            self.assertEqual(want.returncode, 0, want.stderr)
            for ir in ('0', '1'):
                res, exe = build(tmp, CLOSURES, 'closures', ir=ir, typed_only=False)
                self.assertEqual(res.returncode, 0, res.stderr[-2000:])
                self.assertIn('general path', res.stderr)
                got = run_exe(exe)
                self.assertEqual((got.returncode, got.stdout), (0, want.stdout), 'IR=%s' % ir)
            res, exe = build_general(tmp, CLOSURES, 'closures')
            self.assertEqual(res.returncode, 0, res.stderr[-2000:])
            got = run_exe(exe)
            self.assertEqual((got.returncode, got.stdout), (0, want.stdout))

    def test_a_closure_over_a_loop_variable_sees_its_last_value(self):
        text = ('def main() -> None:\n    fs = []\n    for i in range(4):\n        def g(k):\n'
                '            return k * 10 + i\n        fs.append(g)\n    i = 7\n'
                '    print([f(1) for f in fs])\n    total = 0\n\n    def bump(n=2):\n        nonlocal total\n'
                '        total += n\n        return total\n\n    step = bump\n    step()\n    step(5)\n'
                '    print(total, step())\n\n\nmain()\n')
        with tempfile.TemporaryDirectory(prefix='ail-closure-') as tmp:
            want = run_cpython(tmp, text, 'loopvar')
            res, exe = build(tmp, text, 'loopvar', typed_only=False)
            self.assertEqual(res.returncode, 0, res.stderr[-2000:])
            got = run_exe(exe)
            self.assertEqual(got.stdout, want.stdout)


# many closures, cells and default values alive across collections (general path)
GC_STRESS = 'def make(k):\n    acc = [k]\n    count = 0\n\n    def step(x, y=1):\n        nonlocal count\n        count += y\n        acc.append(x * k + count)\n        return len(acc)\n\n    return step\n\n\ndef chain(n):\n    fs = []\n    for i in range(n):\n        fs.append(lambda v, i=i: v + i)\n    total = 0\n    for f in fs:\n        total = f(total) % 1000003\n    return total\n\n\ndef main():\n    steps = [make(k) for k in range(2000)]\n    s = 0\n    for r in range(30):\n        for st in steps:\n            s += st(r, r % 3 + 1)\n        tmp = [str(x) * 3 for x in range(500)]\n        s += len(tmp)\n    print(s)\n    print(chain(20000))\n    nested = []\n    for i in range(3000):\n        def g(z, i=i):\n            return lambda w: w * z + i\n        nested.append(g(i % 7))\n    print(sum(h(2) for h in nested))\n\n\nmain()\n'

SAN_FLAGS = ['-O1', '-g', '-fsanitize=address,undefined', '-fno-sanitize-recover=undefined', '-fno-omit-frame-pointer',
             '-fno-strict-aliasing', '-w']


@unittest.skipUnless(HAVE_CC and os.environ.get('AIL_SKIP_SANITIZERS') != '1', 'needs gcc')
class Sanitized(unittest.TestCase):
    """The C of the shared environments (typed path, with LeakSanitizer) and of the closures (general path)
    under ASan + UBSan."""

    def run_sanitized(self, tmp, text, name, typed, leaks):
        src = Path(tmp, name + '.py')
        src.write_text(text, encoding='utf-8')
        env = dict(os.environ, AIL_NO_CACHE='1', AIL_IR='0')
        if typed:
            env['AIL_NO_GENERAL'] = '1'
        debug = Path(tmp, name + '.d')
        res = subprocess.run([sys.executable, '-B', str(ROOT / 'ail_chatgpt.py'), 'compile', src.name, '--syntax', 'python',
                              '-o', name + '_x', '--debug-dir', debug.name], cwd=tmp, capture_output=True, text=True,
                             timeout=900, env=env)
        self.assertEqual(res.returncode, 0, res.stderr[-2000:])
        c_path = next(debug.glob('*.c'))
        san = Path(tmp, name + '_san')
        cc = subprocess.run(['gcc', *SAN_FLAGS, str(c_path), '-lm', '-o', str(san)], capture_output=True, text=True)
        self.assertEqual(cc.returncode, 0, cc.stderr[-2000:])
        run_env = dict(os.environ, ASAN_OPTIONS='detect_leaks=%d' % leaks,
                       UBSAN_OPTIONS='print_stacktrace=1:halt_on_error=1')
        got = subprocess.run([str(san)], capture_output=True, text=True, timeout=600, env=run_env)
        want = run_cpython(tmp, text, name)
        self.assertEqual((got.returncode, got.stdout), (want.returncode, want.stdout), got.stderr[-3000:])

    def test_environments_and_closures(self):
        with tempfile.TemporaryDirectory(prefix='ail-nested-san-') as tmp:
            for name in ('dfs', 'cached', 'late_bound', 'method', 'grid'):
                with self.subTest(name=name):
                    self.run_sanitized(tmp, FIXED[name], name, typed=True, leaks=1)
            self.run_sanitized(tmp, CLOSURES, 'closures', typed=False, leaks=0)
            self.run_sanitized(tmp, GC_STRESS, 'gcstress', typed=False, leaks=0)


class Rewrite(unittest.TestCase):
    def test_lines_keep_their_numbers(self):
        import ail_syntax
        nestfn = ail_syntax._nestfn()
        for name, text in FIXED.items():
            with self.subTest(name=name):
                out = nestfn.rewrite(text)
                self.assertNotEqual(out, text, name)
                # the statements outside the nested functions stay on their lines
                import ast
                new = {}
                for n in ast.walk(ast.parse(out)):
                    if isinstance(n, ast.stmt):
                        new.setdefault(n.lineno, set()).add(type(n).__name__)
                for n in ast.walk(ast.parse(text)):
                    if not isinstance(n, ast.stmt) or n.lineno not in new:
                        continue
                    if type(n).__name__ in ('FunctionDef', 'Nonlocal'):
                        continue
                    self.assertIn(type(n).__name__, new[n.lineno], '%s line %d' % (name, n.lineno))

    def test_a_program_without_such_a_nested_function_is_left_as_written(self):
        import ail_syntax
        nestfn = ail_syntax._nestfn()
        plain = 'def main() -> None:\n    def sq(x: int) -> int:\n        return x * x\n\n    print(sq(3))\n\n\nmain()\n'
        self.assertEqual(nestfn.rewrite(plain), plain)
        escaping = ('def make():\n    n = 0\n\n    def inc() -> int:\n        nonlocal n\n        n += 1\n'
                    '        return n\n\n    return inc\n')
        self.assertEqual(nestfn.rewrite(escaping), escaping)


if __name__ == '__main__':
    unittest.main()

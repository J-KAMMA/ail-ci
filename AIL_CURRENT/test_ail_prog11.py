"""Typed reach for eight real programs, and the two compiler blockers fixed for them.

Profiled under CPython 3.12, every one of the eight spends its own time in `main` (plus the
helpers named in `lab/progfix/prog11.md`).  The typed path already accepted t256, t058 and
g11_006.  Two more are now typed:

* g11_030 writes annotated tuple module constants (`START: tuple[int, int] = (0, 0)`); the
  annotation used to fall through to the ordinary statement path, so the value became a
  constructor call and the module-constant rule refused it.  `tuplib.py` now lowers the same
  literal shape exactly like the unannotated assignment.
* t404 calls `min(xs, key=lambda v: (abs(v - current), xs.index(v)))`.  `iterlower.py` already
  lowered a keyed min/max to one pass, but a tuple key became a tuple value, which the typed
  path does not compare.  The components are now compared lexicographically (each evaluated
  once per element, in order, as CPython calls the key), so the program builds typed.

The other three keep their recorded follow-ups: t310 needs `iter()` and a str pair in a
generator (`zip(s, t)`), g25_006 needs typed `Enum` methods (the generated `_AilIntEnum`
dunders), and t388 needs typed `datetime` (`date.fromisoformat`, `list[date]`).
"""
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parent
CLI = str(ROOT / 'ail_chatgpt.py')
HAVE_CC = shutil.which(os.environ.get('PIPE_CC') or 'gcc') is not None

PROGRAMS = (
    ('t256', 'lab/census/programs/dev/t256.py', 'lab/corpus/tasks/t256'),
    ('t310', 'lab/corpus/programs/deepseek-v4.1-flash-free/t310.py', 'lab/corpus/tasks/t310'),
    ('g11_030', 'lab/census/programs/gdev/g11_030.py', None),
    ('g25_006', 'lab/census/programs/gdev/g25_006.py', None),
    ('t058', 'lab/census/programs/dev/t058.py', 'lab/corpus/tasks/t058'),
    ('g11_006', 'lab/census/programs/gdev/g11_006.py', None),
    ('t404', 'lab/corpus/programs/deepseek-v4.1-flash-free/t404.py', 'lab/corpus/tasks/t404'),
    ('t388', 'lab/census/programs/dev/t388.py', 'lab/corpus/tasks/t388'),
)
NEWLY_TYPED = ('g11_030', 't404')

TUPLE_KEY = '''
class Box:
    def __init__(self, base: int) -> None:
        self.base = base


def pick_min(xs: list[int], cur: int) -> int:
    return min(xs, key=lambda v: (abs(v - cur), xs.index(v)))


def pick_max(xs: list[int]) -> int:
    return max(xs, key=lambda v: (abs(v), -v))


def one(xs: list[int]) -> int:
    return min(xs, key=lambda v: (v,))


def three(xs: list[int]) -> int:
    return max(xs, key=lambda v: (abs(v), v % 3, -v))


def from_attr(xs: list[int], b: Box) -> int:
    return min(xs, key=lambda v: (abs(v - b.base), v))


def from_dict(xs: list[int], d: dict[str, int]) -> int:
    return min(xs, key=lambda v: (abs(v - d["base"]), v))


def from_item(xs: list[int], bounds: list[int]) -> int:
    return min(xs, key=lambda v: (abs(v - bounds[0]), v))


def main() -> None:
    xs = [5, -3, 8, -1, 8, -3]
    print(pick_min(xs, 2), pick_max(xs), one(xs), three(xs))
    print(pick_min(list(xs), -1), pick_min(xs, 2))
    print(from_attr(xs, Box(4)))
    d: dict[str, int] = {"base": 7}
    print(from_dict(xs, d))
    print(from_item(xs, [0, 99]))
    empty: list[int] = []
    print(min(empty, key=lambda v: (v,), default=42))
    print(max(empty, key=lambda v: (v,), default=-7))
    try:
        print(min(empty, key=lambda v: (v,)))
    except Exception as e:
        print(type(e).__name__, e)
    print(min(xs, key=lambda v: abs(v)))
    print(max(xs, key=lambda v: v))
    zeros = [-0.0, 0.0]
    print(min(zeros, key=lambda v: (v,)))
    print(max(zeros, key=lambda v: (v,)))
    nan = float("nan")
    ys = [nan, 1.0, -1.0, 0.5]
    print(min(ys, key=lambda v: (v, 0)))
    print(max(ys, key=lambda v: (v, 0)))


main()
'''

MUTATING_KEY = '''
def main() -> None:
    xs = [5, 3, 1, 4, 2]
    print(min(xs, key=lambda v: (xs.pop(), v)))
    print(xs)
    ys = [5, 3, 1, 4, 2]
    print(max(ys, key=lambda v: (ys.pop(0), v)))
    print(ys)
main()
'''

FORWARD_TUPLE_CONSTANT = '''
def f() -> int:
    return X[0] + X[1]

X: tuple[int, int] = (4, 5)
print(f())
'''

TUPLE_CONSTANTS = '''
START: tuple[int, int] = (0, 0)
END: tuple[int, int] = (2, 2)
MOVES: tuple[tuple[int, int], ...] = ((1, 0), (-1, 0), (0, 1), (0, -1))
PAIRS: list[tuple[int, int]] = [(1, 2), (3, 4)]
FLOATS: tuple[float, float] = (1.5, -2.5)


def route(p: tuple[int, int]) -> int:
    return p[0] * 10 + p[1]


def span() -> int:
    return (END[0] - START[0]) + (END[1] - START[1])


def pair_sum() -> int:
    return PAIRS[0][0] + PAIRS[1][1]


def float_sum() -> float:
    return FLOATS[0] + FLOATS[1]


def move_count() -> int:
    return len(MOVES)


def main() -> None:
    print(route(START), route(END), span(), pair_sum(), float_sum(), move_count())
    d = {"p": PAIRS[0]}
    print(d["p"][0] + d["p"][1])
    print(MOVES[2][0] + MOVES[2][1])


main()
'''


REBIND_DELETE = {
    'rebind': '''
def f() -> int:
    return X[0]

X: tuple[int, int] = (4, 5)
X = 9
print(f())
''',
    'delete': '''
def f() -> int:
    return X[0]

X: tuple[int, int] = (4, 5)
del X
print(f())
''',
    'global_rebind': '''
def f() -> int:
    return X[0]

X: tuple[int, int] = (4, 5)

def g() -> None:
    global X
    X = 9

g()
print(f())
''',
    'global_delete': '''
def f() -> int:
    return X[0]

X: tuple[int, int] = (4, 5)

def g() -> None:
    global X
    del X

g()
print(f())
''',
}


WALRUS_REBIND = {
    'comprehension': '''
def f() -> int:
    return X[0]

X = (1, 2)
[X := 9 for _ in range(1)]
print(f())
''',
    'call': '''
def f() -> int:
    return X[0]

X = (1, 2)
print((X := 9))
print(f())
''',
    'assignment_value': '''
def f() -> int:
    return X[0]

X = (1, 2)
y = (X := 9)
print(f())
''',
    'global': '''
def f() -> int:
    return X[0]

X = (1, 2)

def g() -> None:
    global X
    (X := 9)

g()
print(f())
''',
}

LOCAL_WALRUS = '''
def f() -> int:
    return X[0]

X = (1, 2)

def g() -> int:
    X = 5
    (X := 9)
    return X

print(f(), g())
'''


def run(cmd, cwd=None, stdin=b'', env=None):
    return subprocess.run(cmd, cwd=cwd, input=stdin, capture_output=True, env=env, timeout=600)


@unittest.skipUnless(HAVE_CC, 'needs a C compiler')
class TypedReach11(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix='ail-prog11-')
        self.env = dict(os.environ, AIL_NO_CACHE='1')

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def build(self, src, name, strict=False):
        out = Path(self.tmp) / (name + ('.strict' if strict else ''))
        cmd = [sys.executable, '-B', CLI, 'compile']
        if strict:
            cmd.append('--strict')
        cmd += [str(src), '--syntax', 'python', '-o', str(out)]
        return run(cmd, Path(self.tmp), env=self.env), out

    def cases(self, task_dir):
        if task_dir is None:
            return [b'']
        base = REPO / task_dir
        return [(base / ('in%d.txt' % i)).read_bytes() for i in range(3)]

    def compare(self, src, exe, task_dir):
        for stdin in self.cases(task_dir):
            want = run([sys.executable, str(src)], Path(self.tmp), stdin=stdin)
            got = run([str(exe)], Path(self.tmp), stdin=stdin)
            self.assertEqual(got.returncode, want.returncode, stdin[:200])
            self.assertEqual(got.stdout, want.stdout, stdin[:200])

    def test_all_eight_match_cpython(self):
        for name, rel, task in PROGRAMS:
            src = REPO / rel
            built, exe = self.build(src, name)
            self.assertEqual(built.returncode, 0, built.stderr[-3000:])
            self.compare(src, exe, task)

    def test_newly_typed_build_strict(self):
        for name, rel, task in PROGRAMS:
            if name not in NEWLY_TYPED:
                continue
            src = REPO / rel
            built, exe = self.build(src, name, strict=True)
            self.assertEqual(built.returncode, 0, built.stderr[-3000:])
            self.compare(src, exe, task)

    def test_tuple_key_min_max(self):
        src = Path(self.tmp) / 'tuple_key.py'
        src.write_text(TUPLE_KEY, encoding='utf-8')
        built, exe = self.build(src, 'tuple_key', strict=True)
        self.assertEqual(built.returncode, 0, built.stderr[-3000:])
        self.compare(src, exe, None)

    def test_annotated_tuple_module_constants(self):
        src = Path(self.tmp) / 'tuple_constants.py'
        src.write_text(TUPLE_CONSTANTS, encoding='utf-8')
        built, exe = self.build(src, 'tuple_constants', strict=True)
        self.assertEqual(built.returncode, 0, built.stderr[-3000:])
        self.compare(src, exe, None)

    def test_tuple_key_with_mutation(self):
        src = Path(self.tmp) / 'mutating_key.py'
        src.write_text(MUTATING_KEY, encoding='utf-8')
        built, exe = self.build(src, 'mutating_key', strict=True)
        self.assertEqual(built.returncode, 0, built.stderr[-3000:])
        self.compare(src, exe, None)

    def test_forward_tuple_constant(self):
        src = Path(self.tmp) / 'forward_tuple.py'
        src.write_text(FORWARD_TUPLE_CONSTANT, encoding='utf-8')
        built, exe = self.build(src, 'forward_tuple', strict=True)
        self.assertEqual(built.returncode, 0, built.stderr[-3000:])
        self.compare(src, exe, None)


    def test_tuple_constant_rebind_or_delete_is_refused(self):
        for name, text in REBIND_DELETE.items():
            src = Path(self.tmp) / ('rebind_' + name + '.py')
            src.write_text(text, encoding='utf-8')
            built, exe = self.build(src, 'rebind_' + name)
            self.assertEqual(built.returncode, 0, built.stderr[-3000:])
            self.compare(src, exe, None)

    def test_walrus_rebind_is_refused_by_name(self):
        for name, text in WALRUS_REBIND.items():
            src = Path(self.tmp) / ('walrus_' + name + '.py')
            src.write_text(text, encoding='utf-8')
            built, exe = self.build(src, 'walrus_' + name)
            output = (built.stdout + built.stderr).decode('utf-8', 'replace')
            self.assertNotEqual(built.returncode, 0, name + ': ' + output[-3000:])
            self.assertIn('module-level tuple constant X', output, name)
            self.assertIn('assignment expression', output, name)

    def test_local_walrus_does_not_refuse(self):
        src = Path(self.tmp) / 'local_walrus.py'
        src.write_text(LOCAL_WALRUS, encoding='utf-8')
        built, exe = self.build(src, 'local_walrus')
        self.assertEqual(built.returncode, 0, built.stderr[-3000:])
        self.compare(src, exe, None)


if __name__ == '__main__':
    unittest.main()

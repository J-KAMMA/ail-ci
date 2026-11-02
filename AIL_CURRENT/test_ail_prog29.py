"""Typed reach for eight real programs, and the two compiler blockers fixed for them.

Profiled under CPython 3.12, the eight spend their own time in `main` plus the helpers named in
`lab/progfix/prog29.md`.  Three programs (t161, g08_004, t188) were already wholly typed and
g17_010's arithmetic helpers were already typed.  The one program moved here is g17_026, whose
four project functions all reach the typed path now:

* `VOWELS: Final[frozenset[str]] = frozenset("aeiou")` was refused as "a module-level name
  assigned to a Call".  `pyfunc._scan_module_consts` now accepts a `frozenset` of str literals as
  an ordered, duplicate-free `list[str]` constant, and `pyc._rewrite_script` keeps that assignment
  at module scope.  Because CPython's frozenset has no stable iteration order, every read must be
  `x in VOWELS` / `x not in VOWELS` or `len(VOWELS)`; anything else is refused by name.
* `len({ch for ch in text.lower() if ch in VOWELS})` was refused as "a set comprehension".  The
  `len` lowering now builds the existing eager list comprehension, adds its elements to a private
  int/set table and returns that table's length, so duplicates collapse exactly as CPython's set
  does.  A float set comprehension is still refused by name.

The other programs keep their recorded follow-ups: t475 needs `struct`, g16_006 needs generators,
g14_020 needs dataclass instance hash/eq, and g17_010's `numbers`/`main` need range as a returned
value and the map/filter pipeline.
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
    ('g17_010', 'lab/census/programs/gdev/g17_010.py', None),
    ('t161', 'lab/corpus/programs/deepseek-v4.1-flash-free/t161.py', 'lab/corpus/tasks/t161'),
    ('t475', 'lab/corpus/programs/deepseek-v4.1-flash-free/t475.py', 'lab/corpus/tasks/t475'),
    ('g16_006', 'lab/census/programs/gdev/g16_006.py', None),
    ('g08_004', 'lab/census/programs/gdev/g08_004.py', None),
    ('g17_026', 'lab/census/programs/gdev/g17_026.py', None),
    ('t188', 'lab/corpus/programs/deepseek-v4.1-flash-free/t188.py', 'lab/corpus/tasks/t188'),
    ('g14_020', 'lab/census/programs/gdev/g14_020.py', None),
)
NEWLY_TYPED = ('g17_026',)
ALREADY_TYPED = ('t161', 'g08_004', 't188')

SETCOMP_LEN = '''
class Box:
    def __init__(self, text: str) -> None:
        self.text = text


def vowels(text: str) -> int:
    return len({ch for ch in text.lower() if ch in "aeiou"})


def residues(values: list[int]) -> int:
    return len({v % 3 for v in values})


def main() -> None:
    words: list[str] = ["banana", "sky", "queue", "education"]
    table: dict[str, str] = {"first": "audio", "second": "rhythm"}
    box = Box("Aeon")
    total = 0
    total += vowels(words[0])
    total += vowels(table["first"])
    total += vowels(box.text)
    print(vowels(words[1]), vowels(table["second"]), vowels(box.text))
    if len({ch for ch in words[2] if ch in "aeiou"}) > 1:
        total += 100
    print(total, len({ch for ch in words[3]}) + 1)
    print(vowels(""), vowels("XYZ"))
    print(residues([0, 1, 2, 3, 4, 5, 6, 7, 8, 9]))
    print(residues([-1, -2, -3, -4]))
    print(len({c for c in "mississippi" if c != "s"}))
    print(len({x for x in [1, 1, 2, 2, 3]}))


main()
'''

FROZENSET_CONSTANTS = '''
VOWELS = frozenset("aeiou")
DIGITS = frozenset(["0", "1", "2", "3", "4", "5", "6", "7", "8", "9"])
REPEATED = frozenset("aabbcc")
EMPTY = frozenset("")
UNICODE = frozenset("aé☃")


def count_vowels(text: str) -> int:
    total = 0
    for ch in text.lower():
        if ch in VOWELS:
            total += 1
    return total


def count_digits(text: str) -> int:
    total = 0
    for ch in text:
        if ch not in DIGITS:
            total += 1
    return total


def main() -> None:
    print(count_vowels("banana"), count_vowels("XYZ"))
    print(count_digits("a1b2c3"))
    print(len(VOWELS), len(DIGITS), len(REPEATED), len(EMPTY), len(UNICODE))
    print("a" in REPEATED, "z" in REPEATED, "z" not in REPEATED)
    print("é" in UNICODE, "☃" in UNICODE, "x" in EMPTY, "x" not in EMPTY)


main()
'''

FROZENSET_ITERATION = '''
VOWELS = frozenset("aeiou")


def main() -> None:
    for ch in VOWELS:
        print(ch)


main()
'''

FLOAT_SETCOMP = '''
def main() -> None:
    print(len({x / 2 for x in [1, 2, 3]}))


main()
'''

MUTATED_SETCOMP = '''
class Box:
    def __init__(self) -> None:
        self.xs: list[int] = [1, 2]

    def side(self) -> bool:
        if len(self.xs) < 3:
            self.xs.append(99)
        return True


def f(box: Box) -> int:
    return len({x for x in box.xs if box.side()})


def main() -> None:
    box = Box()
    print(f(box), len(box.xs))


main()
'''

SHADOWED_LEN = '''
V = frozenset("aeiou")


def f() -> str:
    def len(x: list[str]) -> str:
        return x[0]
    return len(V)


print(f())
'''

SHADOWED_LEN_INNER_ONLY = '''
V = frozenset("aeiou")


def outer() -> int:
    def inner() -> int:
        len = 5
        return len
    return len(V)


print(outer())
'''

READ_BEFORE_ASSIGNMENT = '''
def f() -> bool:
    return "a" in V


print(f())
V = frozenset("aeiou")
'''

READ_AFTER_ASSIGNMENT = '''
def f() -> bool:
    return "a" in V


V = frozenset("aeiou")
print(f())
'''


def run(cmd, cwd=None, stdin=b'', env=None):
    return subprocess.run(cmd, cwd=cwd, input=stdin, capture_output=True, env=env, timeout=600)


@unittest.skipUnless(HAVE_CC, 'needs a C compiler')
class TypedReach29(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix='ail-prog29-')
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

    def hybrid(self, src, name):
        out = Path(self.tmp) / ('hybrid-' + name)
        cmd = [sys.executable, '-B', CLI, 'build', '--cpython', str(src), '-o', str(out)]
        built = run(cmd, Path(self.tmp), env=self.env)
        return built, out / src.stem

    def test_all_eight_match_cpython_under_the_hybrid(self):
        for name, rel, task in PROGRAMS:
            src = REPO / rel
            built, exe = self.hybrid(src, name)
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

    def test_already_typed_build_strict(self):
        for name, rel, task in PROGRAMS:
            if name not in ALREADY_TYPED:
                continue
            src = REPO / rel
            built, exe = self.build(src, name, strict=True)
            self.assertEqual(built.returncode, 0, built.stderr[-3000:])
            self.compare(src, exe, task)

    def test_set_comprehension_len(self):
        src = Path(self.tmp) / 'setcomp_len.py'
        src.write_text(SETCOMP_LEN, encoding='utf-8')
        built, exe = self.build(src, 'setcomp_len', strict=True)
        self.assertEqual(built.returncode, 0, built.stderr[-3000:])
        self.compare(src, exe, None)

    def test_frozenset_module_constants(self):
        src = Path(self.tmp) / 'frozenset_constants.py'
        src.write_text(FROZENSET_CONSTANTS, encoding='utf-8')
        built, exe = self.build(src, 'frozenset_constants', strict=True)
        self.assertEqual(built.returncode, 0, built.stderr[-3000:])
        self.compare(src, exe, None)

    def test_frozenset_iteration_is_refused_by_name(self):
        src = Path(self.tmp) / 'frozenset_iteration.py'
        src.write_text(FROZENSET_ITERATION, encoding='utf-8')
        built, _ = self.build(src, 'frozenset_iteration', strict=True)
        output = (built.stdout + built.stderr).decode('utf-8', 'replace')
        self.assertNotEqual(built.returncode, 0, output[-3000:])
        self.assertIn("'VOWELS' is a module-level frozenset", output)
        self.assertIn('iteration order of a frozenset is not preserved', output)

    def test_float_set_comprehension_is_refused_by_name(self):
        src = Path(self.tmp) / 'float_setcomp.py'
        src.write_text(FLOAT_SETCOMP, encoding='utf-8')
        built, _ = self.build(src, 'float_setcomp', strict=True)
        output = (built.stdout + built.stderr).decode('utf-8', 'replace')
        self.assertNotEqual(built.returncode, 0, output[-3000:])
        self.assertIn('set comprehension with float elements', output)

    def test_mutated_set_comprehension_source_is_refused_by_name(self):
        src = Path(self.tmp) / 'mutated_setcomp.py'
        src.write_text(MUTATED_SETCOMP, encoding='utf-8')
        built, _ = self.build(src, 'mutated_setcomp', strict=True)
        output = (built.stdout + built.stderr).decode('utf-8', 'replace')
        self.assertNotEqual(built.returncode, 0, output[-3000:])
        self.assertIn('set comprehension over a mutable sequence', output)
        general, exe = self.build(src, 'mutated_setcomp_general', strict=False)
        self.assertEqual(general.returncode, 0, general.stderr[-3000:])
        self.compare(src, exe, None)

    def test_shadowed_len_is_refused_by_name(self):
        src = Path(self.tmp) / 'shadowed_len.py'
        src.write_text(SHADOWED_LEN, encoding='utf-8')
        built, _ = self.build(src, 'shadowed_len', strict=True)
        output = (built.stdout + built.stderr).decode('utf-8', 'replace')
        self.assertNotEqual(built.returncode, 0, output[-3000:])
        self.assertIn("'V' is a module-level frozenset", output)
        self.assertIn('not the builtin', output)
        general, exe = self.build(src, 'shadowed_len_general', strict=False)
        self.assertEqual(general.returncode, 0, general.stderr[-3000:])
        self.compare(src, exe, None)

    def test_len_shadowed_in_an_unrelated_scope_stays_typed(self):
        src = Path(self.tmp) / 'shadowed_len_inner.py'
        src.write_text(SHADOWED_LEN_INNER_ONLY, encoding='utf-8')
        built, exe = self.build(src, 'shadowed_len_inner', strict=True)
        self.assertEqual(built.returncode, 0, built.stderr[-3000:])
        self.compare(src, exe, None)

    def test_frozenset_read_before_assignment_is_refused_by_name(self):
        src = Path(self.tmp) / 'read_before_assignment.py'
        src.write_text(READ_BEFORE_ASSIGNMENT, encoding='utf-8')
        built, _ = self.build(src, 'read_before', strict=True)
        output = (built.stdout + built.stderr).decode('utf-8', 'replace')
        self.assertNotEqual(built.returncode, 0, output[-3000:])
        self.assertIn("'V' is a module-level frozenset read before its assignment", output)
        general, exe = self.build(src, 'read_before_general', strict=False)
        self.assertEqual(general.returncode, 0, general.stderr[-3000:])
        self.compare(src, exe, None)

    def test_frozenset_read_after_assignment_builds_typed(self):
        src = Path(self.tmp) / 'read_after_assignment.py'
        src.write_text(READ_AFTER_ASSIGNMENT, encoding='utf-8')
        built, exe = self.build(src, 'read_after', strict=True)
        self.assertEqual(built.returncode, 0, built.stderr[-3000:])
        self.compare(src, exe, None)


if __name__ == '__main__':
    unittest.main()

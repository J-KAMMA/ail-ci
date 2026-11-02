"""Typed reach for the hot functions of eight real programs (job-prog30, 2026-11-02), against CPython 3.12.

`t266` spent its time in `main` (which read the input through `it = iter(data)` and `next(it)`) and
`dfs`; the iterator calls kept the whole program on the general path.  The rewrite this module covers
turns a local `it = iter(sequence)` followed by `next(it)` into an index cursor over the same list /
str / bytes, when the sequence and every use of `it` have the simple shape the rewrite can prove.

P1  `lab/corpus/programs/deepseek-v4.1-flash-free/t266.py` builds typed and matches CPython.
P2  a list literal, `next` in an augmented assignment, a wrapped `next`, and several `next` calls in
    one `print` build typed and match CPython.
P3  a named list, a str and bytes do the same; a list appended to after `iter()` is still walked on,
    exactly as CPython's list iterator is.
P4  a `next` in an `if` test is hoisted ahead of the branch, as CPython evaluates it.
P5  rebinding the source name after `iter()`, a `try`, a `next` in a `while` test, the two-argument
    `next(it, default)`, a `next` after an effectful argument, a `next` before the binding and a
    deleted source stay on the general path and still match CPython.
P6  the programs that already built typed at the base still do (`g11_022`, `g09_034`, `g02_012`,
    `t244`); `g23_004` and `g03_008` stay general (recorded follow-ups) and match CPython.
P7  an exhausted cursor stops the program like CPython (same stdout and exit status).  The typed
    runtime names the trap `list index out of range` where CPython says `StopIteration`; that
    stderr-only spelling is recorded in DIFFERENCES.
P8  `t172` needs a dict of dicts, tuple iteration and generator unpacking at once: it is refused
    by name (the general path cannot build it either) and the exact first reason is recorded.
P9  `xs += [<comprehension>]` keeps both the old and the new elements, for a list of str and a
    nested list (the hoisted comprehension's temp is not freed before its consumer).
P10 an augmented-assignment target that runs code (`a[items.pop(0) % 2] += next(it)`) is evaluated
    before the value in CPython, so the cursor lowering is refused and the program stays general;
    a plain name target (`total += next(it)`) is still lowered.
P11 `iter` or `next` bound in the function's own scope (a local, a parameter, or a nested
    def/class name) replaces the builtin, so the cursor lowering is refused and those programs
    stay general and match CPython; a shadow inside a nested function's own scope does not
    affect the outer function and it still builds typed.
"""
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent
HAVE_CC = shutil.which('gcc') is not None or shutil.which('cc') is not None

ITER_LIST = '''def main() -> None:
    it = iter([3, 1, 2])
    total = 0
    total += next(it)
    total += int(next(it))
    print(total, next(it))
main()
'''

ITER_NAME = '''def main() -> None:
    items = ["alpha", "beta", "gamma"]
    it = iter(items)
    a = next(it)
    b = int(len(next(it)))
    print(a, b, next(it))
main()
'''

ITER_STR = '''def main() -> None:
    it = iter("abc")
    print(next(it), next(it))
    print(next(it))
main()
'''

ITER_BYTES = '''def main() -> None:
    it = iter(b"ab")
    print(next(it), next(it))
main()
'''

ITER_MUTATE = '''def main() -> None:
    items = [1, 2]
    it = iter(items)
    print(next(it))
    items.append(3)
    print(next(it), next(it))
    print(items)
main()
'''

ITER_IF = '''def main() -> None:
    it = iter([1, 2])
    if next(it) == 1:
        print("one", next(it))
main()
'''

ITER_REBIND = '''def main() -> None:
    items = [1, 2]
    it = iter(items)
    items = [8, 9]
    print(next(it))
main()
'''

ITER_TRY = '''def main() -> None:
    it = iter([1])
    try:
        print(next(it))
        print(next(it))
    except StopIteration:
        print("done")
main()
'''

ITER_WHILE = '''def main() -> None:
    it = iter([1, 2])
    while next(it) > 0:
        print("x")
main()
'''

ITER_DEFAULT = '''def main() -> None:
    it = iter([1])
    print(next(it, 9))
    print(next(it, 9))
main()
'''

ITER_UNSAFE = '''def f(a: int, b: int) -> int:
    return a + b
def main() -> None:
    items = [1, 2, 3]
    it = iter(items)
    print(f(items.pop(), next(it)), items)
main()
'''

ITER_EXHAUSTED = '''def main() -> None:
    it = iter([1])
    print(next(it))
    print(next(it))
main()
'''

ITER_BEFORE = '''def main() -> None:
    print(next(it))
    it = iter([1, 2])
main()
'''

ITER_DEL = '''def main() -> None:
    items = [1, 2]
    it = iter(items)
    print(next(it))
    del items
    print(next(it))
main()
'''

SHADOW_NEXT_NESTED = '''def main() -> None:
    def next(x):
        return 42
    it = iter([1, 2])
    print(next(it))
main()
'''

SHADOW_ITER_NESTED = '''def main() -> None:
    def iter(x):
        return [9]
    xs = [1, 2, 3]
    it = iter(xs)
    print(next(it))
main()
'''

SHADOW_ITER_LOCAL = '''def main() -> None:
    iter = 5
    xs = [1, 2, 3]
    it = iter(xs)
    print(next(it))
main()
'''

SHADOW_NEXT_LOCAL = '''def main() -> None:
    next = 5
    xs = [1, 2, 3]
    it = iter(xs)
    print(next(it))
main()
'''

SHADOW_ITER_PARAM = '''def main(iter: int) -> None:
    xs = [1, 2, 3]
    it = iter(xs)
    print(next(it))
main(5)
'''

SHADOW_NEXT_PARAM = '''def main(next: int) -> None:
    xs = [1, 2, 3]
    it = iter(xs)
    print(next(it))
main(5)
'''

SHADOW_NESTED_SCOPE_ONLY = '''def main() -> None:
    def helper():
        next = 5
        return next
    it = iter([1, 2])
    print(next(it), helper())
main()
'''

SHADOWED = {
    'shadow_next_nested': SHADOW_NEXT_NESTED,
    'shadow_iter_nested': SHADOW_ITER_NESTED,
    'shadow_iter_local': SHADOW_ITER_LOCAL,
    'shadow_next_local': SHADOW_NEXT_LOCAL,
    'shadow_iter_param': SHADOW_ITER_PARAM,
    'shadow_next_param': SHADOW_NEXT_PARAM,
}

AUG_COMP = '''def main() -> None:
    rows = [[1, 2], [3, 4]]
    lines = [" ".join(map(str, row)) for row in rows]
    lines += [" ".join(map(str, row)) for row in rows]
    print(lines)
main()
'''

AUG_NESTED = '''def main() -> None:
    g = [[1], [2]]
    g += [[x, x + 1] for x in [3, 4]]
    for row in g:
        print(" ".join(map(str, row)))
main()
'''

AUG_EFFECTFUL_TARGET = '''def main() -> None:
    items = [10, 20, 30]
    it = iter(items)
    a = [0, 0]
    a[items.pop(0) % 2] += next(it)
    print(a, items)
main()
'''

T266 = ROOT.parent / 'lab/corpus/programs/deepseek-v4.1-flash-free/t266.py'
T266_INPUTS = sorted((ROOT.parent / 'lab/corpus/tasks/t266').glob('in*.txt'))

ALREADY_TYPED = {
    'g11_022': ROOT.parent / 'lab/census/programs/gdev/g11_022.py',
    'g09_034': ROOT.parent / 'lab/census/programs/gdev/g09_034.py',
    'g02_012': ROOT.parent / 'lab/census/programs/gdev/g02_012.py',
    't244': ROOT.parent / 'lab/census/programs/dev/t244.py',
}

STILL_GENERAL = {
    'g23_004': ROOT.parent / 'lab/census/programs/gdev/g23_004.py',
    'g03_008': ROOT.parent / 'lab/census/programs/gdev/g03_008.py',
}

INPUTS = {
    't244': ROOT.parent / 'lab/corpus/tasks/t244/in2.txt',
}

T172 = ROOT.parent / 'lab/corpus/programs/deepseek-v4.1-flash-free/t172.py'
T172_FIRST_REASON = ("import of 'collections' with a use that is not built: Counter, defaultdict "
                     "(int, float, str, list, lambda: <constant>), OrderedDict and deque are built "
                     "for str / int / tuple keys and int / float / str / tuple elements")


def _env(extra=None):
    env = dict(os.environ, AIL_NO_CACHE='1')
    for key in ('AIL_NO_GENERAL', 'AIL_UNIFIED_FORCE', 'AIL_QUIET_FALLBACK'):
        env.pop(key, None)
    if extra:
        env.update(extra)
    return env


def compile_source(directory, source, name, extra_env=None):
    path = Path(directory, name + '.py')
    if isinstance(source, Path):
        path.write_bytes(source.read_bytes())
    else:
        path.write_text(source, encoding='utf-8')
    exe = Path(directory, name + '_x')
    res = subprocess.run([sys.executable, '-B', str(ROOT / 'ail_chatgpt.py'), 'compile', path.name,
                          '-o', exe.name], cwd=directory, capture_output=True, text=True,
                         timeout=900, env=_env(extra_env))
    return res, exe, path


def run_python(path, stdin=b''):
    return subprocess.run([sys.executable, str(path)], input=stdin, capture_output=True, timeout=300)


def run_exe(exe, stdin=b''):
    return subprocess.run([str(exe)], input=stdin, capture_output=True, timeout=300)


def typed(res):
    return 'built on the general path' not in res.stderr


@unittest.skipUnless(HAVE_CC, 'needs a C compiler')
class Prog30(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.mkdtemp(prefix='prog30_')

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp, ignore_errors=True)

    def check(self, source, name, expect_typed=True, stdin=b'', extra_env=None):
        res, exe, path = compile_source(self.tmp, source, name, extra_env)
        self.assertEqual(res.returncode, 0, res.stderr[-1500:])
        self.assertEqual(typed(res), expect_typed, res.stderr[-800:])
        want = run_python(path, stdin)
        got = run_exe(exe, stdin)
        self.assertEqual(got.stdout, want.stdout, name)
        self.assertEqual(got.returncode, want.returncode, name)
        return res, want

    def test_t266_typed_and_equal(self):
        if not T266.exists():
            self.skipTest('lab/corpus is not in this tree')
        res, exe, path = compile_source(self.tmp, T266, 't266')
        self.assertEqual(res.returncode, 0, res.stderr[-1500:])
        self.assertTrue(typed(res), res.stderr[-800:])
        for source in T266_INPUTS:
            stdin = source.read_bytes()
            want = run_python(path, stdin)
            got = run_exe(exe, stdin)
            self.assertEqual(got.stdout, want.stdout, source.name)
            self.assertEqual(got.returncode, want.returncode, source.name)

    def test_list_literal_and_wrapped_next_typed(self):
        self.check(ITER_LIST, 'iter_list')

    def test_named_list_of_str_typed(self):
        self.check(ITER_NAME, 'iter_name')

    def test_str_and_bytes_typed(self):
        self.check(ITER_STR, 'iter_str')
        self.check(ITER_BYTES, 'iter_bytes')

    def test_list_appended_after_iter_is_still_walked(self):
        self.check(ITER_MUTATE, 'iter_mutate')

    def test_next_in_an_if_test_typed(self):
        self.check(ITER_IF, 'iter_if')

    def test_exhausted_cursor_typed_and_equal(self):
        self.check(ITER_EXHAUSTED, 'iter_exhausted')

    def test_augassign_comprehension_keeps_both_sides(self):
        self.check(AUG_COMP, 'aug_comp')
        self.check(AUG_NESTED, 'aug_nested')

    def test_effectful_augassign_target_stays_general(self):
        self.check(AUG_EFFECTFUL_TARGET, 'aug_effectful_target', expect_typed=False)

    def test_unsupported_shapes_stay_general(self):
        for source, name in ((ITER_REBIND, 'iter_rebind'), (ITER_TRY, 'iter_try'),
                             (ITER_WHILE, 'iter_while'), (ITER_DEFAULT, 'iter_default'),
                             (ITER_UNSAFE, 'iter_unsafe'), (ITER_BEFORE, 'iter_before'),
                             (ITER_DEL, 'iter_del')):
            self.check(source, name, expect_typed=False)

    def test_shadowed_iter_next_are_not_lowered(self):
        for name, source in SHADOWED.items():
            self.check(source, name, expect_typed=False)
        self.check(SHADOW_NESTED_SCOPE_ONLY, 'shadow_nested_scope_only')

    def test_iter_rewrite_on_both_builds(self):
        for env in ({'AIL_IR': '0'}, {'AIL_IR': '1'}):
            self.check(ITER_LIST, 'iter_list_ir' + env['AIL_IR'], extra_env=env)

    def test_already_typed_programs_stay_typed(self):
        for name, path in ALREADY_TYPED.items():
            if not path.exists():
                continue
            stdin = INPUTS[name].read_bytes() if name in INPUTS else b''
            self.check(path, name, stdin=stdin)

    def test_recorded_follow_ups_stay_general_and_equal(self):
        for name, path in STILL_GENERAL.items():
            if not path.exists():
                continue
            stdin = INPUTS[name].read_bytes() if name in INPUTS else b''
            self.check(path, name, expect_typed=False, stdin=stdin)

    def test_t172_is_refused_by_name(self):
        if not T172.exists():
            self.skipTest('lab/corpus is not in this tree')
        res, _, _ = compile_source(self.tmp, T172, 't172')
        self.assertEqual(res.returncode, 3, res.stderr[-1500:])
        self.assertIn(T172_FIRST_REASON, res.stderr)


if __name__ == '__main__':
    unittest.main()

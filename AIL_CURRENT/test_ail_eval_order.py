"""A hoisted list count/index call must not run before an operand Python evaluates first.

`xs.count(v)` / `xs.index(v)` are rewritten into statements placed at the start of the enclosing
statement.  CPython evaluates the operands to their left first, so a call in `xs[i]` (or a call
that changes the list) must happen before the count/index runs.  `_ListLowering.index_or_count`
now hoists only when every earlier operand is quiet (a name, a constant or an attribute chain),
or, for `count`, when its argument and receiver are quiet and no earlier call can change the
source.  Anything else is refused by name and takes the general path, which keeps source order.

The last group records the still-open helpers found while auditing the same shape (list `+`,
`list(...)` and the heapq values); they are not fixed here because more than two helpers need it.
"""
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent
CLI = str(ROOT / "ail_chatgpt.py")

TEMPLATE = '''def f(a: int) -> int:
    print("side")
    return a


def main() -> None:
    xs: list[int] = [1, 2]
    i: int = 5
    try:
        STMT
    except IndexError:
        print("caught")


main()
'''

BIG = '''def f(a: int) -> int:
    print("side")
    return a


def main() -> None:
    xs: list[int] = [1, 2]
    w: int = 1
    try:
        print(1, xs[4611686018427387904 * w] > 3, xs.count(f(2)))
    except IndexError:
        print("caught")


main()
'''

INDEX_QUIET = '''def main() -> None:
    xs: list[int] = [1, 2]
    i: int = 5
    try:
        print(xs[i], xs.index(99))
    except IndexError:
        print("caught")


main()
'''

COUNT_POP = '''def main() -> None:
    xs: list[int] = [1, 2, 1]
    print(xs.pop(), xs.count(1))


main()
'''

PROBES = {
    'eo_count': TEMPLATE.replace('STMT', 'print(xs[i], xs.count(f(2)))'),
    'eo_count_cmp': TEMPLATE.replace('STMT', 'print(xs[i] > 3, xs.count(f(2)))'),
    'eo_index': TEMPLATE.replace('STMT', 'print(xs[i], xs.index(f(1)))'),
    'eo_assign': TEMPLATE.replace('STMT', 'y = (xs[i], xs.count(f(2)))'),
    'eo_big': BIG,
    'index_quiet_raises_first': INDEX_QUIET,
    'count_after_mutation': COUNT_POP,
}

COUNT_NOEXC = TEMPLATE.replace('STMT', 'print(xs.count(f(2)), xs[0])')

# Found while checking the other hoisting helpers (change 2).  More than two need the guard, so
# they are listed as open instead of fixed; the default build still prints "side" too early.
OPEN_HELPERS = {
    'concat': TEMPLATE.replace('STMT', 'print(xs[i], xs + [f(2)])'),
    'list_call': '''def g() -> list[int]:
    print("side")
    return [2]


def main() -> None:
    xs: list[int] = [1, 2]
    i: int = 5
    try:
        print(xs[i], list(g()))
    except IndexError:
        print("caught")


main()
''',
    'heappop': '''from heapq import heappop


def main() -> None:
    xs: list[int] = [1, 2]
    h: list[int] = [3, 4]
    i: int = 5
    try:
        print(xs[i], heappop(h))
    except IndexError:
        print("caught")
    print(h)


main()
''',
}

MODES = (
    ('default', {}),
    ('unified', {'AIL_UNIFIED_FORCE': '1'}),
)


def run_case(test, name, text, extra, strict=False):
    with tempfile.TemporaryDirectory(prefix='ail-eval-order-') as directory:
        src = Path(directory) / (name + '.py')
        src.write_text(text, encoding='utf-8')
        want = subprocess.run([sys.executable, '-B', str(src)], capture_output=True, timeout=120,
                              env=dict(os.environ, PYTHONUTF8='1'))
        test.assertEqual(want.returncode, 0, want.stderr[-1500:])
        exe = Path(directory) / ('exe_' + name)
        env = dict(os.environ, AIL_NO_CACHE='1', AIL_QUIET_FALLBACK='1')
        for key in ('AIL_UNIFIED_FORCE', 'AIL_UNIFIED', 'AIL_IR', 'AIL_NO_GENERAL'):
            env.pop(key, None)
        env.update(extra)
        command = [sys.executable, '-B', CLI, 'compile', src.name, '--syntax', 'python',
                   '-o', exe.name]
        if strict:
            command.append('--strict')
        built = subprocess.run(command, cwd=directory, capture_output=True, text=True,
                               timeout=900, env=env)
        test.assertEqual(built.returncode, 0, built.stdout[-3000:] + built.stderr[-3000:])
        got = subprocess.run([str(exe)], capture_output=True, timeout=120, cwd=directory)
        test.assertEqual((got.stdout.replace(b'\r\n', b'\n'), got.returncode),
                         (want.stdout.replace(b'\r\n', b'\n'), want.returncode),
                         '%s (%s)\n%s' % (name, extra, got.stderr.decode('utf-8', 'replace')[-1500:]))


class EvalOrderTests(unittest.TestCase):
    def test_probes_match_cpython_in_both_builds(self):
        for name, text in PROBES.items():
            for mode, extra in MODES:
                with self.subTest(name=name, mode=mode):
                    run_case(self, '%s_%s' % (name, mode), text, extra)

    def test_count_noexc_stays_typed(self):
        run_case(self, 'count_noexc_strict', COUNT_NOEXC, {}, strict=True)

    @unittest.expectedFailure
    def test_open_concat(self):
        for mode, extra in MODES:
            run_case(self, 'open_concat_' + mode, OPEN_HELPERS['concat'], extra)

    @unittest.expectedFailure
    def test_open_list_call(self):
        for mode, extra in MODES:
            run_case(self, 'open_list_' + mode, OPEN_HELPERS['list_call'], extra)

    @unittest.expectedFailure
    def test_open_heappop(self):
        for mode, extra in MODES:
            run_case(self, 'open_heap_' + mode, OPEN_HELPERS['heappop'], extra)


if __name__ == '__main__':
    unittest.main()

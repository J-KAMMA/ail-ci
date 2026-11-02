"""fz216: a hoisted `list.count()` / `list.index()` ran before operands Python evaluates first.

The list lowering turns `xs.count(v)` into statements placed at the start of the enclosing
statement.  When an earlier operand of that statement can raise or run code, CPython has not
evaluated it yet: `print(62, xs[99], xs.count(side(99)))` raises IndexError before `side` runs,
while the lowered form ran `side` first (and, in the fuzz program, then diverged).  The lowering
now names that order and leaves the function to the general path, which evaluates operands in
source order.  Values are checked through list items, an attribute, a dict value and an argument,
for int, float and str lists, and a safe earlier operand (a name or `len`) still builds.
"""
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent
CLI = str(ROOT / "ail_chatgpt.py")

MIN_COUNT = r'''def side(x: int) -> int:
    print("side", x)
    return x


def main() -> int:
    v: list[int] = [1, 2, 3]
    try:
        print(62, v[99], v.count(side(99)))
    except IndexError:
        print(-34)
    return 0


main()
'''

MIN_INDEX = r'''def side(x: int) -> int:
    print("side", x)
    return x


def main() -> int:
    v: list[int] = [1, 2, 3]
    try:
        print(62, v[99], v.index(side(2)))
    except IndexError:
        print(-34)
    return 0


main()
'''

CALL_ORDER = r'''def f(x: int) -> int:
    print("f", x)
    return x


def g(x: int) -> int:
    print("g", x)
    return x


def main() -> int:
    v: list[int] = [1, 2, 3]
    print(f(1), v.count(g(2)))
    print(f(3), v.index(g(2)))
    print("x", v[99] if False else v.count(2))
    return 0


main()
'''

TYPES = r'''class Box:
    def __init__(self, xs: list[int]) -> None:
        self.xs: list[int] = xs


def iside(x: int) -> int:
    print("i", x)
    return x


def fside(x: float) -> float:
    print("f", x)
    return x


def sside(x: str) -> str:
    print("s", x)
    return x


def via_arg(xs: list[int], i: int) -> int:
    try:
        print(xs[i], xs.count(iside(2)))
    except IndexError:
        print("ca")
    return 0


def main() -> int:
    xs: list[int] = [1, 2, 3]
    fs: list[float] = [1.5, 2.5]
    ss: list[str] = ["a", "b"]
    b: Box = Box(xs)
    d: dict[str, list[int]] = {"k": xs}
    try:
        print(xs[99], xs.count(iside(2)))
    except IndexError:
        print("ci")
    try:
        print(fs[99], fs.count(fside(2.5)))
    except IndexError:
        print("cf")
    try:
        print(ss[99], ss.count(sside("a")))
    except IndexError:
        print("cs")
    try:
        print(b.xs[99], b.xs.count(iside(2)))
    except IndexError:
        print("cb")
    try:
        print(d["k"][99], d["k"].count(iside(2)))
    except IndexError:
        print("cd")
    via_arg(xs, 99)
    return 0


main()
'''

SAFE = r'''def main() -> int:
    xs: list[int] = [1, 2, 3, 2]
    ss: list[str] = ["a", "b", "a"]
    print("x", xs.count(2), xs.index(3))
    print(len(xs), ss.count("a"), ss.index("b"))
    print(xs.count(2), 99 // 3)
    print(xs.count(2), xs.index(2, 1))
    return 0


main()
'''

MODES = (
    ('default', {}),
    ('legacy', {'AIL_IR': '0'}),
    ('ir', {'AIL_IR': '1'}),
)


def cpython(directory, name, text):
    src = Path(directory) / (name + '_cpython.py')
    src.write_text(text, encoding='utf-8')
    done = subprocess.run([sys.executable, '-B', str(src)], capture_output=True, timeout=120,
                          env=dict(os.environ, PYTHONUTF8='1'))
    return done.stdout.replace(b'\r\n', b'\n'), done.returncode, done.stderr[-1500:]


def build_and_run(directory, name, text, extra, no_general=False):
    src = Path(directory) / (name + '.ail')
    src.write_text(text, encoding='utf-8')
    exe = Path(directory) / ('exe_' + name)
    env = dict(os.environ, AIL_NO_CACHE='1', AIL_QUIET_FALLBACK='1')
    for key in ('AIL_UNIFIED_FORCE', 'AIL_UNIFIED', 'AIL_IR', 'AIL_NO_GENERAL'):
        env.pop(key, None)
    env.update(extra)
    if no_general:
        env['AIL_NO_GENERAL'] = '1'
    built = subprocess.run([sys.executable, '-B', CLI, 'compile', src.name, '--syntax', 'python',
                            '-o', exe.name], cwd=directory, capture_output=True, text=True,
                           timeout=900, env=env)
    if built.returncode != 0:
        return None, (built.stdout + built.stderr)[-3000:]
    got = subprocess.run([str(exe)], capture_output=True, timeout=120, cwd=directory)
    return (got.stdout.replace(b'\r\n', b'\n'), got.returncode), got.stderr.decode('utf-8', 'replace')[-1500:]


class ListMethodOrder(unittest.TestCase):
    def check(self, slug, text):
        with tempfile.TemporaryDirectory(prefix='ail-fz216-') as directory:
            want, want_rc, want_err = cpython(directory, slug, text)
            self.assertEqual(want_rc, 0, want_err)
            for mode, extra in MODES:
                got, err = build_and_run(directory, '%s_%s' % (slug, mode), text, extra)
                self.assertIsNotNone(got, '%s (%s)\n%s' % (text, mode, err))
                self.assertEqual(got, (want, want_rc), '%s (%s)\n%s' % (text, mode, err))

    def test_count_after_raising_operand(self):
        self.check('min_count', MIN_COUNT)

    def test_index_after_raising_operand(self):
        self.check('min_index', MIN_INDEX)

    def test_side_effect_order(self):
        self.check('call_order', CALL_ORDER)

    def test_types_and_provenance(self):
        self.check('types', TYPES)

    def test_safe_earlier_operand_stays_typed(self):
        with tempfile.TemporaryDirectory(prefix='ail-fz216-') as directory:
            want, want_rc, want_err = cpython(directory, 'safe', SAFE)
            self.assertEqual(want_rc, 0, want_err)
            got, err = build_and_run(directory, 'safe_typed', SAFE, {}, no_general=True)
            self.assertIsNotNone(got, 'typed path refused a safe count/index\n%s' % err)
            self.assertEqual(got, (want, want_rc), err)

    def test_unsafe_order_is_named_when_general_path_is_off(self):
        with tempfile.TemporaryDirectory(prefix='ail-fz216-') as directory:
            got, err = build_and_run(directory, 'min_refused', MIN_COUNT, {}, no_general=True)
            self.assertIsNone(got, 'expected a named refusal, got %r' % (got,))
            self.assertIn('list.count()', err)
            self.assertIn('Python evaluates first', err)


if __name__ == '__main__':
    unittest.main()

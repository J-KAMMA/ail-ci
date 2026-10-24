"""Counter ordering comparisons (pre16 p5), against CPython 3.12.

CPython 3.12's collections.Counter defines `< <= > >=` over the union of both operands' keys with a
missing count read as 0: `<=` / `>=` are the subset / superset tests and `<` / `>` their proper
forms. AIL used to fall through to the plain dict comparison and raise `TypeError`. The program below
covers empty and equal counters, zero and negative counts, floats and NaN, aliasing, a counter reached
through an argument, a list item, an attribute and a dict value, and every non-Counter operand kind.

Both builds are checked (the general path forced, and the default build), and stdout must equal
CPython's. The typed path still refuses ordering comparisons between collections by name; the default
build then uses the general path.
"""
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent
CHATGPT = str(ROOT / 'ail_chatgpt.py')
HAVE_CC = shutil.which('gcc') is not None


def _cpython(directory, name, text):
    src = Path(directory) / (name + '_cpython.py')
    src.write_text(text, encoding='utf-8')
    done = subprocess.run([sys.executable, '-B', str(src)], capture_output=True, timeout=120,
                          env=dict(os.environ, PYTHONUTF8='1'))
    return done.stdout.replace(b'\r\n', b'\n'), done.returncode


def _build_run(directory, name, text, general):
    src = Path(directory) / (name + '.ail')
    src.write_text(text, encoding='utf-8')
    exe = Path(directory) / ('exe_' + name + ('_g' if general else '_d'))
    env = dict(os.environ, AIL_NO_CACHE='1', AIL_QUIET_FALLBACK='1')
    env.pop('AIL_NO_GENERAL', None)
    if general:
        env['AIL_UNIFIED_FORCE'] = '1'
    cmd = [sys.executable, '-B', CHATGPT, 'compile', src.name, '--syntax', 'python', '-o', exe.name]
    built = subprocess.run(cmd, cwd=directory, capture_output=True, text=True, timeout=900, env=env)
    if built.returncode != 0:
        return None, (built.stdout + built.stderr)[-1500:]
    got = subprocess.run([str(exe)], capture_output=True, timeout=120, cwd=directory)
    return (got.stdout.replace(b'\r\n', b'\n'), got.returncode), got.stderr.decode('utf-8', 'replace')[-800:]


def check_program(test, name, text, modes=(True, False)):
    with tempfile.TemporaryDirectory(prefix='ail-pre16-') as directory:
        want = _cpython(directory, name, text)
        test.assertEqual(want[1], 0, text)
        for general in modes:
            got, err = _build_run(directory, name, text, general)
            test.assertIsNotNone(got, '%s (general=%s)\n%s' % (text, general, err))
            test.assertEqual(got, want, '%s (general=%s)\n%s' % (text, general, err))


COUNTER_ORDER = r'''from collections import Counter


class Box:
    def __init__(self, c):
        self.c = c


def lt(a, b):
    return a < b


def le(a, b):
    return a <= b


def gt(a, b):
    return a > b


def ge(a, b):
    return a >= b


def show(label, a, b):
    print(label, lt(a, b), le(a, b), gt(a, b), ge(a, b), len(a), len(b))


def main():
    nan = float("nan")
    pairs = [
        ("empty", Counter(), Counter()),
        ("equal", Counter("aab"), Counter("aab")),
        ("zero", Counter({"a": 1}), Counter({"a": 1, "b": 0})),
        ("subset", Counter("a"), Counter("ab")),
        ("reverse", Counter("ab"), Counter("a")),
        ("incomparable", Counter("ab"), Counter("bc")),
        ("negative", Counter({"a": 1, "b": -1}), Counter({"a": 1})),
        ("float", Counter({"a": 1}), Counter({"a": 1.0})),
        ("nan", Counter({"a": nan}), Counter({"a": nan})),
    ]
    for label, a, b in pairs:
        show(label, a, b)
        show(label + "-rev", b, a)
    c = Counter("ab")
    show("alias", c, c)
    print("len-after", len(c), len(Counter("a")))
    print("func", lt(Counter("a"), Counter("ab")), le(Counter("a"), Counter("ab")),
          gt(Counter("ab"), Counter("a")), ge(Counter("ab"), Counter("a")))
    box = Box(Counter("a"))
    hold = [Counter("ab")]
    byname = {"c": Counter("abc")}
    show("attr", box.c, Counter("ab"))
    show("list", hold[0], Counter("a"))
    show("dict", byname["c"], Counter("ab"))
    for other in ({}, {"a": 1}, [1], 1, "a", None, {1}, (1,)):
        for op in ("lt", "le", "gt", "ge"):
            try:
                if op == "lt":
                    r = lt(Counter("a"), other)
                elif op == "le":
                    r = le(Counter("a"), other)
                elif op == "gt":
                    r = gt(Counter("a"), other)
                else:
                    r = ge(Counter("a"), other)
                print(type(other).__name__, op, r)
            except TypeError as e:
                print(type(other).__name__, op, type(e).__name__)


main()
'''

COUNTER_ORDER_ANNOTATED = r'''from collections import Counter


def lt(a: Counter[str], b: Counter[str]) -> bool:
    return a < b


def le(a: Counter[str], b: Counter[str]) -> bool:
    return a <= b


def gt(a: Counter[str], b: Counter[str]) -> bool:
    return a > b


def ge(a: Counter[str], b: Counter[str]) -> bool:
    return a >= b


def main() -> None:
    a: Counter[str] = Counter("ab")
    b: Counter[str] = Counter("abc")
    c: Counter[str] = Counter("bc")
    print(lt(a, b), le(a, b), gt(b, a), ge(b, a))
    print(lt(a, c), le(a, c), gt(a, c), ge(a, c), lt(a, a), le(a, a), gt(a, a), ge(a, a))


main()
'''


@unittest.skipUnless(HAVE_CC, 'gcc is required')
class CounterOrdering(unittest.TestCase):
    def test_general_and_default_builds(self):
        check_program(self, 'ctr_order', COUNTER_ORDER)

    def test_annotated_counters(self):
        check_program(self, 'ctr_order_ann', COUNTER_ORDER_ANNOTATED)


if __name__ == '__main__':
    unittest.main()

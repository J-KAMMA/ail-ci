"""Builtins outside `_BUILTIN_VALUE_ARITY` used as values, against CPython 3.12 (job pre252).

The review of job rbpre183 listed three pre-existing differences, of which the first still
differed on this tree: a builtin used as a first-class value was refused by name unless it was
in the fixed-arity map (`len`, `abs`, ...), so `f = max`, `[min, max]`, `{"m": max}` and a value
reaching a call through an argument or a return did not compile.

`max` and `min` now have a variadic value adapter (one iterable argument, or two or more
arguments, like the direct call), and `callable` / `hash` are in the fixed-arity map. The
generated FUNC object keeps the builtin-kind flag, so `type(max).__name__` is
`builtin_function_or_method` rather than `function` (a type-valued builtin such as `bool` still
says `type`). The comparison errors from max/min now use the source comparison direction
(`'>' not supported ...` for max), matching CPython.

The other two rbpre183 items (tuple members through an untyped wrapper parameter and a
module-level rebinding of a builtin name) already matched CPython on this tree and are not
changed here.
"""
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent

MAXMIN_VALUE = r'''MAX_ALIAS = max
MIN_ALIAS = min


def relay(f, x: int, y: int) -> int:
    return f(x, y)


def lone(f, xs: list) -> int:
    return f(xs)


def get_max():
    return max


def get_min():
    return min


def use_default(g=max) -> int:
    return g([4, 1])


def outer() -> int:
    f = min
    def inner() -> int:
        return f(4, 1)
    return inner()


def show(tag: str, f) -> None:
    try:
        print(tag, f())
    except Exception as e:
        print(tag, type(e).__name__, str(e))


def main() -> None:
    m = max
    n = min
    xs = [max, min]
    d = {"max": max, "min": min}
    print("lit", max(3, 1), min(3, 1))
    print("var", m(3, 1), n(3, 1))
    print("arg", relay(max, 3, 1), relay(min, 3, 1))
    print("list", xs[0](3, 1), xs[1](3, 1), xs[0]([3, 1]), xs[1]([3, 1]))
    print("dict", d["max"](3, 1), d["min"](3, 1), d["max"]([3, 1]), d["min"]([3, 1]))
    print("return", get_max()(3, 1), get_min()(3, 1), get_max()([3, 1]), get_min()([3, 1]))
    print("alias", MAX_ALIAS(4, 1), MIN_ALIAS([4, 1]))
    print("default", use_default(), use_default(min))
    print("closure", outer())
    print("three", max(3, 1, 2), min(3, 1, 2))
    print("lone", lone(max, [3, 1]), lone(min, [3, 1]))
    print("lone-str", max("cab"), min("cab"))
    print("lone-range", max(range(3)), min(range(3)))
    print("lone-dict", max({"b": 1, "a": 2}), min({"b": 1, "a": 2}))
    print("lone-set", max({3, 1}), min({3, 1}))
    print("mixed", max(1, 2.5), min(1, 2.5), max(False, True), min(False, True))
    nan = float("nan")
    print("nan", max(1.0, nan), min(1.0, nan), max([1.0, nan]), min([nan, 1.0]))
    print("setargs", max({1}, {2}), min({1}, {2}), max({1, 2}, {2, 3}), min([{1}, {2}]))
    print("repeat", max(2, 2, 1), min(2, 2, 1))
    print("containers", max([1, 2], [3]), min([1, 2], [3]), max((1, 2), (3,)), min((1, 2), (3,)))
    show("noargs-max", lambda: m())
    show("noargs-min", lambda: n())
    show("empty-max", lambda: m([]))
    show("empty-min", lambda: n([]))
    show("noniter-max", lambda: m(3))
    show("noniter-min", lambda: n(3))
    show("badcmp-max", lambda: m(1, "a"))
    show("badcmp-min", lambda: n(1, "a"))
    show("baditer-max", lambda: m([1, "a"]))
    show("baditer-min", lambda: n([1, "a"]))
    show("plus", lambda: 1 + max)
    show("in-str", lambda: max in "abc")
    print("names", type(max).__name__, type(min).__name__, type(len).__name__,
          type(callable).__name__, type(bool).__name__)
    print("done")


main()
'''

FIXED_VALUE_BUILTINS = r'''xs = [callable, hash]
d = {"callable": callable, "hash": hash}


def relay(f, x: int) -> bool:
    return f(x)


def get_callable():
    return callable


def get_hash():
    return hash


def main() -> None:
    c = callable
    h = hash
    print("callable", c(len), c(max), c(1), c("x"), c([]), relay(callable, max), xs[0](min),
          d["callable"](len), get_callable()(max))
    print("hash", h("abc") == hash("abc"), h(123) == hash(123), relay(hash, 123) == hash(123),
          xs[1]("x") == hash("x"), d["hash"](123) == hash(123), get_hash()("abc") == hash("abc"))
    try:
        print("abc".startswith((max,)))
    except TypeError as e:
        print("tuple-max", type(e).__name__, str(e))
    try:
        print("abc".endswith((min,)))
    except TypeError as e:
        print("tuple-min", type(e).__name__, str(e))
    try:
        print("abc".startswith((callable,)))
    except TypeError as e:
        print("tuple-callable", type(e).__name__, str(e))
    try:
        print("abc".endswith((hash,)))
    except TypeError as e:
        print("tuple-hash", type(e).__name__, str(e))
    print("names", type(callable).__name__, type(hash).__name__, type(max).__name__,
          type(min).__name__)
    print("done")


main()
'''


def _cpython(directory, name, text):
    src = Path(directory) / (name + '_cpython.py')
    src.write_text(text, encoding='utf-8')
    done = subprocess.run([sys.executable, '-B', str(src)], capture_output=True, timeout=120,
                          env=dict(os.environ, PYTHONUTF8='1'))
    return done.stdout.replace(b'\r\n', b'\n'), done.returncode, done.stderr


def _build_and_run(directory, name, text, general):
    src = Path(directory) / (name + '.ail')
    src.write_text(text, encoding='utf-8')
    exe = Path(directory) / ('exe_' + name + ('_g' if general else '_d'))
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


class Pre252Tests(unittest.TestCase):
    def check(self, slug, text):
        with tempfile.TemporaryDirectory(prefix='ail-pre252-') as directory:
            want, rc, err = _cpython(directory, slug, text)
            self.assertEqual(rc, 0, err)
            for general in (True, False):
                got, build_err = _build_and_run(directory, '%s_%s' % (slug, 'g' if general else 'd'),
                                                text, general)
                self.assertIsNotNone(got, '%s (general=%s)\n%s' % (text[:2000], general, build_err))
                self.assertEqual(got, (want, rc), '%s (general=%s)\n%s' % (text[:2000], general, build_err))

    def test_max_min_as_values(self):
        self.check('maxmin_value', MAXMIN_VALUE)

    def test_callable_and_hash_as_values(self):
        self.check('fixed_value_builtins', FIXED_VALUE_BUILTINS)


if __name__ == '__main__':
    unittest.main()

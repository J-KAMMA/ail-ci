"""Differential round 56: a @contextmanager that replaces an exception with a new one.

Found with small programs compared against CPython on both builds:

`contextlib.contextmanager` passes an exception raised in the body into the generator
with `send`. When the generator caught it and raised a *new* exception with the same
class name and the same message, `_AilGenCM.__exit__` (prelude_with.py) treated the
new exception as the one it had sent, returned false, and the `with` re-raised the
original object. CPython compares the exception objects themselves: only the object
that was sent suppresses, so the replacement propagated. A program that keeps the
original exception and prints `e is orig` saw `True` where CPython prints `False`;
the same happened for the exception's attributes and across a nested `with`.

The fix is to compare `e2 is exc`, as CPython's `_GeneratorContextManager.__exit__`
does. Re-raising the same object (bare `raise`) still returns false, and a new
exception of another type or message still propagates. The programs below also keep
an ordinary manager's `__exit__` suppression and the other ways in compared.
"""
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent

REPLACEMENT = r'''from contextlib import contextmanager


class E(Exception):
    def __init__(self, msg: str, tag: int) -> None:
        super().__init__(msg)
        self.tag = tag


@contextmanager
def cm(mode: str):
    try:
        yield
    except E as e:
        print("gen", mode, e.tag)
        if mode == "same_object":
            raise
        if mode == "new_same":
            raise E(str(e), 2)
        if mode == "new_other":
            raise E("other", 3)
        if mode == "other_type":
            raise KeyError(str(e))
        if mode == "yield_again":
            yield 2
        raise


def run(mode: str) -> None:
    orig = E("same", 1)
    try:
        with cm(mode):
            print("body", mode)
            raise orig
    except E as e:
        print("E", e is orig, e.tag, str(e))
    except KeyError as e:
        print("KeyError", str(e))
    except RuntimeError as e:
        print("RuntimeError", str(e))


def main() -> None:
    for mode in ["same_object", "new_same", "new_other", "other_type", "yield_again"]:
        run(mode)
    print("done")


main()
'''

SOURCES = r'''from contextlib import contextmanager


class E(Exception):
    pass


class Holder:
    def __init__(self) -> None:
        self.err = E("attr")
        self.mode = True


@contextmanager
def cm(mode: bool):
    try:
        yield
    except E as e:
        print("gen", str(e))
        if mode:
            raise E("new")
        raise


def via_arg(err: E, mode: bool) -> None:
    try:
        with cm(mode):
            raise err
    except E as e:
        print("arg", e is err, str(e))


def main() -> None:
    h = Holder()
    via_arg(h.err, True)
    via_arg(h.err, False)
    via_arg(h.err, h.mode)
    d = {"err": E("dict"), "mode": False}
    via_arg(d["err"], d["mode"])
    xs = [E("list"), True]
    try:
        with cm(xs[1]):
            raise xs[0]
    except E as e:
        print("list", e is xs[0], str(e))
    print("done")


main()
'''

NESTED = r'''from contextlib import contextmanager


class E(Exception):
    def __init__(self, msg: str, tag: int) -> None:
        super().__init__(msg)
        self.tag = tag


@contextmanager
def replace(tag: int):
    try:
        yield
    except E as e:
        print("inner", e.tag)
        raise E("new", tag)


@contextmanager
def observe(label: str):
    try:
        yield
    except E as e:
        print("outer", label, e.tag)
        raise


def raiser(box: list) -> None:
    raise box[0]


def main() -> None:
    orig = E("same", 1)
    box = [orig]
    try:
        with observe("a"):
            with replace(2):
                print("body")
                raiser(box)
    except E as e:
        print("caught", e is orig, e.tag, str(e))
    print("done")


main()
'''

CUSTOM_MANAGER = r'''class C:
    def __init__(self, name: str, swallow) -> None:
        self.name = name
        self.swallow = swallow

    def __enter__(self):
        print("enter", self.name)
        return self.name

    def __exit__(self, et, e, tb):
        print("exit", self.name, et is None, e)
        return self.swallow


def main() -> None:
    with C("a", False) as x:
        print("body", x)
    try:
        with C("b", True):
            print("body b")
            raise ValueError("swallowed")
        print("after b")
    except ValueError:
        print("escaped")
    for v in [False, True, 1, 0, "yes", "", [1], [], None, 2]:
        try:
            with C("v", v):
                raise KeyError("k")
        except KeyError:
            print("kept", repr(v))
        else:
            print("suppressed", repr(v))
    try:
        with C("outer", False):
            with C("inner", True):
                raise ValueError("inner")
            print("after inner")
            raise TypeError("outer")
    except TypeError as e:
        print("caught", e)
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


class Fuzz56Tests(unittest.TestCase):
    def check(self, slug, text, rc=0):
        with tempfile.TemporaryDirectory(prefix='ail-fuzz56-') as directory:
            want, got_rc, err = _cpython(directory, slug, text)
            self.assertEqual(got_rc, rc, err)
            for general in (True, False):
                got, build_err = _build_and_run(directory, '%s_%s' % (slug, 'g' if general else 'd'), text, general)
                self.assertIsNotNone(got, '%s (general=%s)\n%s' % (text[:2000], general, build_err))
                self.assertEqual(got, (want, rc), '%s (general=%s)\n%s' % (text[:2000], general, build_err))

    def test_replacement_identity_and_kind(self):
        self.check('replacement', REPLACEMENT)

    def test_replacement_exception_from_sources(self):
        self.check('sources', SOURCES)

    def test_replacement_through_nested_with(self):
        self.check('nested', NESTED)

    def test_custom_manager_suppression(self):
        self.check('custom_manager', CUSTOM_MANAGER)


if __name__ == '__main__':
    unittest.main()

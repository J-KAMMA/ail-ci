"""Silent differences found by differential fuzzing of exceptions (round 7), each compared with CPython.

1. `repr(e)` of a KeyError on the general (boxed) path showed the already-quoted message a second
   time: `KeyError("'k'")` where CPython prints `KeyError('k')` (the runtime builds a KeyError's
   message with repr(key), because CPython's str(e) is repr(args[0])). Fixes: cruntime's exception
   repr writes a KeyError's message as it is; safetyrt.patch_exc keeps that when it shows `args`.
2. `assert cond, 5` kept only the text of the message, so repr(e) was `AssertionError('5')` and
   e.args was `('5',)`. CPython's AssertionError holds the object: `AssertionError(5)`, `(5,)`.
   Fixes: pyfunc._assert_stmt builds AssertionError(msg) with the message object; pyboxed2 keeps
   it through ail2x_raise_builtin.

The last class is a guard: try/except/else/finally ordering, `with` and @contextmanager, nested
handlers and returns inside finally still agree with CPython on both builds.
"""
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def compile_source(directory, text, name, syntax='python', env=None):
    source, exe = Path(directory, name + '.ail'), Path(directory, name)
    source.write_text(text, encoding='utf-8')
    built = subprocess.run([sys.executable, '-B', str(ROOT / 'ail_chatgpt.py'), 'compile', source.name,
                            '--syntax', syntax, '-o', exe.name], cwd=directory, capture_output=True,
                           text=True, timeout=600, env=dict(os.environ, **(env or {})))
    return built, source, exe


def run_both(directory, text, name, env=None):
    """(compile result, AIL run, CPython run) of one def-syntax program."""
    built, source, exe = compile_source(directory, text, name, env=env)
    expected = subprocess.run([sys.executable, str(source)], capture_output=True, timeout=60)
    if built.returncode != 0:
        return built, None, expected
    return built, subprocess.run([str(exe)], capture_output=True, timeout=60), expected


# A KeyError raised with a string key, read as str(e) and repr(e) (no `.args` in the program: the
# message alone used to be all the value kept, and repr quoted it again).
KEYERROR_REPR = '''
def main() -> None:
    keys: list[str] = ["", "x", "a b", "q'uote", "back\\\\slash"]
    for k in keys:
        try:
            raise KeyError(k)
        except KeyError as e:
            print(str(e), repr(e))
    try:
        raise KeyError(-3)
    except KeyError as e:
        print(str(e), repr(e))
    try:
        raise KeyError((1, 2))
    except KeyError as e:
        print(str(e), repr(e))
    try:
        raise KeyError(None)
    except KeyError as e:
        print(str(e), repr(e))


main()
'''

# repr(e) of a KeyError from a missing dict key, and the same read through e.args (which is where the
# boxed path still only has the message; the repr half is what this test pins).
KEYERROR_DICT = '''
def main() -> None:
    d: dict[str, int] = {"a": 1}
    for k in ("a", "b", ""):
        try:
            v: int = d[k]
            print("hit", v)
        except KeyError as e:
            print("miss", str(e), repr(e))
    n: dict[int, int] = {1: 2}
    try:
        print(n[7])
    except KeyError as e:
        print(str(e), repr(e))


main()
'''

# a KeyError raised inside __exit__, and one re-raised out of a @contextmanager
KEYERROR_EXIT = '''
class CM:
    def __enter__(self) -> int:
        return 1
    def __exit__(self, t, v, tb) -> bool:
        raise KeyError("exit-raise")

def main() -> None:
    try:
        with CM():
            print("body")
    except KeyError as e:
        print(str(e), repr(e))


main()
'''

KEYERROR_CONTEXTMANAGER = '''
from contextlib import contextmanager

@contextmanager
def cm():
    print("enter")
    try:
        yield 1
    except KeyError as e:
        print("inner-key", str(e))
        raise
    finally:
        print("exit")

def main() -> None:
    try:
        with cm() as v:
            print("v", v)
            raise KeyError("kk")
    except KeyError as e:
        print("outer", str(e), repr(e))


main()
'''

# AssertionError keeps the message object: str(e), repr(e) and e.args
ASSERT_ARGS = '''
def main() -> None:
    for n in (5, -1, 0, 10 ** 6):
        try:
            assert n < 0, n
        except AssertionError as e:
            print(str(e), repr(e), len(e.args), e.args[0] + 1)
    try:
        assert False, "txt"
    except AssertionError as e:
        print(str(e), repr(e), e.args[0])
    try:
        assert 0, -0.5
    except AssertionError as e:
        print(str(e), repr(e), e.args[0])
    try:
        assert 0, True
    except AssertionError as e:
        print(str(e), repr(e), e.args[0])
    try:
        assert 0, None
    except AssertionError as e:
        print(str(e), repr(e), e.args[0] is None)
    try:
        assert 1 == 1, 99
        print("ok")
    except AssertionError:
        print("wrong")


main()
'''

# The guard programs: every one is CPython-identical on both builds.
GUARD = {
    'order': '''
def f(n: int) -> int:
    try:
        print("try", n)
        if n > 0:
            raise ValueError("positive")
        return 1
    except ValueError:
        print("except")
        return 2
    else:
        print("else")
        return 3
    finally:
        print("finally")

print(f(0))
print(f(5))
''',
    'finally_return': '''
def f(n: int) -> int:
    try:
        return n
    finally:
        print("fin")
        if n < 0:
            return -1

print(f(3))
print(f(-3))
''',
    'nested_handlers': '''
def main() -> None:
    try:
        try:
            raise ValueError("first")
        except ValueError:
            try:
                raise KeyError("second")
            except KeyError as k:
                print("inner", str(k))
                raise
            finally:
                print("fin-inner")
    except KeyError as e:
        print("outer key", str(e))

main()
''',
    'exception_in_finally': '''
def f(n: int) -> int:
    try:
        try:
            if n < 0:
                raise ValueError("neg")
            return n
        finally:
            if n == 0:
                raise KeyError("zero-fin")
    except KeyError as e:
        print("handled", str(e))
        return -1

print(f(5))
print(f(-2))
print(f(0))
''',
    'suppress': '''
class CM:
    def __init__(self, r: bool) -> None:
        self.r = r
    def __enter__(self) -> int:
        return 9
    def __exit__(self, t, v, tb) -> bool:
        return self.r

def main() -> None:
    for r in (True, False):
        try:
            with CM(r):
                raise ValueError("v")
            print("no exc", r)
        except ValueError as e:
            print("exc", r, str(e))
    try:
        with CM(False):
            with CM(True):
                raise KeyError("hidden")
            print("inner done")
    except KeyError as e:
        print("outer saw", str(e))

main()
''',
    'contextmanager': '''
from contextlib import contextmanager

@contextmanager
def cm(tag: str):
    print("open", tag)
    try:
        yield tag + "!"
    finally:
        print("close", tag)

def main() -> None:
    with cm("a") as v:
        print("in", v)
    try:
        with cm("b") as w:
            print("in", w)
            raise RuntimeError("bad")
    except RuntimeError as e:
        print("caught", str(e))

main()
''',
    'exit_raises': '''
class CM:
    def __enter__(self) -> int:
        return 1
    def __exit__(self, t, v, tb) -> bool:
        print("exit", t is None, str(v))
        raise RuntimeError("from exit")

def main() -> None:
    try:
        with CM():
            print("body")
            raise ValueError("orig")
    except RuntimeError as e:
        print("caught", str(e))

main()
''',
    'value_through_places': '''
class E(Exception):
    def __init__(self, msg: str, n: int) -> None:
        super().__init__(msg, n)
        self.n = n

def raise_arg(err: E) -> None:
    raise err

def main() -> None:
    xs: list[E] = [E("list", 1)]
    d: dict[str, E] = {"k": E("dict", -2)}
    for e in xs:
        try:
            raise_arg(e)
        except E as got:
            print(str(got), repr(got), got.args[0], got.n)
    try:
        raise d["k"]
    except E as got:
        print(str(got), repr(got), got.args[0], got.n)

main()
''',
    'args_types': '''
def main() -> None:
    try:
        raise ValueError()
    except ValueError as e:
        print("v", str(e), repr(e), len(e.args))
    try:
        raise ValueError(None)
    except ValueError as e:
        print("n", str(e), repr(e), len(e.args), e.args[0] is None)
    try:
        raise ValueError(True)
    except ValueError as e:
        print("b", str(e), repr(e), len(e.args))
    try:
        raise TypeError(-2)
    except TypeError as e:
        print("i", str(e), repr(e), len(e.args))
    try:
        raise ValueError("a" * 100)
    except ValueError as e:
        print(len(str(e)), len(e.args))

main()
''',
    'ranges': '''
def main() -> None:
    for n in (0, -1, 2):
        try:
            print(1 // n)
        except ZeroDivisionError as e:
            print("zde", str(e), repr(e), e.args[0])
    try:
        [1, 2][5]
    except IndexError as e:
        print("idx", str(e), repr(e))
    try:
        "abc"[9]
    except IndexError as e:
        print("sidx", str(e), repr(e))

main()
''',
    'with_return_break': '''
class CM:
    def __enter__(self) -> int:
        return 1
    def __exit__(self, t, v, tb) -> bool:
        print("exit", t is None, type(v).__name__ if v is not None else "-")
        return False

def f(n: int) -> str:
    with CM():
        if n == 0:
            return "returned"
        if n < 0:
            raise ValueError("neg")
    return "fell"

print(f(0))
print(f(1))
try:
    print(f(-1))
except ValueError as e:
    print("caught", str(e))
''',
}


class ExceptionFuzz7(unittest.TestCase):
    def same_as_cpython(self, text, name, env=None):
        with tempfile.TemporaryDirectory() as directory:
            built, ran, expected = run_both(directory, text, name, env)
            self.assertEqual(built.returncode, 0, built.stdout + built.stderr)
            self.assertEqual((ran.returncode, ran.stdout), (expected.returncode, expected.stdout), ran.stderr)

    def both_builds(self, text, name):
        self.same_as_cpython(text, name)
        self.same_as_cpython(text, name + '_general', {'AIL_UNIFIED_FORCE': '1'})

    def test_keyerror_repr(self):
        self.both_builds(KEYERROR_REPR, 'ke_repr')

    def test_keyerror_from_a_missing_dict_key(self):
        self.both_builds(KEYERROR_DICT, 'ke_dict')

    def test_keyerror_from_exit_and_contextmanager(self):
        self.both_builds(KEYERROR_EXIT, 'ke_exit')
        self.both_builds(KEYERROR_CONTEXTMANAGER, 'ke_cm')

    def test_assertion_error_keeps_its_message_object(self):
        self.both_builds(ASSERT_ARGS, 'assert_args')

    def test_ordering_and_context_managers_still_agree(self):
        for name, text in GUARD.items():
            with self.subTest(name):
                self.both_builds(text, name + '_guard')


if __name__ == '__main__':
    unittest.main()

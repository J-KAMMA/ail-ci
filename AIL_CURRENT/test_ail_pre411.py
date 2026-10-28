"""pre411: a non-int ``__index__`` result names CPython's TypeError on a subscript.

The pre397 review recorded as pre-existing that a list (and tuple/str) subscript whose key is an
instance whose ``__index__`` returns a non-int raised ``list indices must be integers or slices``
instead of CPython's ``__index__ returned non-int (type ...)``.  The general path called
``__index__`` and then used the result without checking it.  It now validates the result, and an
IntEnum/IntFlag member is used by its value as CPython's int-subclass fast path does: a direct
member ignores an overridden ``__index__``, and a ``__index__`` result that is another member is
accepted by its value (one-level unwrap).

The key reaches the subscript directly, through an argument, a list item, an attribute and a dict
value; the program covers every non-int result kind, a bool result, negatives, an overridden
IntEnum member, a nested member chain and an IntEnum/IntFlag result.  Both builds must match
CPython's stdout and exit status.
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
                          env=dict(os.environ, PYTHONUTF8='1', PYTHONWARNINGS='ignore'))
    return done.stdout.replace(b'\r\n', b'\n'), done.returncode


def _build_run(directory, name, text, general):
    src = Path(directory) / name
    src.write_text(text, encoding='utf-8')
    exe = Path(directory) / ('exe_' + name + ('_g' if general else '_d'))
    env = dict(os.environ, AIL_NO_CACHE='1', AIL_QUIET_FALLBACK='1')
    env.pop('AIL_NO_GENERAL', None)
    if general:
        env['AIL_UNIFIED_FORCE'] = '1'
    else:
        env.pop('AIL_UNIFIED_FORCE', None)
    built = subprocess.run([sys.executable, '-B', CHATGPT, 'compile', src.name, '--syntax', 'python',
                            '-o', exe.name], cwd=directory, capture_output=True, text=True, timeout=900,
                           env=env)
    if built.returncode != 0:
        return None, (built.stdout + built.stderr)[-1500:]
    got = subprocess.run([str(exe)], capture_output=True, timeout=120, cwd=directory)
    return (got.stdout.replace(b'\r\n', b'\n'), got.returncode), None


PROGRAM = r'''from enum import IntEnum, IntFlag


class BadStr:
    def __index__(self):
        return "x"


class BadFloat:
    def __index__(self):
        return 1.5


class BadNone:
    def __index__(self):
        return None


class BadList:
    def __index__(self):
        return [1]


class BadBool:
    def __index__(self):
        return True


class Good:
    def __init__(self, v):
        self.v = v

    def __index__(self):
        return self.v


class Box:
    def __init__(self, v):
        self.v = v


class C(IntEnum):
    ONE = 1

    def __index__(self):
        return 1


class B(IntEnum):
    ONE = 1

    def __index__(self):
        return C.ONE


class A(IntEnum):
    ONE = 1

    def __index__(self):
        return B.ONE


class ZTwo(IntEnum):
    ONE = 1

    def __index__(self):
        return 2


class ZBad(IntEnum):
    ONE = 1

    def __index__(self):
        return "x"


class F(IntFlag):
    ONE = 1


class Chain:
    def __index__(self):
        return B.ONE


class ChainFlag:
    def __index__(self):
        return F.ONE


class ChainBad:
    def __index__(self):
        return Box(1)


def show(label, f):
    try:
        print(label, f())
    except Exception as e:
        print(label, type(e).__name__, str(e))


def main():
    xs = [10, 20, 30]
    t = (10, 20, 30)
    s = "abc"
    d = {"k": BadStr()}
    box = Box(BadFloat())
    for label, bad in (("str", BadStr()), ("float", BadFloat()), ("none", BadNone()),
                       ("list", BadList()), ("arg", d["k"]), ("attr", box.v),
                       ("item", [BadList()][0])):
        show("list " + label, lambda: xs[bad])
        show("tuple " + label, lambda: t[bad])
        show("str " + label, lambda: s[bad])
    show("bool-return", lambda: xs[BadBool()])
    show("good", lambda: xs[Good(1)])
    show("good-neg", lambda: xs[Good(-1)])
    show("good-arg", lambda: xs[Good(2)])
    show("intenum-direct", lambda: xs[ZTwo.ONE])
    show("intenum-bad", lambda: xs[ZBad.ONE])
    show("intflag-direct", lambda: xs[F.ONE])
    show("chain", lambda: xs[Chain()])
    show("chain-string", lambda: s[Chain()])
    show("chain-flag", lambda: xs[ChainFlag()])
    show("chain-bad", lambda: xs[ChainBad()])
    show("nested-A", lambda: xs[A.ONE])
    print("done")


main()
'''


@unittest.skipUnless(HAVE_CC, 'gcc is required')
class IndexResultTypeError(unittest.TestCase):
    def check(self, mode):
        with tempfile.TemporaryDirectory(prefix='ail-pre411-') as directory:
            want = _cpython(directory, 'index', PROGRAM)
            got, error = _build_run(directory, 'index.ail', PROGRAM, mode)
            self.assertIsNone(error, error)
            self.assertEqual(got, want)

    def test_general(self):
        self.check('general')

    def test_default(self):
        self.check('default')


if __name__ == '__main__':
    unittest.main()

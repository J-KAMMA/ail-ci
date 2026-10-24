"""slice bound conversion through __index__ against CPython 3.12 (DIFFERENCES job-pre71).

`_PyEval_SliceIndexNotNone` accepts an int, a bool or an instance whose `__index__` answers an
int; a plain class attribute (`__index__ = 5`) is looked up and then called, so CPython raises
TypeError "'int' object is not callable" before any bound is applied.  The general path used to
read a non-int bound through the boxed value's `.i` (a garbage index for str/list/tuple, often an
empty result) or raise the generic slice-index TypeError.  It now converts every bound at run
time, in PySlice_Unpack's order (step, then start, then stop) and checks a zero step before the
remaining bounds, for reads, slice assignment/deletion and slice.indices.

Each program is built with the general path forced and with the default build; stdout, the exit
status and the last stderr line must equal CPython's.
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


def _last_line(err):
    lines = [x for x in err.decode('utf-8', 'replace').splitlines() if x.strip() and 'raised near' not in x]
    return lines[-1] if lines else ''


def _cpython(directory, name, text):
    src = Path(directory) / (name + '_cpython.py')
    src.write_text(text, encoding='utf-8')
    done = subprocess.run([sys.executable, '-B', str(src)], capture_output=True, timeout=120,
                          env=dict(os.environ, PYTHONUTF8='1', PYTHONWARNINGS='ignore'))
    return done.stdout.replace(b'\r\n', b'\n'), done.returncode, _last_line(done.stderr)


def _build_run(directory, name, text, mode):
    src = Path(directory) / (name + '_' + mode + '.ail')
    src.write_text(text, encoding='utf-8')
    exe = Path(directory) / ('exe_' + name + '_' + mode)
    env = dict(os.environ, AIL_NO_CACHE='1', AIL_QUIET_FALLBACK='1')
    env.pop('AIL_NO_GENERAL', None)
    env.pop('AIL_UNIFIED_FORCE', None)
    if mode == 'general':
        env['AIL_UNIFIED_FORCE'] = '1'
    cmd = [sys.executable, '-B', CHATGPT, 'compile', src.name, '--syntax', 'python', '-o', exe.name]
    built = subprocess.run(cmd, cwd=directory, capture_output=True, text=True, timeout=900, env=env)
    if built.returncode != 0:
        return None, (built.stdout + built.stderr)[-1500:]
    got = subprocess.run([str(exe)], capture_output=True, timeout=120, cwd=directory)
    return (got.stdout.replace(b'\r\n', b'\n'), got.returncode, _last_line(got.stderr)), None


PROGRAM = r'''class NonCallableInt:
    __index__ = 5


class NonCallableStr:
    __index__ = "x"


class NonCallableFloat:
    __index__ = 1.5


class NonCallableNone:
    __index__ = None


class NonCallableList:
    __index__ = [1]


class CallableIndex:
    def __index__(self):
        return 2


class BadReturn:
    def __index__(self):
        return "x"


class Boom:
    def __index__(self):
        raise ValueError("boom")


class Plain:
    pass


class Box:
    def __init__(self, lo, hi):
        self.lo = lo
        self.hi = hi


S = "abcdef"
XS = [10, 20, 30, 40, 50, 60]
T = (10, 20, 30, 40, 50, 60)
B = b"abcdef"
BA = bytearray(b"abcdef")


def show(label, recv, lo, hi):
    try:
        print(label, recv[lo:hi])
    except Exception as e:
        print(label, type(e).__name__, str(e))


def show3(label, recv, lo, hi, st):
    try:
        print(label, recv[lo:hi:st])
    except Exception as e:
        print(label, type(e).__name__, str(e))


def show_indices(label, sl, n):
    try:
        print(label, sl.indices(n))
    except Exception as e:
        print(label, type(e).__name__, str(e))


def note(tag, value):
    print("eval", tag)
    return value


def main() -> None:
    for name, recv in (("str", S), ("list", XS), ("tuple", T)):
        show(name + "-lo", recv, NonCallableInt(), 2)
        show(name + "-hi", recv, 2, NonCallableInt())
        show(name + "-both", recv, NonCallableInt(), NonCallableInt())
    show3("step-attr", S, 0, 6, NonCallableInt())
    show("bytes-attr", B, NonCallableInt(), 2)
    show("bytearray-attr", BA, NonCallableInt(), 2)

    show("float-attr", S, NonCallableFloat(), 2)
    show("str-attr", S, NonCallableStr(), 2)
    show("none-attr", S, NonCallableNone(), 2)
    show("list-attr", S, NonCallableList(), 2)

    show("callable", S, CallableIndex(), 5)
    show("callable-hi", S, 1, CallableIndex())
    show3("callable-step", S, 0, 6, CallableIndex())
    show("callable-list", XS, CallableIndex(), 5)
    show("bad-return", S, BadReturn(), 5)
    show("boom", S, Boom(), 5)
    show("plain", S, Plain(), 5)

    box = Box(NonCallableInt(), 2)
    show("attr", S, box.lo, box.hi)
    items = [NonCallableInt(), 2]
    show("item", S, items[0], items[1])
    d = {"lo": NonCallableInt(), "hi": 2}
    show("dict", S, d["lo"], d["hi"])

    ys = [0, 1, 2, 3]
    try:
        ys[NonCallableInt():2] = [9]
    except Exception as e:
        print("assign-attr", type(e).__name__, str(e))
    print("assign-attr-state", ys)
    zs = [0, 1, 2, 3]
    zs[CallableIndex():2] = [9]
    print("assign-callable", zs)
    ws = [0, 1, 2, 3]
    try:
        del ws[NonCallableInt():]
    except Exception as e:
        print("delete-attr", type(e).__name__, str(e))
    print("delete-attr-state", ws)

    show_indices("indices-attr", slice(NonCallableInt(), 4, None), 6)
    show_indices("indices-method", slice(CallableIndex(), 4, None), 6)

    try:
        print("order-lo", S[note("lo", NonCallableInt()):note("hi", 2.0):note("step", 1)])
    except Exception as e:
        print("order-lo", type(e).__name__, str(e))
    try:
        print("order-zero-step", S[note("lo2", 1):note("hi2", NonCallableInt()):note("step2", 0)])
    except Exception as e:
        print("order-zero-step", type(e).__name__, str(e))


main()
'''


@unittest.skipUnless(HAVE_CC, 'gcc is required')
class SliceIndexProtocol(unittest.TestCase):
    def check(self, name, text, modes=('general', 'default')):
        with tempfile.TemporaryDirectory(prefix='ail-pre71-') as directory:
            want = _cpython(directory, name, text)
            for mode in modes:
                got, error = _build_run(directory, name, text, mode)
                self.assertIsNone(error, '%s %s: %s' % (name, mode, error))
                self.assertEqual(got, want, '%s %s' % (name, mode))

    def test_non_callable_and_callable_slice_bounds(self):
        self.check('bounds', PROGRAM)


if __name__ == '__main__':
    unittest.main()

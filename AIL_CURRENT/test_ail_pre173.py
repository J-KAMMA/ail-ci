"""bytes/bytearray start/end bounds against CPython 3.12 (job pre173).

The general path's bytes methods took the optional start/end arguments straight from the boxed
value's `.i` field, so a str, a float or None was read as an index instead of raising CPython's
TypeError.  CPython converts each bound with _PyEval_SliceIndex: an int, a bool or an object with
__index__ is an index; None, a float, a str and anything else raise
TypeError("slice indices must be integers or None or have an __index__ method"), and a bad
__index__ return is "__index__ returned non-int (type ...)".  The bounds of find, rfind, count,
index, rindex, startswith and endswith are converted through one C primitive (safetyrt.py) that
uses the general path's __index__ dispatch, so the value may reach the call through a variable, a
list item, an attribute or a dict value.

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


PROGRAM = r'''class Ix:
    def __init__(self, v):
        self.v = v

    def __index__(self):
        return self.v


class BadIx:
    def __index__(self):
        return "x"


class IntOnly:
    def __int__(self):
        return 1


class Both:
    def __index__(self):
        return 1

    def __int__(self):
        return 3


class Box:
    def __init__(self, lo, hi):
        self.lo = lo
        self.hi = hi


def call(name: str, data, sub, lo, hi):
    if name == "find":
        return data.find(sub, lo, hi)
    if name == "rfind":
        return data.rfind(sub, lo, hi)
    if name == "count":
        return data.count(sub, lo, hi)
    if name == "index":
        return data.index(sub, lo, hi)
    if name == "rindex":
        return data.rindex(sub, lo, hi)
    if name == "startswith":
        return data.startswith(sub, lo, hi)
    return data.endswith(sub, lo, hi)


def show(label: str, f) -> None:
    try:
        print(label, f())
    except Exception as e:
        print(label, type(e).__name__, str(e))


def main() -> None:
    data = b"abcabc"
    bounds = (None, 0, 1, 6, 7, -1, -6, -7, True, False, 2 ** 40, -(2 ** 40),
              1.0, "1", b"1", [1], Ix(1), Ix(2), Ix(-2), Ix(99), BadIx(), IntOnly(), Both())
    for name in ("find", "rfind", "count", "index", "rindex", "startswith", "endswith"):
        k = 0
        for bound in bounds:
            show(name + " start b" + str(k), lambda: call(name, data, b"a", bound, None))
            show(name + " end b" + str(k), lambda: call(name, data, b"a", 0, bound))
            k += 1
    for name in ("find", "rfind", "count", "index", "rindex"):
        k = 0
        for bound in (None, 0, -1, 3, -3, 10, -10, True, False, 1.0, "1", Ix(0), Ix(3), Ix(-3), BadIx()):
            show("empty-sub " + name + " b" + str(k), lambda: call(name, b"", b"", bound, None))
            show("empty-sub2 " + name + " b" + str(k), lambda: call(name, b"abc", b"", bound, None))
            k += 1
    a = bytearray(b"abcabc")
    for name in ("find", "rfind", "count", "index", "rindex", "startswith", "endswith"):
        k = 0
        for bound in (None, 1, -1, 9, -9, 1.5, Ix(2), BadIx()):
            show("ba " + name + " b" + str(k), lambda: call(name, a, b"a", bound, None))
            show("ba " + name + " end b" + str(k), lambda: call(name, a, b"a", 0, bound))
            k += 1
    box = Box(1, 4)
    vals = [None, 2, "x", 1.5]
    d = {"lo": Ix(2), "hi": Ix(5)}
    d2 = {"lo": "x", "hi": 4}
    for label, lo, hi in (("direct", 1, 4), ("arg", vals[1], vals[2]), ("list", vals[0], vals[3]),
                          ("attr", box.lo, box.hi), ("dict", d["lo"], d["hi"]),
                          ("dictbad", d2["lo"], d2["hi"]), ("none", None, None),
                          ("neg", -2, -1), ("empty", 3, 3)):
        for name in ("find", "rfind", "count", "index", "rindex", "startswith", "endswith"):
            show(label + " " + name, lambda: call(name, b"abcabc", b"a", lo, hi))


main()
'''


@unittest.skipUnless(HAVE_CC, 'gcc is required')
class BytesBounds(unittest.TestCase):
    def check(self, mode):
        with tempfile.TemporaryDirectory(prefix='ail-pre173-') as d:
            want = _cpython(d, 'bounds', PROGRAM)
            got, error = _build_run(d, 'bounds', PROGRAM, mode)
            self.assertIsNone(error, error)
            self.assertEqual(got, want)


    def test_general(self):
        self.check('general')

    def test_default(self):
        self.check('default')


if __name__ == '__main__':
    unittest.main()

"""Differential fuzz round 81: KeyError arguments and the exception hierarchy, against CPython.

Found with small programs compared against CPython on both builds:

A KeyError raised by the runtime itself (a missing dict key in `d[k]`, `d.pop`, `del d[k]`,
`popitem`, `set.remove`, `set.pop`) carried `repr(key)` as its message and, through the
general path's `args` fallback, as its argument. CPython keeps the raw key: `str(e)` is
`repr(key)`, `repr(e)` is `KeyError(repr-key)` and `e.args` is `(key,)`. A missing `"x"`
therefore printed `e.args` as `("'x'",)` instead of `('x',)`, and an `int` key `5` printed
`repr(e)` as `KeyError('5')` instead of `KeyError(5)`. The runtime now raises those through
`ail_raise_key`, which stores the key as the argument; explicit `raise KeyError(...)` already
did.

The hierarchy programs below (custom bases, `except` tuples, subclass-before-base order and
`except Exception`) stay compared with CPython. `LookupError` and `ArithmeticError` are still
refused by name (not in the caught-exception subset), so they are not used here.
"""
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent

KEY_ERRORS = r'''class Holder:
    def __init__(self):
        self.d = {}


def take_get(d, k):
    return d[k]


def take_pop(d, k):
    return d.pop(k)


def take_del(d, k):
    del d[k]


def take_remove(s, k):
    s.remove(k)


def report(label, e):
    print(label, str(e), repr(e), e.args, type(e).__name__,
          isinstance(e, KeyError), isinstance(e, Exception))


def probe_get(d, k, label):
    try:
        take_get(d, k)
    except KeyError as e:
        report(label, e)


def probe_pop(d, k, label):
    try:
        take_pop(d, k)
    except KeyError as e:
        report(label, e)


def probe_del(d, k, label):
    try:
        take_del(d, k)
    except KeyError as e:
        report(label, e)


def probe_remove(s, k, label):
    try:
        take_remove(s, k)
    except KeyError as e:
        report(label, e)


def probe_set_pop(s, label):
    try:
        s.pop()
    except KeyError as e:
        report(label, e)


def main():
    vals = ["", "it's", 0, -42, 2 ** 62, (1, 2), True, None]
    for i in range(len(vals)):
        k = vals[i]
        d = {k: 1}
        probe_get(d, "missing", "get" + str(i))
        probe_pop(d, "missing", "pop" + str(i))
        probe_del(d, "missing", "del" + str(i))
        probe_remove({k}, "missing", "remove" + str(i))
    try:
        {}.popitem()
    except KeyError as e:
        report("popitem", e)
    probe_set_pop(set(), "setpop")
    box = [{1: 2}]
    h = Holder()
    h.d = {"a": 1}
    probe_get(box[0], "z", "listitem")
    probe_get(h.d, "z", "attribute")
    probe_get({"inner": {}}["inner"], "z", "dictvalue")
    probe_get(box[0], "", "emptykey")
    print("done")


main()
'''

HIERARCHY = r'''class AppError(Exception):
    pass


class SubError(AppError):
    pass


class LeafError(SubError):
    pass


def classify(kind):
    try:
        if kind == 0:
            raise AppError("app")
        if kind == 1:
            raise SubError("sub")
        if kind == 2:
            raise LeafError("leaf")
        if kind == 3:
            raise ValueError("value")
        if kind == 4:
            return {}["k"]
        if kind == 5:
            return [0][2]
        raise KeyError("key")
    except (KeyError, IndexError) as e:
        print("tuple", kind, type(e).__name__, str(e), repr(e), e.args)
    except LeafError as e:
        print("leaf", kind, e.args, isinstance(e, SubError), isinstance(e, AppError))
    except SubError as e:
        print("sub", kind, e.args, isinstance(e, AppError))
    except AppError as e:
        print("app", kind, e.args)
    except Exception as e:
        print("exception", kind, type(e).__name__, e.args)
    else:
        print("else", kind)
    finally:
        print("finally", kind)


def tuples(kind):
    try:
        if kind == 0:
            raise SubError("s")
        if kind == 1:
            raise ValueError("v")
        if kind == 2:
            raise AppError("a")
        raise TypeError("t")
    except (SubError, ValueError) as e:
        print("sv", kind, type(e).__name__, e.args)
    except AppError as e:
        print("app-tuple", kind, type(e).__name__, e.args)
    except Exception as e:
        print("other", kind, type(e).__name__, e.args)


def any_exception(kind):
    try:
        if kind == 0:
            raise LeafError("l")
        if kind == 1:
            return {}["missing"]
        {}.popitem()
    except Exception as e:
        print("any", kind, type(e).__name__, e.args)


def main():
    for i in range(7):
        classify(i)
    for i in range(4):
        tuples(i)
    for i in range(3):
        any_exception(i)
    print(type(LeafError("x")).__name__, isinstance(LeafError("x"), AppError),
          isinstance(LeafError("x"), Exception))
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


class Fuzz81Tests(unittest.TestCase):
    def check(self, slug, text, rc=0):
        with tempfile.TemporaryDirectory(prefix='ail-fuzz81-') as directory:
            want, got_rc, err = _cpython(directory, slug, text)
            self.assertEqual(got_rc, rc, err)
            for general in (True, False):
                got, build_err = _build_and_run(directory, '%s_%s' % (slug, 'g' if general else 'd'), text, general)
                self.assertIsNotNone(got, '%s (general=%s)\n%s' % (text[:2000], general, build_err))
                self.assertEqual(got, (want, rc), '%s (general=%s)\n%s' % (text[:2000], general, build_err))

    def test_key_error_arguments(self):
        self.check('key_errors', KEY_ERRORS)

    def test_exception_hierarchy_and_tuples(self):
        self.check('hierarchy', HIERARCHY)


if __name__ == '__main__':
    unittest.main()

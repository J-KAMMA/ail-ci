"""pre196: repr()/str() of a user class value must name the class.

The review of job rbpre170 recorded a pre-existing difference: `repr(C)` for a user class
printed `<object>` where CPython prints `<class '__main__.C'>` (and `str()`/`print()` use
the same text).  The v2 runtime's repr writer had no AIL_T_CLASS case, so every class value
fell through to the `<object>` default.  It now writes CPython's class repr for user classes
and `<class 'Name'>` for the builtin exception classes the runtime owns.

The cases below reach a class value directly, through an alias, an argument, a list item, a
dict value, an attribute, a return value, a container, an f-string and %-formatting, on both
builds.
"""
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent

CLASS_REPR = r'''class C:
    pass


class D(C):
    x = 1


class E:
    def __repr__(self):
        return "E()"


class Box:
    def __init__(self, v):
        self.v = v


def show(v):
    return repr(v)


A = C
xs = [C, D]
d = {"c": D}
b = Box(C)
print(repr(C), repr(D), repr(A), repr(xs[0]), repr(xs[1]), repr(d["c"]), repr(b.v))
print(repr(show(C)), repr(show(D)), repr(show(E)))
print(str(C), str(D), str(A), str(xs[1]), str(d["c"]), str(b.v))
print(C, D, b.v)
print(f"{C!r} {C!s} {C} {D!r}")
print("%r %s %r" % (C, D, b.v))
print(repr([C, D, A]), repr((C,)), repr({"c": C}))
print(repr(C.__name__), D.__name__, b.v.__name__, getattr(C, "__name__"))
print(repr(E()), repr(E.__name__))


class Empty:
    pass


print(repr(Empty), str(Empty), Empty.__name__)


class _Under:
    pass


print(repr(_Under))
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


class Pre196Tests(unittest.TestCase):
    def check(self, slug, text):
        with tempfile.TemporaryDirectory(prefix='ail-pre196-') as directory:
            want, rc, err = _cpython(directory, slug, text)
            self.assertEqual(rc, 0, err)
            for general in (True, False):
                got, build_err = _build_and_run(directory, '%s_%s' % (slug, 'g' if general else 'd'),
                                                text, general)
                self.assertIsNotNone(got, '%s (general=%s)\n%s' % (text[:2000], general, build_err))
                self.assertEqual(got, (want, rc), '%s (general=%s)\n%s' % (text[:2000], general, build_err))

    def test_class_repr(self):
        self.check('class_repr', CLASS_REPR)


if __name__ == '__main__':
    unittest.main()

"""Pre-197: `__exit__` sees a non-None third argument when the `with` body raised.

The review of job pre181 left `C?-job-pre181-10251538-2` open: the third argument of
`__exit__` was always None, so `tb is None` printed True even for a body that raised,
where CPython passes the active traceback.  AIL has no traceback objects, so the general
path now passes a non-None stand-in and both paths answer `tb is None` / `tb is not None`
(and `==` / `!=` against None) from whether the body raised; any other use of the
tb parameter is refused by name at compile time.  The typed path maps the test to its
exception code instead of folding it to a constant.

The cases below cover a clean body, an exception, a suppressed exception, a returning
body, `break`/`continue`, nested managers, a `@contextmanager` generator, and managers
reaching the `with` through an argument, a list item, an attribute and a dict value, on
both builds.  The refusal covers `type(tb)`, truthiness and passing `tb` to a helper.
"""
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent
CLI = str(ROOT / "ail_chatgpt.py")

PROGRAM = r'''from contextlib import contextmanager


class CM:
    def __init__(self, tag: str) -> None:
        self.tag = tag

    def __enter__(self) -> "CM":
        return self

    def __exit__(self, et, ev, tb) -> bool:
        print("exit", self.tag, et.__name__ if et is not None else None,
              tb is None, tb is not None, tb == None, tb != None)
        return True


class Strict:
    def __enter__(self) -> "Strict":
        return self

    def __exit__(self, et, ev, tb) -> bool:
        print("strict", et.__name__ if et is not None else None, tb is None, tb is not None)
        return False


class Box:
    def __init__(self, m):
        self.m = m


def use(m, mode, label):
    with m:
        print("body", label)
        if mode == 1:
            raise ValueError(label)
        if mode == 2:
            return "ret-" + label
        if mode == 3:
            raise KeyError(label)


def via_arg(m):
    use(m, 1, "arg-raise")
    use(m, 0, "arg-clean")
    use(m, 2, "arg-return")


def via_attr(box):
    use(box.m, 3, "attr")


def via_list(xs):
    use(xs[0], 0, "list-clean")
    use(xs[1], 1, "list-raise")


def via_dict(d):
    use(d["m"], 3, "dict")


def loops():
    for i in range(3):
        with CM("loop") as m:
            if i == 1:
                continue
            if i == 2:
                break
            print("loop", i, m.tag)


def nested():
    try:
        with CM("outer"):
            with Strict():
                raise ValueError("nested")
    except Exception as e:
        print("nested caught", type(e).__name__, e)


@contextmanager
def cm(tag):
    yield tag


def stopiter():
    try:
        with cm("si"):
            raise StopIteration("sent")
    except Exception as e:
        print("si", type(e).__name__, e)


def main():
    with CM("direct-clean"):
        pass
    try:
        with CM("direct-raise"):
            raise ValueError("direct")
    except Exception as e:
        print("direct caught", type(e).__name__, e)
    try:
        with Strict():
            raise RuntimeError("strict")
    except Exception as e:
        print("strict caught", type(e).__name__, e)
    try:
        with Strict():
            pass
    except Exception as e:
        print("strict clean caught", type(e).__name__, e)
    try:
        via_arg(CM("arg"))
    except Exception as e:
        print("arg caught", type(e).__name__, e)
    try:
        via_attr(Box(CM("attr")))
    except Exception as e:
        print("attr caught", type(e).__name__, e)
    via_list([CM("list0"), CM("list1")])
    try:
        via_dict({"m": CM("dict")})
    except Exception as e:
        print("dict caught", type(e).__name__, e)
    loops()
    nested()
    stopiter()


main()
'''

_HEAD = ('class CM:\n'
         '    def __enter__(self):\n'
         '        return self\n\n'
         '    ')

_TAIL = ('\n\n'
         'with CM():\n'
         '    raise ValueError("x")\n')


def _program(method, before=''):
    return before + _HEAD + method + _TAIL


REFUSED = [
    ('type', _program('def __exit__(self, et, ev, tb):\n'
                      '        print(type(tb).__name__)\n'
                      '        return True\n')),
    ('truth', _program('def __exit__(self, et, ev, tb):\n'
                       '        if tb:\n'
                       '            print("truthy")\n'
                       '        return True\n')),
    ('helper', _program('def __exit__(self, et, ev, tb):\n'
                        '        return helper(tb)\n',
                        before='def helper(t):\n'
                               '    return t is None\n\n\n')),
    ('attr', _program('def __exit__(self, et, ev, tb):\n'
                      '        print(tb.tb_lineno)\n'
                      '        return True\n')),
]

REFUSAL = "__exit__ uses 'tb' other than in `is None` / `is not None`"


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
    built = subprocess.run([sys.executable, '-B', CLI, 'compile', src.name,
                            '--syntax', 'python', '-o', exe.name], cwd=directory,
                           capture_output=True, text=True, timeout=900, env=env)
    if built.returncode != 0:
        return None, (built.stdout + built.stderr)[-3000:]
    got = subprocess.run([str(exe)], capture_output=True, timeout=120, cwd=directory)
    return (got.stdout.replace(b'\r\n', b'\n'), got.returncode), got.stderr.decode('utf-8', 'replace')[-1500:]


class Pre197Tests(unittest.TestCase):
    def check(self, slug, text):
        with tempfile.TemporaryDirectory(prefix='ail-pre197-') as directory:
            want, want_rc, err = _cpython(directory, slug, text)
            self.assertEqual(want_rc, 0, err)
            for general in (True, False):
                got, build_err = _build_and_run(directory, '%s_%s' % (slug, 'g' if general else 'd'),
                                                text, general)
                self.assertIsNotNone(got, '%s (general=%s)\n%s' % (slug, general, build_err))
                self.assertEqual(got, (want, 0), '%s (general=%s)\n%s' % (slug, general, build_err))

    def check_refused(self, slug, text, needle):
        with tempfile.TemporaryDirectory(prefix='ail-pre197-') as directory:
            for general in (True, False):
                got, build_err = _build_and_run(directory, '%s_%s' % (slug, 'g' if general else 'd'),
                                                text, general)
                self.assertIsNone(got, 'built and ran instead of refusing (general=%s):\n%s\n%s'
                                  % (general, text, build_err))
                self.assertIn(needle, build_err, 'general=%s\n%s' % (general, build_err))

    def test_exit_traceback_argument(self):
        self.check('traceback_arg', PROGRAM)

    def test_other_traceback_uses_refused(self):
        for slug, text in REFUSED:
            self.check_refused(slug, text, REFUSAL)


if __name__ == '__main__':
    unittest.main()

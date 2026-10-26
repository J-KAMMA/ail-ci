"""Pre-181: contextlib's throw() re-raises a sent StopIteration instead of AIL's RuntimeError.

CPython's PEP 479 turns a StopIteration escaping a generator into
`RuntimeError: generator raised StopIteration` whose `__cause__` is that object.
`contextlib._GeneratorContextManager.__exit__` recognises that cause and re-raises
the original exception, so a `StopIteration` raised in a `with` body comes back out
as the same `StopIteration`.  The general path lowered `@contextmanager` to
`send()`; the runtime converted the re-raised value to a RuntimeError and
`_AilGenCM.__exit__` propagated it, so both builds printed RuntimeError.  The runtime
now keeps the converted StopIteration as a private cause and `_AilGenCM.__exit__`
uses it, as CPython's contextlib does; a generator that catches the sent value and
raises a different StopIteration still gives RuntimeError, and a different exception
still propagates unchanged.  Normal attribute reads of exception chaining stay
refused (test_ail_pre179).
"""
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent

BASIC = r'''from contextlib import contextmanager


class MyStop(StopIteration):
    pass


@contextmanager
def cm(tag):
    yield tag


def builtin():
    try:
        with cm("builtin") as v:
            print("body", "builtin", v)
            raise StopIteration("builtin")
    except Exception as e:
        print("caught builtin", type(e).__name__, e)


def subtype(err, label):
    try:
        with cm(label) as v:
            print("body", label, v)
            raise err
    except Exception as e:
        print("caught", label, type(e).__name__, e, e is err)


@contextmanager
def replacement():
    try:
        yield
    except StopIteration:
        raise StopIteration("new")


@contextmanager
def converted():
    try:
        yield
    except StopIteration:
        raise ValueError("converted")


def other_stop():
    try:
        with replacement():
            raise StopIteration("sent")
    except Exception as e:
        print("new", type(e).__name__, e)


def other_type():
    try:
        with converted():
            raise StopIteration("sent")
    except Exception as e:
        print("value", type(e).__name__, e)


def main():
    builtin()
    subtype(MyStop("sub"), "sub")
    other_stop()
    other_type()


main()
'''

SOURCES = r'''from contextlib import contextmanager


class MyStop(StopIteration):
    pass


class Box:
    def __init__(self, tag):
        self.err = MyStop(tag)


@contextmanager
def cm(tag):
    yield tag


def via(err, label):
    try:
        with cm(label):
            raise err
    except Exception as e:
        print("via", label, type(e).__name__, e, e is err)


def main():
    via(MyStop("arg"), "arg")
    xs = [MyStop("list")]
    via(xs[0], "list")
    box = Box("attr")
    via(box.err, "attr")
    d = {"e": MyStop("dict")}
    via(d["e"], "dict")


main()
'''

GENERATOR_AND_CLEAN = r'''from contextlib import contextmanager


def raw():
    yield 1
    raise StopIteration("raw")


@contextmanager
def swallow_key():
    try:
        yield
    except KeyError:
        print("gen got KeyError")
        return
    finally:
        print("gen finally")


@contextmanager
def reraise_key(tag):
    try:
        yield tag
    except KeyError:
        print("gen reraise", tag)
        raise


def main():
    it = raw()
    print(next(it))
    try:
        next(it)
    except RuntimeError as e:
        print("raw", type(e).__name__, e)

    with reraise_key("clean") as v:
        print("body", v)
    try:
        with swallow_key():
            raise KeyError("k")
        print("suppressed")
    except Exception as e:
        print("escaped", type(e).__name__, e)
    try:
        with reraise_key("reraise"):
            raise KeyError("r")
    except Exception as e:
        print("caught", type(e).__name__, e)


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


class Pre181Tests(unittest.TestCase):
    def check(self, slug, text):
        with tempfile.TemporaryDirectory(prefix='ail-pre181-') as directory:
            want, want_rc, err = _cpython(directory, slug, text)
            self.assertEqual(want_rc, 0, err)
            for general in (True, False):
                got, build_err = _build_and_run(directory, '%s_%s' % (slug, 'g' if general else 'd'), text, general)
                self.assertIsNotNone(got, '%s (general=%s)\n%s' % (text[:2000], general, build_err))
                self.assertEqual(got, (want, 0), '%s (general=%s)\n%s' % (text[:2000], general, build_err))

    def test_sent_stopiteration_comes_back(self):
        self.check('basic', BASIC)

    def test_sent_stopiteration_from_sources(self):
        self.check('sources', SOURCES)

    def test_raw_pep479_and_clean_exits_unchanged(self):
        self.check('generator_clean', GENERATOR_AND_CLEAN)


if __name__ == '__main__':
    unittest.main()

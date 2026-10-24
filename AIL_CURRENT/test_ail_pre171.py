"""pre171: a boxed handler survives an indirect call into a typed helper.

pymix's exception rule walked the call graph only through ordinary direct calls by name.  A
helper with a typed trap (here the shift guards' ``ValueError`` for a negative count) could be
called from a lambda, stored in a list or passed as a callback; the invocation then happened
under the caller's boxed ``try``, but that handler was invisible from the helper's definition
site, so the typed clone aborted instead of returning to the handler.  Indirectly invoked
trap-capable candidates are now rejected, leaving the general/boxed path in charge.  The
programs cover ``<<``, ``>>`` and augmented shifts, counts from arguments, list items,
attributes and dict values, zero/valid shifts, aliases, callbacks and nested wrappers.
"""
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent


INDIRECT_SHIFT = r'''class Box:
    def __init__(self, n):
        self.n = n


def left(a, b):
    return a << b


def right(a, b):
    return a >> b


def aug_left(a, b):
    a <<= b
    return a


def aug_right(a, b):
    a >>= b
    return a


def report(tag, value):
    print(tag, value)


def main():
    box = Box(-2)
    xs = [4, -3]
    d = {"a": 6, "b": -1}
    fns = [
        lambda: report("left-const", left(1, -1)),
        lambda: report("left-arg", left(xs[0], box.n)),
        lambda: report("left-list", left(xs[0], xs[1])),
        lambda: report("left-attr", left(d["a"], box.n)),
        lambda: report("left-dict", left(d["a"], d["b"])),
        lambda: report("right-const", right(8, -1)),
        lambda: report("right-zero", right(8, 0)),
        lambda: report("right-big", right(8, 64)),
        lambda: report("aug-left", aug_left(1, -1)),
        lambda: report("aug-right", aug_right(8, -1)),
        lambda: report("valid", left(3, 4) + right(-16, 2)),
    ]
    for i in range(len(fns)):
        try:
            fns[i]()
        except ValueError as e:
            report("caught", (i, type(e).__name__, str(e), e.args))
    try:
        report("direct", left(0, -1))
    except ValueError as e:
        report("direct-caught", (type(e).__name__, str(e), e.args))
    empty = []
    for fn in empty:
        fn()
    print("done")


main()
'''

INDIRECT_ALIAS = r'''def shift(a, b):
    return a << b


def wrapper(a, b):
    return shift(a, b)


def wrapper2(a, b):
    return wrapper(a, b)


def apply(fn, a, b):
    return fn(a, b)


def main():
    alias = shift
    table = {"f": shift}
    cases = [
        ("alias", alias),
        ("dict", table["f"]),
        ("callback", lambda a, b: apply(shift, a, b)),
        ("wrapper", wrapper),
        ("wrapper2", wrapper2),
        ("lambda", lambda a, b: shift(a, b)),
    ]
    for name, fn in cases:
        try:
            print(name, fn(9, -1))
        except ValueError as e:
            print(name, "caught", type(e).__name__, repr(str(e)), repr(e.args))
    print("done")


main()
'''

INDIRECT_RAISE = r'''def fail(x):
    if x < 0:
        raise ValueError("bad value")
    return x


def main():
    fns = [lambda: fail(1), lambda: fail(-1), lambda: fail(2)]
    for i in range(len(fns)):
        try:
            print("case", i, fns[i]())
        except ValueError as e:
            print("caught", i, type(e).__name__, repr(str(e)), repr(e.args))
    print("done")


main()
'''

UNCAUGHT = r'''def shift(a, b):
    return a << b


fns = [lambda: shift(1, -1)]
print("before")
print(fns[0]())
print("after")
'''

PARALLEL_SHIFT = r'''fn work(n: int, b: int, mode: int) -> int {
    let xs: list[int] = [0] * n;
    parallel for i in range(0, n) {
        let t = i * 3;
        if i == n - 1 {
            if mode == 0 { xs[i] = t << b; } else { if mode == 1 { xs[i] = t >> b; } else { let u = t; u <<= b; xs[i] = u; } }
        } else { xs[i] = t; }
    }
    return xs[5];
}
fn main() {
    try { print(work(1000, -1, 0)); }
    except ValueError as e { print("caught0", e.kind, str(e)); }
    try { print(work(1000, -2, 1)); }
    except ValueError as e { print("caught1", e.kind, str(e)); }
    try { print(work(1000, -3, 2)); }
    except ValueError as e { print("caught2", e.kind, str(e)); }
    print(work(1000, 2, 0));
    print("done");
}
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


def _build_and_run_ail(directory, name, text, threads):
    src = Path(directory) / (name + '.ail')
    src.write_text(text, encoding='utf-8')
    exe = Path(directory) / ('exe_' + name)
    env = dict(os.environ, AIL_NO_CACHE='1', AIL_QUIET_FALLBACK='1', AIL_THREADS=str(threads))
    env.pop('AIL_UNIFIED_FORCE', None)
    built = subprocess.run([sys.executable, '-B', str(ROOT / 'ail_chatgpt.py'), 'compile', src.name,
                            '-o', exe.name], cwd=directory,
                           capture_output=True, text=True, timeout=900, env=env)
    if built.returncode != 0:
        return None, (built.stdout + built.stderr)[-3000:]
    got = subprocess.run([str(exe)], capture_output=True, timeout=120, cwd=directory, env=env)
    return (got.stdout.replace(b'\r\n', b'\n'), got.returncode), got.stderr.decode('utf-8', 'replace')[-1500:]


class Pre171Tests(unittest.TestCase):
    def check(self, slug, text, rc=0, stderr_last=None):
        with tempfile.TemporaryDirectory(prefix='ail-pre171-') as directory:
            want, got_rc, err = _cpython(directory, slug, text)
            self.assertEqual(got_rc, rc, err)
            if stderr_last is not None:
                lines = [line for line in err.decode('utf-8', 'replace').splitlines() if line.strip()]
                self.assertEqual(lines[-1], stderr_last)
            for general in (True, False):
                got, build_err = _build_and_run(directory, '%s_%s' % (slug, 'g' if general else 'd'), text, general)
                self.assertIsNotNone(got, '%s (general=%s)\n%s' % (text[:2000], general, build_err))
                self.assertEqual(got, (want, rc), '%s (general=%s)\n%s' % (text[:2000], general, build_err))
                if stderr_last is not None:
                    lines = [line for line in build_err.splitlines() if line.strip()]
                    self.assertEqual(lines[-1], stderr_last, '%s (general=%s)' % (slug, general))

    def test_indirect_shift_through_lambda(self):
        self.check('indirect_shift', INDIRECT_SHIFT)

    def test_indirect_shift_through_alias_and_wrapper(self):
        self.check('indirect_alias', INDIRECT_ALIAS)

    def test_indirect_explicit_raise(self):
        self.check('indirect_raise', INDIRECT_RAISE)

    def test_parallel_for_negative_shift_traps_on_the_caller(self):
        expected = (b"caught0 ValueError negative shift count\n"
                    b"caught1 ValueError negative shift count\n"
                    b"caught2 ValueError negative shift count\n"
                    b"15\ndone\n", 0)
        with tempfile.TemporaryDirectory(prefix='ail-pre171-par-') as directory:
            for threads in (1, 4):
                got, err = _build_and_run_ail(directory, 'parallel_shift_%d' % threads, PARALLEL_SHIFT, threads)
                self.assertIsNotNone(got, err)
                self.assertEqual(got, expected, 'AIL_THREADS=%d\n%s' % (threads, err))

    def test_uncaught_indirect_shift_names_the_value_error(self):
        self.check('indirect_uncaught', UNCAUGHT, rc=1, stderr_last='ValueError: negative shift count')


if __name__ == '__main__':
    unittest.main()

"""pre190: a large constant intermediate that reduces to an int64 result is folded.

The review of job pre184 recorded that the 4096-bit guard ran before the zero/base
special cases: `0 * (1 << 5000)`, `0 ** (1 << 5000)`, `1 ** (1 << 5000)`,
`(-1) ** (1 << 5000)` and `(1 << 5000) >> 5000` stopped with `integer overflow`, and
the same constants used as a `str.split` maxsplit were refused by name, although
CPython evaluates each to a value that fits int64.  The constant folders now decide
zero and the power bases 0/1/-1 before the size guard, and they allow a larger (but
still bounded) intermediate so a following shift/division/modulo can reduce it.
"""
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent

INT64_REDUCTIONS = r'''class Box:
    def __init__(self):
        self.value = 0


def identity(v):
    return v


def main():
    print(0 * (1 << 5000))
    print((1 << 5000) * 0)
    print((1 << 5000) & 0)
    print(0 & (1 << 5000))
    print(0 ** (1 << 5000))
    print(1 ** (1 << 5000))
    print((-1) ** (1 << 5000))
    print((-1) ** ((1 << 5000) + 1))
    print((1 << 5000) ** 0)
    print((1 << 5000) >> 5000)
    print((1 << 5000) // (1 << 4999))
    print((2 ** 5000) % (2 ** 5000))
    print((2 ** 5000) - (2 ** 5000))
    print((1 << 5000) ^ (1 << 5000))
    print(identity((1 << 5000) >> 5000))
    xs = [(1 << 5000) >> 5000]
    print(xs[0])
    box = Box()
    box.value = (1 << 5000) >> 5000
    print(box.value)
    d = {"k": (1 << 5000) >> 5000}
    print(d["k"])
    M = (1 << 5000) >> 5000
    print(M)


main()
'''

MAXSPLIT_REDUCTIONS = r'''class Box:
    def __init__(self):
        self.n = 1


def main():
    s = "a b c d"
    print(s.split(" ", 0 * (1 << 5000)))
    print(s.split(" ", (1 << 5000) * 0))
    print(s.split(" ", 0 ** (1 << 5000)))
    print(s.split(" ", 1 ** (1 << 5000)))
    print(s.split(" ", (-1) ** (1 << 5000)))
    print(s.split(" ", (1 << 5000) >> 5000))
    print(s.split(" ", (2 ** 5000) >> 4990))
    print(s.rsplit(" ", (2 ** 5000) // (2 ** 4998)))
    print(s.split(" ", (2 ** 5000) % (2 ** 5000)))
    n = (1 << 5000) >> 4999
    print(s.split(" ", n))
    xs = [(1 << 5000) >> 4999]
    print(s.split(" ", xs[0]))
    d = {"n": (1 << 5000) >> 4999}
    print(s.split(" ", d["n"]))
    box = Box()
    box.n = (1 << 5000) >> 4999
    print(s.split(" ", box.n))
    print(s.split(" ", maxsplit=(1 << 5000) >> 4999))


main()
'''

NON_INT_ZERO_CASES = r'''class Box:
    def __init__(self):
        self.v = 1.5
        self.n = 1


def ident(v):
    return v


def f():
    print("called")
    return 2


def show(label, fn):
    try:
        print(label, fn())
    except Exception as e:
        print(label, type(e).__name__)


def main():
    print(1.5 ** 0)
    print(f() ** 0)
    show("pow-error", lambda: (1 // 0) ** 0)
    show("pow-str", lambda: "a" ** 0)
    print(0 * 1.5)
    print(1.5 * 0)
    print(0 * "ab")
    print("ab" * 0)
    print(f() * 0)
    print(0 * f())
    show("mul-error", lambda: 0 * (1 // 0))
    show("mul-error2", lambda: (1 // 0) * 0)
    show("and-float", lambda: 0 & 1.5)
    show("and-float2", lambda: 1.5 & 0)
    show("and-error", lambda: 0 & (1 // 0))
    print(f() & 0)
    print(0 & f())
    print(0 * (1 << 5000))
    print((1 << 5000) ** 0)
    x = 1.5
    print(ident(x) ** 0)
    xs = [2.5]
    print(xs[0] ** 0)
    b = Box()
    print(b.v ** 0)
    d = {"v": 2.5, "n": 1}
    ns = [1]
    print(d["v"] ** 0)
    print(ident(x) * 0)
    print(xs[0] * 0)
    print(b.v * 0)
    print(d["v"] * 0)
    show("and-item", lambda: xs[0] & 0)
    show("and-attr", lambda: b.v & 0)
    show("and-dict", lambda: d["v"] & 0)
    s = "a,b,c"
    print(s.split(",", 0 * f()))
    print(s.split(",", f() ** 0))
    show("split-float", lambda: s.split(",", 2.0 ** 0))
    show("split-error", lambda: s.split(",", 0 * (1 // 0)))
    print(s.split(",", 0 * (1 << 5000)))
    print(s.split(",", (1 << 5000) ** 0))
    print(s.rsplit(",", f() ** 0))
    n = 1
    print(s.split(",", ident(n)))
    print(s.split(",", ns[0]))
    print(s.split(",", b.n))
    print(s.split(",", d["n"]))
    print(s.split(",", maxsplit=f() ** 0))


main()
'''

OUT_OF_RANGE = [
    ('over_intermediate', 'print("a b".split(" ", 1 << 2000000))\n'),
    ('over_int64', 'print("a b".split(" ", 2**63))\n'),
]

MODES = (
    ('default', {}),
    ('general', {'AIL_UNIFIED_FORCE': '1'}),
    ('typed_legacy', {'AIL_IR': '0'}),
    ('general_legacy', {'AIL_UNIFIED_FORCE': '1', 'AIL_UNIFIED': '0'}),
)


def _cpython(directory, name, text):
    src = Path(directory) / (name + '_cpython.py')
    src.write_text(text, encoding='utf-8')
    done = subprocess.run([sys.executable, '-B', str(src)], capture_output=True, timeout=120,
                          env=dict(os.environ, PYTHONUTF8='1'))
    return done.stdout.replace(b'\r\n', b'\n'), done.returncode, done.stderr


def _build_and_run(directory, name, text, extra):
    src = Path(directory) / (name + '.ail')
    src.write_text(text, encoding='utf-8')
    exe = Path(directory) / ('exe_' + name)
    env = dict(os.environ, AIL_NO_CACHE='1', AIL_QUIET_FALLBACK='1')
    for key in ('AIL_UNIFIED_FORCE', 'AIL_UNIFIED', 'AIL_IR', 'AIL_NO_GENERAL'):
        env.pop(key, None)
    env.update(extra)
    built = subprocess.run([sys.executable, '-B', str(ROOT / 'ail_chatgpt.py'), 'compile', src.name,
                            '--syntax', 'python', '-o', exe.name], cwd=directory,
                           capture_output=True, text=True, timeout=900, env=env)
    if built.returncode != 0:
        return None, (built.stdout + built.stderr)[-3000:]
    got = subprocess.run([str(exe)], capture_output=True, timeout=120, cwd=directory)
    return (got.stdout.replace(b'\r\n', b'\n'), got.returncode), got.stderr.decode('utf-8', 'replace')[-1500:]


class Pre190Tests(unittest.TestCase):
    def check(self, slug, text):
        with tempfile.TemporaryDirectory(prefix='ail-pre190-') as directory:
            want, rc, err = _cpython(directory, slug, text)
            self.assertEqual(rc, 0, err)
            for mode, extra in MODES:
                got, build_err = _build_and_run(directory, '%s_%s' % (slug, mode), text, extra)
                self.assertIsNotNone(got, '%s (%s)\n%s' % (text[:2000], mode, build_err))
                self.assertEqual(got, (want, rc), '%s (%s)\n%s' % (text[:2000], mode, build_err))

    def check_refused(self, slug, text, needle):
        with tempfile.TemporaryDirectory(prefix='ail-pre190-') as directory:
            for mode, extra in MODES:
                got, build_err = _build_and_run(directory, '%s_%s' % (slug, mode), text, extra)
                self.assertIsNone(got, '%s (%s) built but should be refused' % (text[:200], mode))
                self.assertIn(needle, build_err, '%s (%s)' % (text[:200], mode))

    def test_large_intermediate_reduces_to_int64(self):
        self.check('int64_reductions', INT64_REDUCTIONS)

    def test_large_intermediate_as_maxsplit(self):
        self.check('maxsplit_reductions', MAXSPLIT_REDUCTIONS)

    def test_zero_and_base_shortcuts_require_constant_ints(self):
        self.check('non_int_zero_cases', NON_INT_ZERO_CASES)

    def test_fold_limit_is_shared_with_maxsplit(self):
        sys.path.insert(0, str(ROOT / 'python/pkg-v12'))
        try:
            import pyfunc
        finally:
            sys.path.pop(0)
        self.assertGreaterEqual(pyfunc._CONST_INT_BITS, pyfunc._MAXSPLIT_BITS)
        self.assertEqual(pyfunc._CONST_INT_BITS, 1 << 22)

    def test_oversized_maxsplit_still_refused(self):
        # exact ints (bigint): built, and the OverflowError comes at run time as in CPython
        for slug, text in OUT_OF_RANGE:
            with tempfile.TemporaryDirectory(prefix='ail-pre190-') as directory:
                want, rc, err = _cpython(directory, slug, text)
                for mode, extra in MODES:
                    got, build_err = _build_and_run(directory, '%s_%s' % (slug, mode), text, extra)
                    self.assertIsNotNone(got, '%s (%s)\n%s' % (text[:200], mode, build_err))
                    self.assertEqual(got, (want, rc), '%s (%s)\n%s' % (text[:200], mode, build_err))


if __name__ == '__main__':
    unittest.main()

"""pre203: a unary constant expression with an out-of-int64 intermediate but int64 result.

Python parses ``-(1 << 63)`` as a unary minus over a shift.  Both builds used to shift to
2**63 and then trap in the negate, while CPython prints INT64_MIN.  The same happened to
``-((1 << 5000) >> 4937)``.  The front end now rewrites an in-range unary constant expression
to a literal (MIN as ``-9223372036854775807 - 1``) before the backends parse the text again.
"""
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent

SOURCE = r'''M = -(1 << 63)
a, b = -(1 << 63), 1


class Box:
    def __init__(self, value):
        self.value = value


def show(value):
    print(value)


def main():
    print(M)
    print(a, b)
    print(-(1 << 63))
    print(-((1 << 5000) >> 4937))
    print(-(1 << 62))
    print(+(1 << 62))
    print(-(2 ** 63 - 1))
    print(-(1 << 63) + 1)
    print(-(1 << 63) >> 1)
    print(-(1 << 63) + (1 << 63))
    print(-(1 << 63) // 2)
    print(-0)
    print(-1)
    print(-(-5))
    print(-0.0)
    print(-1.5)
    show(-(1 << 63))
    xs = [-(1 << 63)]
    print(xs[0])
    box = Box(-(1 << 63))
    print(box.value)
    d = {"k": -(1 << 63)}
    print(d["k"])
    alias = -(1 << 63)
    copy = alias
    print(copy)
    print(-((1 << 5000) >> 4937) + 1)
    print(f"{-(1 << 63)=}")
    print(f"{+(1 << 62)=}")


return5 = 99
not5 = 42


def adjacent():
    return+5


main()
print(adjacent())
print(not+5)
print(1 and+(1 << 62))
'''

MODES = (
    ('default', {}),
    ('general', {'AIL_UNIFIED_FORCE': '1'}),
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


class Pre203Tests(unittest.TestCase):
    def test_unary_min_int64_matches_cpython(self):
        with tempfile.TemporaryDirectory(prefix='ail-pre203-') as directory:
            want, want_rc, err = _cpython(directory, 'source', SOURCE)
            self.assertEqual(want_rc, 0, err)
            for label, extra in MODES:
                with self.subTest(label):
                    got, build_err = _build_and_run(directory, label, SOURCE, extra)
                    self.assertIsNotNone(got, build_err)
                    self.assertEqual(got, (want, want_rc), build_err)

    def test_nested_unary_overflow_is_still_refused_by_name(self):
        text = 'print(-(-9223372036854775808))\n'
        with tempfile.TemporaryDirectory(prefix='ail-pre203-') as directory:
            # exact ints (bigint): the value 2**63 is no longer refused, both builds print CPython's answer
            want, want_rc, err = _cpython(directory, 'refused_source', text)
            self.assertEqual(want_rc, 0, err)
            for label, extra in MODES:
                with self.subTest(label):
                    got, build_err = _build_and_run(directory, 'refused_' + label, text, extra)
                    self.assertIsNotNone(got, build_err)
                    self.assertEqual(got, (want, want_rc), build_err)

    def test_generic_fold_limit_covers_wide_unary(self):
        sys.path.insert(0, str(ROOT / 'python/pkg-v12'))
        try:
            import pyfunc
        finally:
            sys.path.pop(0)
        self.assertGreaterEqual(pyfunc._CONST_INT_BITS, 8192)


if __name__ == '__main__':
    unittest.main()

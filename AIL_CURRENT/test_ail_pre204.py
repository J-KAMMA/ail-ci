"""Pre-204: a unary constant expression whose result fits int64 is folded exactly.

`print(-(1 << 63))` and `print(-((1 << 5000) >> 4937))` both denote INT64_MIN.  The unary
emitters only folded a plain literal operand, so they emitted a checked shift/negation whose
intermediate (2**63, or 2**5000 before the right shift) left int64 and stopped the program with
`integer overflow`; CPython's unbounded ints print -9223372036854775808.

Every emitter now folds the whole unary constant expression with Python ints and emits the
in-range result.  The same exact folding also covers a whole binary reduction whose intermediate
is large but whose result fits (`0 >> (1 << 5000)`, `2 ** ((1 << 2000000) - (1 << 2000000))`,
`(1 << 2000000) >> 2000000`).  Values that only reach the operation as variables keep the
fixed-width run-time trap.
"""
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent

NEGATIVE_INT64_MIN = r'''def main():
    print(-(1 << 63))
    print(-((1 << 5000) >> 4937))
    print(-(2 ** 63))
    print(~((1 << 63) - 1))
    print(-((1 << 64) >> 1))
    print(-((1 << 2000000) >> 1999999))
    print(-(1 << 62))
    print(-0)
    print(-(-5))
    print(+(-(1 << 63)))
    print(-(-(1 << 63) + 1))
    print(-(1 << 63) + 1)
    print(-((1 << 63) - 1))
    print((1 << 63) - 1)


main()
'''

FLOWS = r'''class Box:
    def __init__(self, v):
        self.v = v


def identity(v):
    return v


def pick(i):
    if i == 0:
        return -(1 << 63)
    return -((1 << 5000) >> 4937)


def main():
    vals = [-(1 << 63), -((1 << 5000) >> 4937), -(2 ** 63)]
    print(vals)
    print(identity(-(1 << 63)))
    print(identity(-((1 << 5000) >> 4937)))
    box = Box(0)
    box.v = -(1 << 63)
    print(box.v)
    d = {"k": -((1 << 5000) >> 4937)}
    print(d["k"])
    x = -(1 << 63)
    y = x
    print(y)
    print(pick(0), pick(1))


main()
'''

REDUCTIONS = r'''def main():
    print(0 >> (1 << 5000))
    print(2 ** ((1 << 2000000) - (1 << 2000000)))
    print((1 << 2000000) >> 2000000)
    print((1 << 64) - (1 << 64))
    print(2 ** 65 - 2 ** 65)


main()
'''

DYNAMIC = r'''def neg(x):
    return -x


def main():
    x = 1 << 62
    print(neg(x), -x)
    y = 5
    print(-y, -(-y))
    vals = [7, -9]
    print(-vals[0], -vals[1])


main()
'''

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
    return done.stdout.replace(b'\r\n', b'\n'), done.returncode


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


class Pre204Tests(unittest.TestCase):
    def check(self, slug, text, modes=MODES):
        with tempfile.TemporaryDirectory(prefix='ail-pre204-') as directory:
            want, rc = _cpython(directory, slug, text)
            for mode, extra in modes:
                got, build_err = _build_and_run(directory, '%s_%s' % (slug, mode), text, extra)
                self.assertIsNotNone(got, '%s (%s)\n%s' % (text[:2000], mode, build_err))
                self.assertEqual(got, (want, rc), '%s (%s)\n%s' % (text[:2000], mode, build_err))

    def test_negative_int64_min(self):
        self.check('negative_int64_min', NEGATIVE_INT64_MIN)

    def test_value_flows(self):
        self.check('flows', FLOWS)

    def test_large_intermediate_reductions(self):
        self.check('reductions', REDUCTIONS)

    def test_dynamic_values_keep_the_runtime_path(self):
        self.check('dynamic', DYNAMIC, MODES[:2])


if __name__ == '__main__':
    unittest.main()

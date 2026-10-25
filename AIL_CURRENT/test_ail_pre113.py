"""pre113: an all-int constant expression whose result fits int64 is folded exactly.

Python evaluates `(1 << 63) - 1` and `2**65 - 2**65` with unbounded ints, so the
intermediate may be outside int64 even when the answer is not.  The typed IR, the
legacy typed emitter and the general path used to trap on that intermediate.
"""
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent

INT64_BOUNDARIES = r'''class Box:
    def __init__(self):
        self.value = 0


def identity(v):
    return v


def main():
    print((1 << 63) - 1)
    print(2 ** 65 - 2 ** 65)
    print(2 ** 63 - 1)
    print((1 << 64) - (1 << 64))
    print((1 << 62) * 2 - 1)
    print(2 ** 64 // 2 - 1)
    print(0 - (1 << 63))
    print(((1 << 63) - 1) * -1 - 1)
    print(identity((1 << 63) - 1))
    xs = [(1 << 63) - 1]
    print(xs[0])
    box = Box()
    box.value = (1 << 63) - 1
    print(box.value)
    d = {"k": (1 << 63) - 1}
    print(d["k"])
    print([(1 << 63) - 1, 2 ** 65 - 2 ** 65])


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


class Pre113Tests(unittest.TestCase):
    def check(self, slug, text, rc=0):
        with tempfile.TemporaryDirectory(prefix='ail-pre113-') as directory:
            want, got_rc, err = _cpython(directory, slug, text)
            self.assertEqual(got_rc, rc, err)
            for mode, extra in MODES:
                got, build_err = _build_and_run(directory, '%s_%s' % (slug, mode), text, extra)
                self.assertIsNotNone(got, '%s (%s)\n%s' % (text[:2000], mode, build_err))
                self.assertEqual(got, (want, rc), '%s (%s)\n%s' % (text[:2000], mode, build_err))

    def test_int64_boundaries(self):
        self.check('int64_boundaries', INT64_BOUNDARIES)


if __name__ == '__main__':
    unittest.main()

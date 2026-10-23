"""`-2**63` (INT64_MIN) in comparisons and containers, against CPython 3.12.

Python parses `-2**63` as `-(2**63)`: the positive power is outside int64, but its negation is
INT64_MIN and is inside. The typed path emitted the power first, so `print(-2**63 < 0)` raised
`integer overflow` before the minus could bring the result back into range (only a single-line
`print(<expression>)` escaped it by falling back to the general path). The general path now
recognises the same spelling, as do the typed legacy emitter and the IR emitter.

Each program is built with the general path forced, with the default build (IR on), and with the
typed legacy emitter (AIL_IR=0); stdout and the exit status must equal CPython's.
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
MODES = ('general', 'default', 'legacy')


def _last_line(err):
    lines = [x for x in err.decode('utf-8', 'replace').splitlines() if x.strip()]
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
    elif mode == 'legacy':
        env['AIL_IR'] = '0'
    cmd = [sys.executable, '-B', CHATGPT, 'compile', src.name, '--syntax', 'python', '-o', exe.name]
    built = subprocess.run(cmd, cwd=directory, capture_output=True, text=True, timeout=900, env=env)
    if built.returncode != 0:
        return None, (built.stdout + built.stderr)[-1500:]
    got = subprocess.run([str(exe)], capture_output=True, timeout=120, cwd=directory)
    return (got.stdout.replace(b'\r\n', b'\n'), got.returncode, _last_line(got.stderr)), ''


PROGRAMS = {
    'chain': '''print(-2**63 < 0)
print(-2**63 < 0 < 1)
print(-2**63 == -2**63 < 0)
print(-2**63 <= -2**63 <= -2**63)
print(0 > -2**63 > -1)
print(-2**63 > -2**63)
print(-2**63 != -2**63)
''',
    'contexts': '''def neg(x):
    return x < 0


class Box:
    def __init__(self, value):
        self.value = value


a = -2**63
b = a
xs = [-2**63, 0]
ys = []
d = {1: -2**63, 2: 0}
e = {}
box = Box(-2**63)
print(neg(-2**63))
print(xs[0] < 0)
print(d[1] < 0)
print(box.value < 0)
print(len(xs), len(ys), len(d), len(e))
print(a == b)
print(box.value == a)
print(-2**63 in xs)
print(-2**63 in d)
''',
    'types_widths': '''xs = []
d = {}
s = ""
print(-2**63 < -9223372036854775807)
print(-2**63 > -9223372036854775807)
print(-2**63 + 0 == -2**63)
print(-2**63 * 1 == -2**63)
print(-2**62 - 2**62 == -2**63)
print(-2.0**63 < 0)
print(-2**63 + 0.0 == -2.0**63)
print((-2)**63 == -2**63)
print(len(xs), len(d), len(s))
print(-2**63 in xs)
print(-2**63 in d)
''',
}


@unittest.skipUnless(HAVE_CC, 'gcc is required')
class NegativeInt64MinPower(unittest.TestCase):
    def check(self, name, modes=MODES):
        text = PROGRAMS[name]
        with tempfile.TemporaryDirectory(prefix='ail-pre3-') as directory:
            want = _cpython(directory, name, text)
            self.assertEqual(want[1], 0, name)
            for mode in modes:
                got, err = _build_run(directory, name, text, mode)
                self.assertIsNotNone(got, '%s (%s)\n%s' % (name, mode, err))
                self.assertEqual(got, want, '%s (%s)' % (name, mode))


def _add(name):
    setattr(NegativeInt64MinPower, 'test_' + name,
            lambda self, name=name: self.check(name))


for _name in PROGRAMS:
    _add(_name)


if __name__ == '__main__':
    unittest.main()

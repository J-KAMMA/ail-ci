"""pre104: one-argument `round()` of nan/inf raises CPython's exception on both builds.

The pre54 review recorded that the default build stopped on `round(float('nan'))` with the
runtime trap message `round() of nan` instead of raising the ValueError a program can catch
(and printing CPython's `ValueError: cannot convert float NaN to integer` when uncaught).
`round(float('inf'))` had the same problem with OverflowError.  The runtime now raises those
two exceptions through the normal exception path, so caught and uncaught programs agree with
CPython; finite values, including the int64-boundary trap, are unchanged.
"""
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent

NAN_TRY = '''\
try:
    print(round(float("nan")))
except Exception as e:
    print(type(e).__name__, repr(str(e)))
'''

INF_TRY = '''\
try:
    print(round(float("inf")))
except Exception as e:
    print(type(e).__name__, repr(str(e)))
'''

NINF_TRY = '''\
try:
    print(round(float("-inf")))
except Exception as e:
    print(type(e).__name__, repr(str(e)))
'''

NAN_UNCAUGHT = '''\
print("before")
print(round(float("nan")))
'''

INF_UNCAUGHT = '''\
print("before")
print(round(float("inf")))
'''

ARGUMENT = '''\
def probe(v):
    try:
        return round(v)
    except Exception as e:
        return type(e).__name__, str(e)


print(probe(float("nan")))
print(probe(float("inf")))
print(probe(float("-inf")))
print(probe(2.5), probe(-0.0))
'''

CONTAINERS = '''\
class Holder:
    def __init__(self, v):
        self.v = v


def probe(v):
    try:
        return round(v)
    except Exception as e:
        return type(e).__name__, str(e)


xs = [float("nan")]
h = Holder(float("inf"))
d = {"v": float("-inf")}
print(probe(xs[0]))
print(probe(h.v))
print(probe(d["v"]))
'''

TWO_ARG = '''\
for v in (float("nan"), float("inf"), float("-inf"), 2.5, -0.0):
    print(repr(round(v, 2)))
'''

FINITE = '''\
for v in (2.5, 3.5, -2.5, -0.0, 0.0, 1e15):
    print(type(round(v)).__name__, round(v))
'''

CASES = (
    ('nan_try', NAN_TRY),
    ('inf_try', INF_TRY),
    ('ninf_try', NINF_TRY),
    ('nan_uncaught', NAN_UNCAUGHT),
    ('inf_uncaught', INF_UNCAUGHT),
    ('argument', ARGUMENT),
    ('containers', CONTAINERS),
    ('two_arg', TWO_ARG),
    ('finite', FINITE),
)


def _compile(directory, name, text, general):
    src = Path(directory) / (name + '.py')
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
    return built, exe


def _last_line(blob):
    lines = [line for line in blob.decode('utf-8', 'replace').replace('\r\n', '\n').split('\n') if line]
    return lines[-1] if lines else ''


class Pre104Tests(unittest.TestCase):
    def test_round_nan_and_inf_match_cpython_on_both_builds(self):
        for label, text in CASES:
            with tempfile.TemporaryDirectory(prefix='ail-pre104-') as directory:
                src = Path(directory) / (label + '_cpython.py')
                src.write_text(text, encoding='utf-8')
                want = subprocess.run([sys.executable, '-B', str(src)], capture_output=True,
                                      timeout=120, env=dict(os.environ, PYTHONUTF8='1'))
                for general in (True, False):
                    with self.subTest(label=label, general=general):
                        built, exe = _compile(directory, '%s_%s' % (label, 'g' if general else 'd'),
                                              text, general)
                        self.assertEqual(built.returncode, 0, built.stdout + built.stderr)
                        got = subprocess.run([str(exe)], capture_output=True, timeout=120, cwd=directory)
                        self.assertEqual(got.stdout.replace(b'\r\n', b'\n'),
                                         want.stdout.replace(b'\r\n', b'\n'))
                        self.assertEqual(got.returncode, want.returncode, got.stderr[-1500:])
                        if want.returncode != 0:
                            self.assertEqual(_last_line(got.stderr), _last_line(want.stderr))
                            self.assertNotIn('round() of nan', got.stderr.decode('utf-8', 'replace'))
                            self.assertNotIn('does not fit in this language', got.stderr.decode('utf-8', 'replace'))


if __name__ == '__main__':
    unittest.main()

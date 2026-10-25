"""pre188: abs() of negative zero must print 0.0, not -0.0.

The review of job fuzz42 recorded a pre-existing difference: on the default/typed path
`abs(-0.0)` printed `-0.0` where CPython prints `0.0`.  Both typed lowerings wrote the
absolute value as `x < 0 ? -x : x`, and that comparison is false for negative zero, so the
negative sign survived.  The legacy emitter and the IR now clear the sign with an absolute
value (`__builtin_fabs`), which also keeps infinities and NaN right.

The cases below reach abs() through a float parameter (the IR), a literal, an alias, a list
item, an attribute, a dict value and a helper argument (the legacy emitter / typed path), on
both builds.
"""
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent

ABS_ZERO = r'''class Box:
    def __init__(self, v: float):
        self.v = v


def ident(x: float) -> float:
    return abs(x)


def from_list(xs: list[float], i: int) -> float:
    return abs(xs[i])


def main() -> None:
    print(repr(abs(-0.0)), repr(abs(0.0)), repr(abs(-0)))
    z = -0.0
    y = z
    print(repr(abs(z)), repr(abs(y)), repr(ident(z)), repr(ident(0.0)))
    a: float = abs(-0.0)
    print(repr(a))
    xs: list[float] = [-0.0, 0.0, -2.5, 2.5]
    print(repr(abs(xs[0])), repr(abs(xs[1])), abs(xs[2]), abs(xs[3]))
    print(repr(from_list(xs, 0)), repr(from_list(xs, 1)), from_list(xs, 2))
    d: dict[str, float] = {"n": -0.0, "p": -3.5}
    print(repr(abs(d["n"])), abs(d["p"]))
    box = Box(-0.0)
    print(repr(abs(box.v)), repr(ident(box.v)))
    print(repr(abs(-float("inf"))), repr(abs(float("-inf"))), repr(abs(float("nan"))))
    print(repr(abs(-5e-324)), repr(abs(5e-324)))
    print(abs(-1), abs(1), abs(-5), abs(5), abs(0))
    print(abs(-9223372036854775807), abs(9223372036854775807))
    print("end")


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


class Pre188Tests(unittest.TestCase):
    def check(self, slug, text):
        with tempfile.TemporaryDirectory(prefix='ail-pre188-') as directory:
            want, rc, err = _cpython(directory, slug, text)
            self.assertEqual(rc, 0, err)
            for general in (True, False):
                got, build_err = _build_and_run(directory, '%s_%s' % (slug, 'g' if general else 'd'),
                                                text, general)
                self.assertIsNotNone(got, '%s (general=%s)\n%s' % (text[:2000], general, build_err))
                self.assertEqual(got, (want, rc), '%s (general=%s)\n%s' % (text[:2000], general, build_err))

    def test_abs_negative_zero(self):
        self.check('abs_zero', ABS_ZERO)


if __name__ == '__main__':
    unittest.main()

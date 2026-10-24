"""Space sign + zero padding in the general path's boxed formatter (job pre83).

The general path's `ail__pad` treats `=` alignment (what the `0` flag sets) as sign-aware, but
it only recognised `-` and `+` as signs, not `' '`.  A space-sign zero-padded field therefore
put the fill before the sign: `f"{1.5: 010.2f}"` printed `00000 1.50` where CPython prints
` 000001.50`.  The same helper backs `format()` and `.format()`.

The values reach the formatter as a local, a parameter, a list item, a dict value and an
attribute, and cover zero, negative zero, negative values, widths narrower than the text and the
`+`, `' '` and absent sign.  Both builds (the general path forced with AIL_UNIFIED_FORCE=1 and
the default build) must print what CPython prints.
"""
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent

PROGRAM = r'''class Box:
    def __init__(self, v: float) -> None:
        self.v: float = v


def show(v: float) -> None:
    print(f"[{v: 010.2f}]")
    print(f"[{v:+010.2f}]")
    print(f"[{v:010.2f}]")
    print(f"[{v: 010.0f}]")
    print(f"[{v: 010.4f}]")
    print(f"[{v: 02.2f}]")
    print(f"[{v: 0.2f}]")
    print(f"[{v: 012.2F}]")


def main() -> None:
    for v in [1.5, -1.5, 0.0, -0.0, 0.25, -0.25, 1234.5]:
        show(v)
    b = Box(2.5)
    xs: list[float] = [3.5, -3.5]
    d: dict[str, float] = {"k": 4.5, "n": -4.5}
    print(f"[{b.v: 010.2f}]")
    print(f"[{xs[0]: 010.2f}]")
    print(f"[{xs[1]: 010.2f}]")
    print(f"[{d['k']: 010.2f}]")
    print(f"[{d['n']: 010.2f}]")
    n = 42
    print(f"[{n: 010d}]")
    print(f"[{-n: 010d}]")
    print(f"[{n:+010d}]")
    print(f"[{n:010d}]")
    print(f"[{n: 04d}]")
    print(f"[{-n: 012d}]")
    print("[" + format(1.5, " 010.2f") + "]")
    print("[" + "{: 010.2f}".format(-1.5) + "]")


main()
'''


def _cpython(directory, text):
    src = Path(directory) / 'cpython.py'
    src.write_text(text, encoding='utf-8')
    done = subprocess.run([sys.executable, '-B', str(src)], capture_output=True, timeout=120,
                          env=dict(os.environ, PYTHONUTF8='1'))
    return done.stdout.replace(b'\r\n', b'\n'), done.returncode, done.stderr


def _build_and_run(directory, text, general):
    src = Path(directory) / 'p.ail'
    src.write_text(text, encoding='utf-8')
    exe = Path(directory) / ('exe_g' if general else 'exe_d')
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
    return (got.stdout.replace(b'\r\n', b'\n'), got.returncode), \
        got.stderr.decode('utf-8', 'replace')[-1500:]


class Pre83Tests(unittest.TestCase):
    def test_space_sign_zero_padding(self):
        with tempfile.TemporaryDirectory(prefix='ail-pre83-') as directory:
            want, rc, err = _cpython(directory, PROGRAM)
            self.assertEqual(rc, 0, err)
            self.assertTrue(want, 'the oracle printed nothing')
            for general in (True, False):
                got, build_err = _build_and_run(directory, PROGRAM, general)
                self.assertIsNotNone(got, 'general=%s\n%s' % (general, build_err))
                self.assertEqual(got, (want, 0), 'general=%s\n%s' % (general, build_err))


if __name__ == '__main__':
    unittest.main()

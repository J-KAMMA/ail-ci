"""A run-time integer exponent may be negative in the default build too (job pre321).

The reviewer of job pre305 recorded that `**` with a negative exponent stopped only on the
default build, although the general path already matched CPython.  The typed path emitted
`ail_ipow`, which is exact for int64 and therefore traps when the exponent turns out negative;
the general path carries the value type at run time and returns CPython's float (`2 ** -1` is
`0.5`).  The legacy type of `**` now leaves a computed integer exponent to the general path,
where its sign is handled at run time; constant exponents keep their existing int/float type,
and a computed positive exponent still gives the same result (through the general path).
"""
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent

PROGRAM = r'''class Box:
    def __init__(self):
        self.b = 2
        self.e = -3


def power(base, exponent):
    return base ** exponent


def main():
    b = 2
    n = -1
    alias_b = b
    alias_n = n
    xs = [3, -2]
    d = {"b": -2, "e": -3}
    box = Box()

    print(power(b, n))
    print(power(2, -2), power(10, -2), power(-2, -1), power(-2, -2))
    print(power(alias_b, alias_n), power(b, alias_n), power(alias_b, n))
    print(power(xs[0], xs[1]), power(d["b"], d["e"]), power(box.b, box.e))
    print(power(2, -1000), power(1, -1000000), power(-1, -1000001))
    print(power(2, 10), power(-2, 3), power(3, 0))
    print(power(2.0, -1), power(b, True), power(b, False))


main()
'''


def build_run(directory, general):
    src = Path(directory) / ('probe_%s.py' % ('g' if general else 'd'))
    exe = Path(directory) / ('probe_%s' % ('g' if general else 'd'))
    src.write_text(PROGRAM, encoding='utf-8')
    env = dict(os.environ, AIL_NO_CACHE='1', AIL_QUIET_FALLBACK='1')
    env.pop('AIL_NO_GENERAL', None)
    env.pop('AIL_GENERAL', None)
    if general:
        env['AIL_UNIFIED_FORCE'] = '1'
    else:
        env.pop('AIL_UNIFIED_FORCE', None)
    built = subprocess.run([sys.executable, '-B', str(ROOT / 'ail_chatgpt.py'), 'compile', src.name,
                            '--syntax', 'python', '-o', exe.name], cwd=directory,
                           capture_output=True, text=True, timeout=900, env=env)
    if built.returncode:
        return built.returncode, b'', built.stdout + built.stderr
    ran = subprocess.run([str(exe)], cwd=directory, capture_output=True, timeout=30)
    return ran.returncode, ran.stdout.replace(b'\r\n', b'\n'), built.stdout + built.stderr


class Pre321(unittest.TestCase):
    def test_computed_negative_exponent_matches_cpython(self):
        with tempfile.TemporaryDirectory(prefix='ail-pre321-') as directory:
            want = subprocess.run([sys.executable, '-B', '-c', PROGRAM], capture_output=True,
                                  timeout=30)
            self.assertEqual(want.returncode, 0, want.stderr)
            for general in (False, True):
                with self.subTest(general=general):
                    status, got, output = build_run(directory, general)
                    self.assertEqual(status, 0, output)
                    self.assertEqual(got, want.stdout.replace(b'\r\n', b'\n'), output)


if __name__ == '__main__':
    unittest.main()

"""bigcap's hard marks read constants the function names (docs/design/BIGINT.md section 5).

`x << SH` with `SH = 22` bound once in the function (or a module int constant) is the shift `x << 22`, which was never a
hard mark; `int.from_bytes` of at most 7 bytes (a bytes literal, `s[3:7]`, `s[p:p + 4]`) is below 2**56. Both used to
send the whole program to the general path (lab/compare berth_sim, rail_transfer; echo_pack's header read).

C1  the marks: what is a constant and what is not (a parameter, two stores, `global`, `nonlocal`, a long slice)
C2  programs built with them: the default build prints what CPython prints and no longer names the construct
"""
import ast
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / 'python' / 'pkg-v12'))


def marks(text):
    import bigcap
    saved = os.environ.get('AIL_SURFACE')
    os.environ['AIL_SURFACE'] = 'python'
    try:
        return bigcap.marked(ast.parse(text), local=False)
    finally:
        if saved is None:
            os.environ.pop('AIL_SURFACE', None)
        else:
            os.environ['AIL_SURFACE'] = saved


SHIFT = '''
import sys

NB = 11


def main():
    SH = 22
    vals = [int(t) for t in sys.stdin.read().split()]
    keys = []
    for p, v in enumerate(vals):
        keys.append((v << SH) | p)
        keys.append((v << NB) | p)
    keys.sort()
    print(keys[:5], keys[-1] >> SH, len(keys))


main()
'''

FROM_BYTES = '''
import sys


def main():
    data = sys.stdin.buffer.read()
    n = int.from_bytes(data[3:7], "little")
    pos = 0
    total = 0
    while pos + 2 <= len(data):
        total += int.from_bytes(data[pos:pos + 2], "big")
        pos += 2
    print(n, total, int.from_bytes(b"\\x01\\x02", "big"))


main()
'''


class Marks(unittest.TestCase):
    def test_c1_shift_by_named_constant(self):
        self.assertEqual(marks('def f(x):\n    SH = 22\n    return x << SH\n'), {})
        self.assertEqual(marks('K = 7\n\ndef f(x):\n    return x << K\n\nprint(f(3))\n'), {})
        self.assertEqual(marks('def f(x):\n    SH = 2\n    x <<= SH\n    return x\n'), {})
        hard = '`<<` by an amount that is not a constant'
        self.assertEqual(marks('def f(x, n):\n    return x << n\n')['f'], hard)
        self.assertEqual(marks('def f(x):\n    SH = 2\n    SH = 70\n    return x << SH\n')['f'], hard)
        self.assertEqual(marks('def f(x, SH):\n    SH = 2\n    return x << SH\n')['f'], hard)
        self.assertEqual(marks('def f(x):\n    global SH\n    SH = 2\n    return x << SH\n')['f'], hard)
        self.assertEqual(marks('def f(x):\n    for SH in range(80):\n        x = x << SH\n    return x\n')['f'], hard)
        self.assertEqual(marks('K = 7\n\ndef g():\n    global K\n    K = 90\n\ndef f(x):\n    return x << K\n')['f'], hard)

    def test_c1_short_from_bytes(self):
        self.assertEqual(marks('def f(s):\n    return int.from_bytes(s[3:7], "little")\n'), {})
        self.assertEqual(marks('def f(s, p):\n    return int.from_bytes(s[p:p + 4], "big")\n'), {})
        self.assertEqual(marks('def f():\n    return int.from_bytes(b"\\x01\\x02", "big")\n'), {})
        hard = 'a call of int.from_bytes'
        for call in ('s[p:]', 's[0:8]', 's[p:p + 9]', 's', 's[-3:4]'):
            self.assertEqual(marks('def f(s, p):\n    return int.from_bytes(%s, "big")\n' % call)['f'], hard, call)


def build(directory, text, name):
    source, exe = Path(directory, name + '.py'), Path(directory, name)
    source.write_text(text, encoding='utf-8')
    env = dict(os.environ)
    for k in ('AIL_UNIFIED_FORCE', 'AIL_NO_GENERAL'):
        env.pop(k, None)
    env['AIL_NO_CACHE'] = '1'
    r = subprocess.run([sys.executable, '-B', str(ROOT / 'ail_chatgpt.py'), 'compile', source.name, '--syntax', 'python',
                        '-o', exe.name], cwd=directory, capture_output=True, text=True, timeout=900, env=env)
    return r, source, exe


def run(cmd, data):
    r = subprocess.run(cmd, input=data, capture_output=True, timeout=120)
    return r.returncode, r.stdout


class Programs(unittest.TestCase):
    def check(self, text, inputs, construct):
        with tempfile.TemporaryDirectory() as d:
            r, source, exe = build(d, text, 'p')
            self.assertEqual(r.returncode, 0, r.stderr[-1500:])
            self.assertNotIn(construct, r.stderr)
            for data in inputs:
                self.assertEqual(run([str(exe)], data), run([sys.executable, str(source)], data), data)

    def test_c2_shift(self):
        self.check(SHIFT, [b'5 3 9 1\n', b'1000000 7 0\n', b'\n'], 'not a constant')

    def test_c2_from_bytes(self):
        self.check(FROM_BYTES, [bytes(range(40)), b'\xff' * 11, b'ab'], 'from_bytes')


if __name__ == '__main__':
    unittest.main()

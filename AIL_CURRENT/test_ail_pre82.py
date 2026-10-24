"""pre82: a space sign is kept in front of zero padding.

`f"{x: 010.2f}"` asks for a space sign flag and `0` padding, so CPython puts the sign
(one space) before the zeros: ` 000001.50`.  The general path's `ail__pad` only kept
`-`/`+` in front, so the space sign ended up after the zero fill: `00000 1.50`.  The
same helper serves `% 010.2f % x` (constant-folded to the same call), ints and bools.
Checked against CPython on the default build and the forced general path, including
widths that do not pad, negatives, `-0.0`, every align/fill combination, inf/nan, and
values reaching the format through an argument, a list item, an attribute and a dict
value.
"""
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent

SOURCE = r'''
class Box:
    def __init__(self, v):
        self.v = v


def fmt(x):
    return f"{x: 010.2f}"


def main():
    for v in (0.0, -0.0, 1.5, -1.5, 1e10, -1e10, 1e-10, -1e-10):
        for s in (" 010.2f", " 012.4f", " 010.0f", " 08.3e", " 08.3g", " 010.2%",
                  " 010.2", " 04.2f", " 01.2f", " 0.2f", "= 10.2f", "*= 10.2f",
                  "*< 10.2f", "*> 10.2f", "*^ 10.2f"):
            out = f"{v:{s}}"
            print(repr(v), repr(s), len(out), repr(out))
    for v in (0, 1, -1, 5, -5, 1000000000, True, False):
        for s in (" 04d", " 06d", " 01d", " 0d", " 04", " 10d",
                  "*=8d", "*<8d", "*>8d", "*^8d", " 08.0f"):
            out = f"{v:{s}}"
            print(repr(v), repr(s), len(out), repr(out))
    box = Box(1.5)
    values = {"k": -1.5, "i": 5}
    xs = [1.5, -1.5]
    print(fmt(1.5), fmt(xs[0]), fmt(box.v), fmt(values["k"]))
    print(f"{xs[1]: 010.2f}", f"{box.v: 012.4f}", f"{values['i']: 06d}")
    x = 1.5
    print(f"{x: 010.2f}", f"{x: 010.2f}", f"{x:+010.2f}", f"{x: 010.2f}", f"{x:010.2f}")
    x = -1.5
    print(f"{x: 010.2f}", f"{x: 06.2f}")
    x = 5
    print(f"{x: 05d}", f"{x: 05d}", f"{x:+05d}", f"{x:05d}")
    for v in (float("inf"), float("-inf"), float("nan")):
        print(f"{v: 010.2f}", f"{v:010.2f}", f"{v:+010.2f}")
    for v in (0, 1, -1, 5, -5, 12345):
        print("% 05d" % v, "% 010d" % v, "%- 08d" % v, "% 04d" % v, "%+010d" % v, "%010d" % v)
    for v in (0.0, -0.0, 1.5, -1.5, 1e10, -1e10):
        print("% 010.2f" % v, "% 012.4f" % v, "% 08.3e" % v, "% 010.2g" % v,
              "%+010.2f" % v, "%010.2f" % v, "%- 010.2f" % v)


main()
'''


def build_and_run(directory, text, name, force_general):
    source, exe = Path(directory, name + '.ail'), Path(directory, name)
    source.write_text(text, encoding='utf-8')
    env = dict(os.environ, AIL_NO_CACHE='1', AIL_IR='0')
    if force_general:
        env['AIL_UNIFIED_FORCE'] = '1'
    built = subprocess.run([sys.executable, '-B', str(ROOT / 'ail_chatgpt.py'), 'compile',
                            source.name, '--syntax', 'python', '-o', exe.name],
                           cwd=directory, capture_output=True, text=True, timeout=600, env=env)
    expected = subprocess.run([sys.executable, str(source)], capture_output=True, timeout=120)
    if built.returncode != 0:
        return built, None, expected
    return built, subprocess.run([str(exe)], capture_output=True, timeout=120), expected


class Pre82(unittest.TestCase):
    def check(self, name, force_general):
        with tempfile.TemporaryDirectory() as directory:
            built, ran, expected = build_and_run(directory, SOURCE, name, force_general)
            self.assertEqual(built.returncode, 0, built.stdout + built.stderr)
            self.assertEqual((ran.returncode, ran.stdout), (expected.returncode, expected.stdout),
                             ran.stderr)

    def test_space_sign_zero_pad_default(self):
        self.check('space_sign_d', False)

    def test_space_sign_zero_pad_general(self):
        self.check('space_sign_g', True)


if __name__ == '__main__':
    unittest.main()

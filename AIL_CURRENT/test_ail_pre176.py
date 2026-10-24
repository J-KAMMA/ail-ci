"""Dynamic non-BMP chr() on the general path (job pre176), against CPython 3.12.

`chr(0x1F600)` used to die with an internal error on the general path. The string backing now stores one
32-bit code point per unit, so a dynamic code point above U+FFFF is an ordinary one-character string in
both builds: length, ord, indexing, slicing, concatenation, comparison, dict keys, case mapping, encode,
%, format, f-strings and json all agree with CPython.
"""
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent
PYC = ROOT / 'python' / 'pkg-v12' / 'pyc.py'
HAVE_CC = shutil.which('gcc') is not None
sys.path.insert(0, str(ROOT))

PROGRAM = '''import json


class Holder:
    def __init__(self, c):
        self.c = c


def make(n):
    return chr(n)


def main():
    e = chr(0x1F600)
    o = chr(0x10001)
    m = chr(0x10FFFF)
    print(len(e), ord(e), repr(e))
    print(repr(e + o), repr((e + o)[0]), repr((e + o)[-1]), ord((e + o)[1]))
    print(e < o, o < m, e == chr(128512), sorted([o, e]))
    d = {e: "face", o: "plane"}
    print(d[e], d[o], len(d), e in d)
    xs = [chr(0x10000), chr(0x10400)]
    print([ord(x) for x in xs], repr(xs[1].lower()), repr(xs[1].upper()))
    h = Holder(e)
    print(repr(h.c), h.c.encode("utf-8"), len(h.c.encode()))
    print("%s|%r|%c" % (e, o, 0x10400))
    print("{}{}".format(e, o), f"{e}{o}")
    print(json.dumps(e, ensure_ascii=True))
    print(json.dumps(e, ensure_ascii=False))
    print(json.loads('"\\\\ud83d\\\\ude00"') == e)
    for n in (0x10000, 0x10FFFF):
        print(n, ord(make(n)))
    for n in (-1, 0x110000):
        try:
            chr(n)
        except ValueError as ex:
            print("ValueError", ex)


main()
'''


def surface(text):
    import ail_syntax
    return ail_syntax.fold_constants(ail_syntax.python_surface(text))


def build(directory, general):
    source = Path(directory, 'p.ail')
    exe = Path(directory, 'p_g' if general else 'p_d')
    env = dict(os.environ, AIL_NO_CACHE='1', AIL_IR='0')
    env.pop('AIL_NO_GENERAL', None)
    if general:
        source.write_text(surface(PROGRAM), encoding='utf-8')
        env['AIL_SURFACE'] = 'python'
        cmd = [sys.executable, '-B', str(PYC), exe.name, '--file', source.name, '--general-only']
    else:
        source.write_text(PROGRAM, encoding='utf-8')
        cmd = [sys.executable, '-B', str(ROOT / 'ail_chatgpt.py'), 'compile', source.name,
               '--syntax', 'python', '-o', exe.name]
    return subprocess.run(cmd, cwd=directory, capture_output=True, text=True, timeout=900, env=env), exe


@unittest.skipUnless(HAVE_CC, 'gcc is required')
class Pre176NonBmpChr(unittest.TestCase):
    def check(self, general):
        with tempfile.TemporaryDirectory() as d:
            res, exe = build(d, general)
            self.assertEqual(res.returncode, 0, res.stderr[-2000:])
            src = Path(d, 'cpython.py')
            src.write_text(PROGRAM, encoding='utf-8')
            want = subprocess.run([sys.executable, str(src)], cwd=d, capture_output=True, timeout=300)
            got = subprocess.run([str(exe)], cwd=d, capture_output=True, timeout=300)
            self.assertEqual(got.stdout, want.stdout)
            self.assertEqual(got.returncode, want.returncode, got.stderr[-500:])

    def test_general_path(self):
        self.check(True)

    def test_default_build(self):
        self.check(False)

"""repre20: non-BMP chr() on the general path is refused by name or stops with a named limit.

The general (boxed) path stores str as 16-bit UTF-16 units, so a code point above U+FFFF
cannot be represented.  A literal argument is refused at build time
("chr() of the non-BMP code point U+... in the 16-bit v2 runtime"); a value only known at
run time stops with the named limit "chr_non_bmp" (exit 3) instead of the old
"AIL internal error: chr() non-BMP code point requires 32-bit strings".  The default
(typed) build still produces CPython's astral character.  BMP boundaries and chr()'s
ValueError range errors are unchanged, and the limit is uncatchable like the others.
"""
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent
CLI = str(ROOT / 'ail_chatgpt.py')

RUNTIME = '''import sys


class Box:
    def __init__(self, n):
        self.n = n


def from_arg(n):
    return chr(n)


def from_list(n):
    xs = [n]
    return chr(xs[0])


def from_dict(n):
    d = {'k': n}
    return chr(d['k'])


def from_attr(n):
    return chr(Box(n).n)


def main():
    n = int(sys.stdin.readline())
    print(from_arg(n))
    print(from_list(n))
    print(from_dict(n))
    print(from_attr(n))


main()
'''

TRY = '''def f(n):
    try:
        print(chr(n))
    except Exception:
        print("caught")
    finally:
        print("finally")
    print("after")


f(0x1F600)
'''

TYPED = '''def f(n: int) -> str:
    return chr(n)


def via_list(n: int) -> str:
    xs = [n]
    return chr(xs[0])


def main() -> None:
    n = 0x1F600
    print(f(n))
    print(via_list(n))
    print(len(chr(n)), ord(chr(n)))


main()
'''


def cpython(directory, name, text, stdin=b''):
    src = Path(directory) / (name + '_cpython.py')
    src.write_text(text, encoding='utf-8')
    done = subprocess.run([sys.executable, '-B', str(src)], input=stdin, capture_output=True,
                          timeout=120, env=dict(os.environ, PYTHONUTF8='1'))
    return done.stdout.replace(b'\r\n', b'\n'), done.returncode, done.stderr


def build(directory, name, text, general):
    src = Path(directory) / (name + '.py')
    src.write_text(text, encoding='utf-8')
    exe = Path(directory) / ('exe_' + name + ('_g' if general else '_d'))
    env = dict(os.environ, AIL_NO_CACHE='1', AIL_QUIET_FALLBACK='1')
    env.pop('AIL_NO_GENERAL', None)
    if general:
        env['AIL_UNIFIED_FORCE'] = '1'
    else:
        env.pop('AIL_UNIFIED_FORCE', None)
    return subprocess.run([sys.executable, '-B', CLI, 'compile', src.name, '--syntax', 'python',
                           '-o', exe.name], cwd=directory, capture_output=True, text=True, timeout=900,
                          env=env), exe


def run(exe, directory, stdin=b''):
    done = subprocess.run([str(exe)], input=stdin, capture_output=True, timeout=120, cwd=directory)
    return (done.stdout.replace(b'\r\n', b'\n'), done.returncode,
            done.stderr.replace(b'\r\n', b'\n'))


class Repre20Tests(unittest.TestCase):
    def test_literal_non_bmp_is_refused_by_name_on_the_general_path(self):
        for code in (0x10000, 0x1F600, 0x10FFFF):
            text = 'print(chr(0x%X))\n' % code
            with tempfile.TemporaryDirectory(prefix='ail-repre20-') as directory:
                built, exe = build(directory, 'lit_%x' % code, text, True)
                output = built.stdout + built.stderr
                self.assertNotEqual(built.returncode, 0, output)
                self.assertFalse(exe.exists(), output)
                self.assertIn('chr() of the non-BMP code point U+%04X' % code, output)
                self.assertNotIn('AIL internal error', output)
                self.assertNotIn('Traceback', output)

    def test_literal_non_bmp_matches_cpython_on_the_default_build(self):
        text = 'print(chr(0x10000))\nprint(chr(0x1F600))\nprint(chr(0x10FFFF))\n'
        with tempfile.TemporaryDirectory(prefix='ail-repre20-') as directory:
            want, want_rc, err = cpython(directory, 'lit_default', text)
            self.assertEqual(want_rc, 0, err)
            built, exe = build(directory, 'lit_default_d', text, False)
            self.assertEqual(built.returncode, 0, built.stdout + built.stderr)
            got, rc, _ = run(exe, directory)
            self.assertEqual((got, rc), (want, want_rc))

    def test_runtime_value_stops_with_named_limit_on_the_general_path(self):
        with tempfile.TemporaryDirectory(prefix='ail-repre20-') as directory:
            want, want_rc, err = cpython(directory, 'runtime', RUNTIME, b'128512\n')
            self.assertEqual(want_rc, 0, err)
            self.assertEqual(want.count('😀'.encode('utf-8')), 4)
            built, exe = build(directory, 'runtime_g', RUNTIME, True)
            self.assertEqual(built.returncode, 0, built.stdout + built.stderr)
            got, rc, run_err = run(exe, directory, b'128512\n')
            self.assertEqual(rc, 3, run_err)
            self.assertIn(b'AIL limit: chr_non_bmp', run_err)
            self.assertNotIn(b'AIL internal error', run_err)
            self.assertEqual(got, b'')

    def test_runtime_value_through_a_single_source_stops_with_the_limit(self):
        programs = {
            'argument': 'def f(n):\n    return chr(n)\n\n\ndef main():\n'
                        '    n = 0x1F600\n    print(f(n))\n\n\nmain()\n',
            'list': 'def main():\n    n = 0x1F600\n    xs = [n]\n    print(chr(xs[0]))\n\n\nmain()\n',
            'dict': 'def main():\n    n = 0x1F600\n    d = {"k": n}\n    print(chr(d["k"]))\n\n\nmain()\n',
            'attribute': 'class Box:\n    def __init__(self, n):\n        self.n = n\n\n\n'
                         'def main():\n    n = 0x1F600\n    print(chr(Box(n).n))\n\n\nmain()\n',
        }
        for slug, text in programs.items():
            with tempfile.TemporaryDirectory(prefix='ail-repre20-') as directory:
                built, exe = build(directory, slug, text, True)
                self.assertEqual(built.returncode, 0, '%s\n%s' % (slug, built.stdout + built.stderr))
                got, rc, run_err = run(exe, directory)
                self.assertEqual(rc, 3, '%s\n%s' % (slug, run_err))
                self.assertIn(b'AIL limit: chr_non_bmp', run_err, slug)
                self.assertNotIn(b'AIL internal error', run_err, slug)
                self.assertEqual(got, b'', slug)

    def test_runtime_limit_is_uncatchable(self):
        with tempfile.TemporaryDirectory(prefix='ail-repre20-') as directory:
            built, exe = build(directory, 'try_g', TRY, True)
            self.assertEqual(built.returncode, 0, built.stdout + built.stderr)
            got, rc, run_err = run(exe, directory)
            self.assertEqual(rc, 3, run_err)
            self.assertIn(b'AIL limit: chr_non_bmp', run_err)
            self.assertEqual(got, b'')
            self.assertNotIn(b'caught', got)
            self.assertNotIn(b'finally', got)
            self.assertNotIn(b'after', got)

    def test_typed_runtime_value_matches_cpython_on_the_default_build(self):
        with tempfile.TemporaryDirectory(prefix='ail-repre20-') as directory:
            want, want_rc, err = cpython(directory, 'typed', TYPED)
            self.assertEqual(want_rc, 0, err)
            built, exe = build(directory, 'typed_d', TYPED, False)
            self.assertEqual(built.returncode, 0, built.stdout + built.stderr)
            got, rc, _ = run(exe, directory)
            self.assertEqual((got, rc), (want, want_rc))

    def test_bmp_boundary_matches_cpython_on_both_builds(self):
        text = ('for n in (0, 1, 0x7f, 0x80, 0xff, 0x3a9, 0xfffe, 0xffff):\n'
                '    c = chr(n)\n'
                '    print(n, c == chr(n), len(c), ord(c))\n'
                'print(chr(0xFFFF) == "\\uffff")\n')
        with tempfile.TemporaryDirectory(prefix='ail-repre20-') as directory:
            want, want_rc, err = cpython(directory, 'bmp', text)
            self.assertEqual(want_rc, 0, err)
            for general in (True, False):
                built, exe = build(directory, 'bmp_%s' % ('g' if general else 'd'), text, general)
                self.assertEqual(built.returncode, 0, built.stdout + built.stderr)
                got, rc, _ = run(exe, directory)
                self.assertEqual((got, rc), (want, want_rc), 'general=%s' % general)

    def test_out_of_range_chr_still_matches_cpython(self):
        text = ('for n in (-1, -0x10000, 0x110000, 0x110001):\n'
                '    try:\n'
                '        print(chr(n))\n'
                '    except ValueError as e:\n'
                '        print("ValueError", e)\n')
        with tempfile.TemporaryDirectory(prefix='ail-repre20-') as directory:
            want, want_rc, err = cpython(directory, 'range', text)
            self.assertEqual(want_rc, 0, err)
            for general in (True, False):
                built, exe = build(directory, 'range_%s' % ('g' if general else 'd'), text, general)
                self.assertEqual(built.returncode, 0, built.stdout + built.stderr)
                got, rc, _ = run(exe, directory)
                self.assertEqual((got, rc), (want, want_rc), 'general=%s' % general)


if __name__ == '__main__':
    unittest.main()

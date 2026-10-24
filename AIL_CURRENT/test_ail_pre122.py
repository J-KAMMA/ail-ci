"""Pre-existing differences revisited (job pre122).

The 16-bit general runtime stores a non-BMP character as a surrogate pair, one CPython
character, so `chr(0x1F600)` and a format-spec fill made from it now match CPython instead of
stopping with an uncatchable "requires 32-bit strings" error. That includes values arriving
through an argument, a list item, an attribute and a dict value, and the string operations a
surrogate pair implies (len/ord/repr/index/slice/iteration/comparison/encode/decode). A lone
surrogate still has no printable representation and a constant `chr()` of one is refused by
name. BMP fills (including non-Latin-1 ones) and every BMP chr() still match CPython, and
out-of-range chr() arguments still raise CPython's ValueError.

The exact cases are compared with CPython on the default build and on the forced general path.
"""
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent

NON_BMP_FILL = '''
print(repr(format("x", chr(0x1F600) + ">5")))
print(repr(f"{'x':{chr(0x1F600)}>5}"))
print(repr(format(42, chr(0x1F600) + "^8d")))
'''

NON_BMP_DYNAMIC = '''
def mk(n):
    return chr(n)


class Box:
    def __init__(self, v):
        self.v = v


s = mk(0x1F600)
xs = [mk(0x1F600)]
d = {"k": mk(0x1F600)}
b = Box(mk(0x1F600))
for v in (s, xs[0], d["k"], b.v):
    print(len(v), ord(v), repr(v))
    print(repr(format("x", v + ">4")))
    print(repr(f"{'x':{v}<4}"))
    print(repr(format(-7, v + "^7d")))
'''

NON_BMP_STRING_OPS = '''
def mk(n):
    return chr(n)


s = mk(0x1F600)
t = mk(0x10000)
print(repr(s), repr(t))
print(len(s), ord(s), repr(s[0]), repr(s[-1]))
print(repr(s + s), repr(s * 2))
print(list(s), list(reversed(s)))
print(s == mk(0x1F600), s < "\\uE000", s > "\\uE000", t < "\\uE000")
print(repr(s[::-1]), repr(s[0:2]))
print(repr("abc".join([s, t])))
print(repr(s.encode("utf-8")))
print(repr(b'\\xf0\\x9f\\x98\\x80'.decode("utf-8")))
'''

NON_BMP_CONSTANT = '''
print(repr(chr(0x1F600 + 0)))
'''

NON_BMP_DEAD = '''
def f():
    return chr(0x1F600)


print("ok", len("ok"))
'''

SURROGATE_CHR = '''
print(repr(chr(0xD800)))
'''

BMP_FILL = '''
class Box:
    def __init__(self, spec):
        self.spec = spec


def fmt(v, spec):
    return format(v, spec)


def main():
    specs = ["日>5", "é^7", "*<4"]
    d = {"s": "日>5"}
    b = Box("é>6")
    print(repr(format("x", specs[0])))
    print(repr(format("x", "日>5")))
    print(repr(format("x", d["s"])))
    print(repr(f"{'ab':{specs[0]}}"))
    print(repr(fmt("ab", specs[2])))
    print(repr(f"{'x':{b.spec}}"))
    print(repr(f"{'':日>3}"))
    print(repr(f"{'abc':日>2}"))
    print(repr(f"{42:日^8d}"))
    print(repr(f"{-42:é>9d}"))
    print(repr(f"{-3.5:日<10.2f}"))
    print(repr(fmt(0, "*^5d")))
    print(repr(fmt(-1, "*^5d")))
    print(repr(fmt("abcdef", "日>8.3")))
    print(repr(fmt("abcdef", "é<8.3")))


main()
'''

CHR_BOUNDARIES = '''
def main():
    for n in (0, 65, 0x263A, 0xD7FF, 0xE000, 0xFFFF, 0x10000, 0x1F600, 0x10FFFF):
        c = chr(n)
        print(n, repr(c), len(c), ord(c))
    for n in (-1, 0x110000):
        try:
            print(repr(chr(n)))
        except ValueError as e:
            print("ValueError", e)


main()
'''


def _cpython(directory, name, text):
    src = Path(directory) / (name + '_cpython.py')
    src.write_text(text, encoding='utf-8')
    done = subprocess.run([sys.executable, '-B', str(src)], capture_output=True, timeout=120,
                          env=dict(os.environ, PYTHONUTF8='1'))
    return done.stdout.replace(b'\r\n', b'\n'), done.returncode, done.stderr


def _build(directory, name, text, general):
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
    return built, exe


def _run(exe, directory):
    got = subprocess.run([str(exe)], capture_output=True, timeout=120, cwd=directory)
    return got.stdout.replace(b'\r\n', b'\n'), got.returncode, got.stderr.decode('utf-8', 'replace')


class Pre122Tests(unittest.TestCase):
    def check(self, slug, text):
        with tempfile.TemporaryDirectory(prefix='ail-pre122-') as directory:
            want, want_rc, err = _cpython(directory, slug, text)
            self.assertEqual(want_rc, 0, err)
            for general in (True, False):
                built, exe = _build(directory, '%s_%s' % (slug, 'g' if general else 'd'), text, general)
                self.assertEqual(built.returncode, 0, (built.stdout + built.stderr)[-2000:])
                got = _run(exe, directory)
                self.assertEqual(got[:2], (want, want_rc),
                                 '%s (general=%s)\n%s' % (text[:1000], general, got[2][-1500:]))

    def refused(self, slug, text, name):
        with tempfile.TemporaryDirectory(prefix='ail-pre122-') as directory:
            for general in (True, False):
                built, _exe = _build(directory, '%s_%s' % (slug, 'g' if general else 'd'), text, general)
                output = built.stdout + built.stderr
                self.assertNotEqual(built.returncode, 0, '%s built (general=%s)' % (slug, general))
                self.assertIn('not in the subset', output, output[-2000:])
                self.assertIn(name, output, output[-2000:])

    def test_non_bmp_format_fill_matches_cpython(self):
        self.check('non_bmp_fill', NON_BMP_FILL)

    def test_non_bmp_through_arguments_lists_attrs_dicts(self):
        self.check('non_bmp_dynamic', NON_BMP_DYNAMIC)

    def test_non_bmp_string_operations_match_cpython(self):
        self.check('non_bmp_ops', NON_BMP_STRING_OPS)

    def test_non_bmp_constant_expression_matches_cpython(self):
        self.check('non_bmp_constant', NON_BMP_CONSTANT)

    def test_uncalled_non_bmp_function_still_builds(self):
        self.check('non_bmp_dead', NON_BMP_DEAD)

    def test_lone_surrogate_chr_is_refused_by_name(self):
        self.refused('surrogate_chr', SURROGATE_CHR, 'chr() of U+D800 is refused')

    def test_bmp_fill_matches_cpython(self):
        self.check('bmp_fill', BMP_FILL)

    def test_chr_boundaries_match_cpython(self):
        self.check('chr_boundaries', CHR_BOUNDARIES)


if __name__ == '__main__':
    unittest.main()

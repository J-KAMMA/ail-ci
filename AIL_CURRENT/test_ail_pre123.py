"""Pre-existing CPython differences from job pre91, first item: UTF-8 decode of a
non-BMP code point must not die on the general path.  A non-BMP code point is
stored as a UTF-16 surrogate pair there, so every public string operation has to
work in code points, not storage units.
"""
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent

DECODE = r"""def main() -> None:
    em = b'\xf0\x9f\x98\x80'.decode('utf-8')
    mu = b'\xf0\x9d\x84\x9e'.decode('utf-8')
    s = 'a' + em + 'b' + mu + 'c'
    print(repr(em), repr(mu), repr(s))
    print(len(em), len(mu), len(s), s[0], s[1], s[2], s[3], s[4], s[-1])
    print([repr(c) for c in s], [ord(c) for c in s])
    print(repr(s[1:3]), repr(s[::2]), repr(s[::-1]), repr(s[1:5:2]), repr(s[4:0:-2]))
    print(s == 'a' + em + 'b' + mu + 'c', s < 'a' + em + 'b' + mu + 'd', s > 'a')
    print(em in s, mu in s, 'ab' in s, 'a' + em in s, em + 'b' in s)
    print(s.find(em), s.rfind(mu), s.count(em), s.index(mu), s.startswith('a' + em), s.endswith(mu + 'c'))
    print(repr(s.replace(em, 'X')), repr(s.replace('', '-')), repr(s.replace(mu, '')))
    print(repr(s.split(em)), repr(s.split(mu)), repr(('x' + em + 'y').partition(em)))
    print(repr((' ' + em + 'x' + mu + ' ').strip()), repr((em + 'z' + mu).strip(em + mu)))
    print(repr((em + mu).ljust(5, '.')), repr((em + mu).center(6, '.')))
    print('%s|%r|%5s|%.1s' % (em, em, em + '!', em + '!'))
    print('{}|{!r}|{:>4}'.format(em, em, em + '!'))
    print(repr(em.encode('utf-8')), repr(em.encode('ascii', 'replace')), repr(em.encode('latin-1', 'replace')))


main()
"""

OPS = r"""def main() -> None:
    em = b'\xf0\x9f\x98\x80'.decode()
    em2 = b'\xf0\x9f\x98\x81'.decode()
    mu = b'\xf0\x9d\x84\x9e'.decode()
    s = 'x' + em + 'y' + em2 + 'z' + em + 'w'
    print(repr(s.split(em)), repr(s.split(em, 0)), repr(s.split(em, 1)), repr(s.split(em, 2)))
    print(repr(s.rsplit(em)), repr(s.rsplit(em, 0)), repr(s.rsplit(em, 1)), repr(s.rsplit(em, 2)))
    print(repr(s.split(em2)), repr(s.rsplit(em2)), repr(s.rsplit('z' + em)))
    print(repr(s.replace(em, '_')), repr(s.replace(em, '_', 0)), repr(s.replace(em, '_', 1)), repr(s.replace(em, '_', 5)))
    print(repr(s.replace('', '.')), repr(s.replace('', '.', 0)), repr(s.replace('', '.', 1)), repr(s.replace('', '.', 3)))
    print(repr(s.replace(em2, em + em2, 1)), repr(s.replace(em, '', 5)))
    print(repr(s.find(em, 2)), repr(s.rfind(em, 0, 6)), repr(s.find(em2, 3, 5)), repr(s.rfind(em2, 3, 5)))
    print(repr(s.count(em)), repr(s.count(em, 2)), repr(s.count(em, 0, 6)))
    print(repr(s.startswith(em, 1)), repr(s.endswith(em, 0, 6)))
    t = em + em + em
    print(repr(t.find(em + em)), repr(t.rfind(em + em)), repr(t.count(em + em)), repr(t.replace(em + em, 'X')))
    print(repr(t.split(em + em)), repr(t.rsplit(em + em)), repr(t.split(em + em, 1)), repr(t.rsplit(em + em, 1)))
    print(repr((em + mu + em * 2).rfind(em, 1)), repr((em + mu + em * 2).rfind(em, 0, 2)))
    print(repr((em + em).strip(em)), repr((em + 'a' + em).strip(em)), repr((em + mu).rstrip(em)), repr((mu + em).lstrip(em)))


main()
"""

CARRIERS = r"""def take(s: str) -> str:
    return s


def main() -> None:
    em = b'\xf0\x9f\x98\x80'.decode('utf-8')
    print(repr(take(em)), len(take(em)))
    xs = [em, b'\xf0\x9f\x98\x81'.decode('utf-8')]
    print(repr(xs), len(xs[0]), ord(xs[0]))
    d = {'k': em}
    print(repr(d['k']), len(d['k']))
    print(repr(bytearray(b'\xf0\x9f\x98\x80').decode('utf-8')))
    for c in em:
        print(repr(c), ord(c))
    for c in reversed(em + 'a'):
        print(repr(c))
    print(repr(chr(0x1F600)), len(chr(0x1F600)), ord(chr(0x1F600)))
    print(repr(chr(0x10000)), repr(chr(0x10FFFF)), len(chr(0x10FFFF)))
    print(repr(b'a\xffb'.decode('utf-8', 'replace')), repr(b'a\xffb'.decode('utf-8', 'ignore')))
    print(repr(b'\xff\x80\x00'.decode('latin-1')))
    try:
        b'\xf0\x9f\x98'.decode('utf-8')
    except UnicodeDecodeError as e:
        print(type(e).__name__, str(e))
    try:
        b'\x80'.decode('ascii')
    except UnicodeDecodeError as e:
        print(type(e).__name__, str(e))


main()
"""

CASES = [
    ('decode_astral', DECODE),
    ('astral_operations', OPS),
    ('astral_carriers_errors', CARRIERS),
]


def build_and_run(directory, text, name, ir):
    source, exe = Path(directory, name + '.ail'), Path(directory, name)
    source.write_text(text, encoding='utf-8')
    env = dict(os.environ, AIL_IR='1' if ir else '0')
    built = subprocess.run([sys.executable, '-B', str(ROOT / 'ail_chatgpt.py'), 'compile', source.name,
                            '--syntax', 'python', '-o', exe.name], cwd=directory,
                           capture_output=True, text=True, timeout=600, env=env)
    expected = subprocess.run([sys.executable, str(source)], capture_output=True, timeout=60)
    if built.returncode != 0:
        return built, None, expected
    return built, subprocess.run([str(exe)], capture_output=True, timeout=120), expected


class Pre123NonBmpDecode(unittest.TestCase):
    def check(self, slug, text, ir):
        with tempfile.TemporaryDirectory() as directory:
            built, ran, expected = build_and_run(directory, text, slug + ('_ir' if ir else ''), ir)
            self.assertEqual(expected.returncode, 0, expected.stderr)
            self.assertEqual(built.returncode, 0, built.stdout + built.stderr)
            self.assertEqual((ran.returncode, ran.stdout), (expected.returncode, expected.stdout), ran.stderr)

    def test_cases_default(self):
        for slug, text in CASES:
            with self.subTest(slug):
                self.check(slug, text, False)

    def test_cases_ir(self):
        for slug, text in CASES:
            with self.subTest(slug):
                self.check(slug, text, True)


if __name__ == '__main__':
    unittest.main()

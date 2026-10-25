"""Differential fuzz round 22: str.title / capitalize / swapcase / casefold over all of Unicode.

Found with small random programs compared against CPython on both builds:

The general (boxed) runtime implemented title/capitalize/swapcase/casefold as ASCII-only
methods and stopped the program with `AIL limit: str_title_nonascii` (or
`str_lower_nonascii`) on any code point above U+007F.  CPython, of course, maps those
characters: `"ǆ".title()` is `"ǅ"`, `"ß".capitalize()` is `"Ss"`, `"ΑΣ".swapcase()` is
`"ας"` (final sigma), and `"İ".casefold()` is `"i̇"`.

The boxed path now uses the same CPython-derived Unicode tables the typed path already
used, over its UTF-16 strings, so both builds print CPython's answers.  This test checks
every BMP code point on its own, the multi-character rules (word boundaries, final sigma,
titlecase characters, expanding mappings), and random strings built from those pieces.

Strings are passed as UTF-8 hex so NULs, newlines and every BMP code point are legal
receivers.  Non-BMP construction is still outside the 16-bit general runtime (chr() and
bytes.decode report that separately), so this round covers the BMP.
"""
import os
import random
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent

SOURCE = r'''def show(s: str) -> str:
    return "|".join([s.encode().hex(), s.title().encode().hex(),
                     s.capitalize().encode().hex(), s.swapcase().encode().hex(),
                     s.casefold().encode().hex(), "1" if s.istitle() else "0"])


def main() -> int:
    text: str = read_bytes(sys.argv[1]).decode("utf-8")
    out: list[str] = []
    for line in text.split("\n"):
        out.append(show(bytes.fromhex(line).decode("utf-8")))
    write_stdout_bytes("\n".join(out).encode("utf-8"))
    return 0


main()
'''

PIECES = ['', 'a', 'A', 'z', 'Z', '0', '9', ' ', '\t', '\n', '.', '-', "'",
          'ß', 'ẞ', 'İ', 'ı', 'Σ', 'σ', 'ς', 'Ǆ', 'ǅ', 'ǆ', 'Ǉ', 'ǈ', 'ǉ',
          'ᾈ', 'ᾀ', 'ᾼ', 'ῼ', 'ŉ', 'ǰ', 'ﬀ', 'ﬃ', 'ﬓ', 'ΐ', 'ΰ',
          'é', 'É', 'ö', 'Ö', '日', '本', '٣', '²', '½', 'Ⅷ', 'ʰ', 'ª',
          '\u0301', '\u0345', '\u00ad', '\u200d', '\u200c', '\u0085',
          '\u00a0', '\u2003', '\u3000', 'A\u0301', '\u03a3\u0301']


def expected(s):
    return '|'.join([s.encode('utf-8').hex(), s.title().encode('utf-8').hex(),
                     s.capitalize().encode('utf-8').hex(), s.swapcase().encode('utf-8').hex(),
                     s.casefold().encode('utf-8').hex(), '1' if s.istitle() else '0'])


def _cpython(directory, name, text):
    src = Path(directory) / (name + '_cpython.py')
    src.write_text(text, encoding='utf-8')
    done = subprocess.run([sys.executable, '-B', str(src)], capture_output=True, timeout=120,
                          env=dict(os.environ, PYTHONUTF8='1'))
    return done.stdout.replace(b'\r\n', b'\n'), done.returncode, done.stderr


def _build_and_run(directory, name, text, general, data=None):
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
    got = subprocess.run([str(exe)] + ([str(data)] if data is not None else []),
                         capture_output=True, timeout=300, cwd=directory)
    return (got.stdout.replace(b'\r\n', b'\n'), got.returncode), got.stderr.decode('utf-8', 'replace')[-1500:]


class Fuzz22Tests(unittest.TestCase):
    def test_case_methods_all_unicode(self):
        rng = random.Random(20261122)
        cases = [chr(cp) for cp in range(0x10000) if not 0xD800 <= cp <= 0xDFFF]
        cases += [''.join(rng.choice(PIECES) for _ in range(rng.randrange(0, 10))) for _ in range(8000)]
        cases += ['', 'Ab Cd', 'AB CD', 'ab cd', 'ǅa', 'aǅ', 'ǄǄ', 'ǅǅ', 'ΑΣ', 'ΣΣ', 'ΣΣΣ',
                  'aΣ', 'Σa', 'ß', 'ßß', 'İ', 'i̇', '\u03a3\u0301', 'ᾈΣ', 'Ǆǅǆ']
        data = '\n'.join(s.encode('utf-8').hex() for s in cases)
        want = [expected(s) for s in cases]
        with tempfile.TemporaryDirectory(prefix='ail-fuzz22-') as directory:
            src = Path(directory) / 'case_all.py'
            src.write_text(SOURCE, encoding='utf-8')
            data_path = Path(directory) / 'cases.txt'
            data_path.write_text(data, encoding='utf-8')
            reference = '\n'.join(want).encode('utf-8')
            for general in (True, False):
                got, build_err = _build_and_run(directory, 'case_all_%s' % ('g' if general else 'd'),
                                                SOURCE, general, data_path)
                self.assertIsNotNone(got, 'general=%s\n%s' % (general, build_err))
                out, rc = got
                if (out, rc) != (reference, 0):
                    lines = out.split(b'\n')
                    want = reference.split(b'\n')
                    for i in range(min(len(lines), len(want))):
                        if lines[i] != want[i]:
                            self.fail('general=%s line %d, case %r: got %r want %r\n%s'
                                      % (general, i, cases[i], lines[i], want[i], build_err))
                    self.fail('general=%s: %d lines, %d bytes, want %d lines, %d bytes\n%s'
                              % (general, len(lines), len(out), len(want), len(reference), build_err))


if __name__ == '__main__':
    unittest.main()

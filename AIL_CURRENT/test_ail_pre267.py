"""Pre-267: non-BMP bytes.decode() is refused by name on the 16-bit general runtime.

The rbpre51 review recorded the general path's ``b"\\xf0\\x9f\\x98\\x80".decode()`` still
stopping with ``AIL internal error: decode: a code point above U+FFFF``.  The default build
already prints the astral character.  The general runtime keeps UTF-16 units, so a statically
known decode whose text contains a non-BMP code point is now refused at compile time, including
through module constants and aliases, list/tuple/dict literals, class attributes, simple
identity calls, ``bytes([...])`` / ``bytearray(...)`` and a function parameter; BMP text and
invalid UTF-8 keep their run-time behaviour.
"""
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent

REFUSED = {
    'literal': '''def main():
    print(b'\\xf0\\x9f\\x98\\x80'.decode())


main()
''',
    'module_alias': '''DATA = b'\\xf0\\x9f\\x98\\x80'
ALIAS = DATA


def main():
    print(ALIAS.decode())


main()
''',
    'containers': '''def main():
    xs = [b'\\xf0\\x9f\\x98\\x80']
    d = {'k': b'\\xf0\\x9f\\x98\\x80'}
    t = (b'\\xf0\\x9f\\x98\\x80',)
    print(xs[0].decode())
    print(d['k'].decode())
    print(t[0].decode())


main()
''',
    'argument': '''def identity(v):
    return v


def show(data):
    print(data.decode())


def main():
    print(identity(b'\\xf0\\x9f\\x98\\x80').decode())
    show(b'\\xf0\\x9f\\x98\\x80')


main()
''',
    'attribute': '''class Box:
    data = b'\\xf0\\x9f\\x98\\x80'


def main():
    print(Box.data.decode())


main()
''',
    'str_call': '''def main():
    print(str(b'\\xf0\\x9f\\x98\\x80', 'utf-8'))


main()
''',
    'constructors': '''def main():
    print(bytes([240, 159, 152, 128]).decode())
    print(bytearray(b'\\xf0\\x9f\\x98\\x80').decode())


main()
''',
    'encoding_keyword': '''def main():
    print(b'\\xf0\\x9f\\x98\\x80'.decode(encoding='utf-8', errors='strict'))


main()
''',
    'low_non_bmp': '''def main():
    print(b'\\xf0\\x90\\x80\\x80'.decode())


main()
''',
    'high_non_bmp': '''def main():
    print(b'\\xf4\\x8f\\xbf\\xbf'.decode())


main()
''',
}

MATCHES = r'''def show(data):
    try:
        s = data.decode()
        print(repr(s), len(s))
    except Exception as e:
        print(type(e).__name__, str(e))


def main():
    for data in (b'', b'abc', b'h\xc3\xa9llo', b'\xe4\xb8\xad', b'\xef\xbf\xbf',
                 b'\xed\xa0\x80', b'\xc0\xaf', b'\xf4\x90\x80\x80', b'\xf0\x9f\x98',
                 b'\xff', b'a\xe4\xb8x'):
        show(data)
    print(b'h\xc3\xa9llo'.decode('utf-8'))
    print(b'h\xe9llo'.decode('latin-1'))
    print(b'\xff'.decode('utf-8', 'replace'))
    print(b'\xff'.decode('utf-8', 'ignore'))
    print(str(b'h\xc3\xa9llo', 'utf-8'))
    data = bytearray(b'\xf0\x9f\x98\x80')
    data.clear()
    data.extend(b'ok')
    print(data.decode())
    xs = [b'\xf0\x9f\x98\x80']
    alias = xs
    alias[0] = b'ok'
    print(xs[0].decode())
    d = {'k': b'\xf0\x9f\x98\x80'}
    d['k'] = b'ok'
    print(d['k'].decode())


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


def _run(directory, name, text, general):
    built, exe = _build(directory, name, text, general)
    if built.returncode != 0:
        return None, (built.stdout + built.stderr)[-3000:]
    got = subprocess.run([str(exe)], capture_output=True, timeout=120, cwd=directory)
    return (got.stdout.replace(b'\r\n', b'\n'), got.returncode), got.stderr.decode('utf-8', 'replace')[-1500:]


class Pre267Tests(unittest.TestCase):
    def test_non_bmp_decode_is_refused_by_name(self):
        for slug, text in REFUSED.items():
            with tempfile.TemporaryDirectory(prefix='ail-pre267-') as directory:
                for general in (True, False):
                    name = '%s_%s' % (slug, 'g' if general else 'd')
                    built, exe = _build(directory, name, text, general)
                    output = built.stdout + built.stderr
                    if built.returncode != 0:
                        self.assertFalse(exe.exists(), '%s (general=%s) built an executable' % (slug, general))
                        self.assertIn('non-BMP', output, '%s (general=%s)\n%s' % (slug, general, output[-3000:]))
                        continue
                    if general:
                        self.fail('%s (general) built\n%s' % (slug, output[-3000:]))
                    got = subprocess.run([str(exe)], capture_output=True, timeout=120, cwd=directory)
                    want, want_rc, err = _cpython(directory, name, text)
                    self.assertEqual(want_rc, 0, err)
                    self.assertEqual((got.stdout.replace(b'\r\n', b'\n'), got.returncode), (want, want_rc),
                                     '%s (default)\n%s' % (slug, output[-3000:]))

    def test_bmp_and_invalid_utf8_decode_matches_cpython(self):
        with tempfile.TemporaryDirectory(prefix='ail-pre267-') as directory:
            want, want_rc, err = _cpython(directory, 'matches', MATCHES)
            self.assertEqual(want_rc, 0, err)
            for general in (True, False):
                got, build_err = _run(directory, 'matches_%s' % ('g' if general else 'd'), MATCHES, general)
                self.assertIsNotNone(got, 'general=%s\n%s' % (general, build_err))
                self.assertEqual(got, (want, want_rc), 'general=%s\n%s' % (general, build_err))


if __name__ == '__main__':
    unittest.main()

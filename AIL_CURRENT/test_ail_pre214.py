"""Pre-214: a constant ``abs(MIN)`` is refused by name.

AIL integers are fixed width.  ``abs(-(2 ** 63))`` is 2**63, which int64 cannot hold, so both
builds used to stop at run time with ``integer overflow`` while CPython prints the bignum.  A
statically known ``abs`` of the int64 minimum is now refused at compile time with the existing
``int64 constant expression out of range`` wording, wherever the call appears.  In-range constant
absolutes, float/bool arguments, and a shadowed ``abs`` still match CPython.
"""
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent

OUT_OF_RANGE = {
    'pow': '''def main():
    print(abs(-(2 ** 63)))


main()
''',
    'shift': '''def main():
    print(abs(-(1 << 63)))


main()
''',
    'literal': '''def main():
    print(abs(-9223372036854775808))


main()
''',
    'module_constant': '''MIN = -(2 ** 63)


def main():
    print(abs(MIN))


main()
''',
    'argument': '''def show(v):
    print(v)


def main():
    show(abs(-(2 ** 63)))


main()
''',
    'list_item': '''def main():
    print([abs(-(2 ** 63))][0])


main()
''',
    'attribute': '''class Box:
    v = abs(-(2 ** 63))


def main():
    print(Box.v)


main()
''',
    'dict_value': '''def main():
    print({"v": abs(-(2 ** 63))}["v"])


main()
''',
}

IN_RANGE = '''def main():
    print(abs(-(2 ** 62)), abs(-(2 ** 63 - 1)), abs(-(1 << 62)), abs(-0), abs(-1), abs(0), abs(1))
    print(repr(abs(-0.0)), repr(abs(-2.5)))
    print(abs(-True), abs(False))


main()
'''

SHADOWED = '''def abs(x):
    return 0


def main():
    print(abs(-(2 ** 63)))


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


class Pre214Tests(unittest.TestCase):
    def refused(self, slug, text):
        # exact ints (bigint): builds and matches CPython (stdout, exit code)
        with tempfile.TemporaryDirectory(prefix='ail-pre214-') as directory:
            want, want_rc, err = _cpython(directory, slug, text)
            for general in (True, False):
                got, build_err = _run(directory, '%s_%s' % (slug, 'g' if general else 'd'),
                                      text, general)
                self.assertIsNotNone(got, '%s (general=%s)\n%s' % (slug, general, build_err))
                self.assertEqual(got, (want, want_rc), '%s (general=%s)\n%s' % (slug, general, build_err))

    def matches(self, slug, text):
        with tempfile.TemporaryDirectory(prefix='ail-pre214-') as directory:
            want, want_rc, err = _cpython(directory, slug, text)
            self.assertEqual(want_rc, 0, err)
            for general in (True, False):
                got, build_err = _run(directory, '%s_%s' % (slug, 'g' if general else 'd'),
                                      text, general)
                self.assertIsNotNone(got, '%s (general=%s)\n%s' % (slug, general, build_err))
                self.assertEqual(got, (want, want_rc), '%s (general=%s)\n%s' % (slug, general, build_err))

    def test_constant_abs_of_int64_minimum_is_refused(self):
        for slug, text in OUT_OF_RANGE.items():
            self.refused(slug, text)

    def test_in_range_constant_absolutes_match_cpython(self):
        self.matches('in_range', IN_RANGE)

    def test_shadowed_abs_is_not_folded(self):
        self.matches('shadowed', SHADOWED)


if __name__ == '__main__':
    unittest.main()

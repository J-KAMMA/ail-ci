"""Pre-241: constant shifts of bools fold like CPython's ints.

A bool is an int subclass in CPython, so ``True << 64`` is the exact bignum 2**64 and
``(True << 64) >> 64`` is 1.  The constant folders treated only ``type(x) is int`` as a
constant int, so both builds compiled the bool shift with the fixed-width runtime and stopped
with ``integer overflow``.  Bool constants now take part in the same exact folding as int
constants: a result that fits int64 is emitted as a literal (the shrinking shifts included),
and a result outside int64 is refused by name, like the existing int-constant rule.  A bool
result of ``&``, ``|`` or ``^`` is still left to the runtime so it keeps printing True/False.
"""
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent

OUT_OF_RANGE = {
    'shift_64': '''def main():
    print(True << 64)


main()
''',
    'shift_4096': '''def main():
    print(True << 4096)


main()
''',
    'shift_63': '''def main():
    print(True << 63)


main()
''',
    'shift_65': '''def main():
    print(True << 65)
    print(False)


main()
''',
    'dead_code': '''def main():
    if False:
        print(True << 64)
    print("done")


main()
''',
    'bool_or': '''def main():
    print((False | True) << 64)


main()
''',
    'argument': '''def show(v):
    print(v)


def main():
    show(True << 64)


main()
''',
    'list_item': '''def main():
    print([True << 64][0])


main()
''',
    'attribute': '''class Box:
    v = True << 64


def main():
    print(Box.v)


main()
''',
    'dict_value': '''def main():
    print({"v": True << 64}["v"])


main()
''',
}

IN_RANGE = '''def main():
    print((True << 64) >> 64)
    print((True << 100000) >> 100000)
    print((True << 63) >> 63)
    print(True << 62)
    print(True << 0, True >> 64, True >> 4096)
    print(False << 64, False << 4096)
    print((False << 100000) >> 100000)
    print((False | True) << 62)
    print((True & True) >> 64)
    print(True & False, True | False, True ^ True)
    print(+True, -True, ~True)
    print([(True << 64) >> 64][0])
    print({"v": (True << 64) >> 64}["v"])


main()
'''

IN_RANGE_ARGUMENT = '''def show(v):
    print(v)


def main():
    show((True << 64) >> 64)


main()
'''

MAXSPLIT_OUT_OF_RANGE = '''def main():
    print("a b c".split(" ", True << 64))


main()
'''

MAXSPLIT_IN_RANGE = '''def main():
    print("a b c".split(" ", (True << 64) >> 64))


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


class Pre241Tests(unittest.TestCase):
    def refused(self, slug, text, message='outside the signed 64-bit range'):
        with tempfile.TemporaryDirectory(prefix='ail-pre241-') as directory:
            for general in (True, False):
                name = '%s_%s' % (slug, 'g' if general else 'd')
                built, exe = _build(directory, name, text, general)
                output = built.stdout + built.stderr
                self.assertNotEqual(built.returncode, 0,
                                    '%s (general=%s)\n%s' % (slug, general, output[-3000:]))
                self.assertFalse(exe.exists(), '%s (general=%s) built an executable' % (slug, general))
                self.assertIn('not in the subset', output,
                              '%s (general=%s)\n%s' % (slug, general, output[-3000:]))
                self.assertIn(message, output, '%s (general=%s)\n%s' % (slug, general, output[-3000:]))

    def matches(self, slug, text):
        with tempfile.TemporaryDirectory(prefix='ail-pre241-') as directory:
            want, want_rc, err = _cpython(directory, slug, text)
            self.assertEqual(want_rc, 0, err)
            for general in (True, False):
                got, build_err = _run(directory, '%s_%s' % (slug, 'g' if general else 'd'),
                                      text, general)
                self.assertIsNotNone(got, '%s (general=%s)\n%s' % (slug, general, build_err))
                self.assertEqual(got, (want, want_rc), '%s (general=%s)\n%s' % (slug, general, build_err))

    def test_out_of_int64_bool_shifts_are_refused(self):
        for slug, text in OUT_OF_RANGE.items():
            self.refused(slug, text)

    def test_in_range_bool_shifts_match_cpython(self):
        self.matches('in_range', IN_RANGE)
        self.matches('in_range_argument', IN_RANGE_ARGUMENT)

    def test_bool_maxsplit_uses_the_same_folding(self):
        self.refused('maxsplit_out', MAXSPLIT_OUT_OF_RANGE, 'maxsplit constant does not fit')
        self.matches('maxsplit_in', MAXSPLIT_IN_RANGE)


if __name__ == '__main__':
    unittest.main()

"""Typed reach for the hot functions of eight real programs (lab/progfix/prog2.md).

The compiler gaps closed here are:

* return kinds are proved from the body, never trusted from an annotation: `line.isupper()` is a
  bool even when the annotation says `int`, and `" ".join(reversed(line.split()))` is a str.  The
  earlier annotation-filling shortcut boxed the first case as an int on the raw build path; pymix
  now infers the fixed result kind of the str methods and of `sys.stdin.read()`/`readline()`, so
  the hot `reverse_words` helper of lab/corpus/.../t079.py reaches the typed path without that
  unsafe guess;
* the CPython hybrid no longer sends away a division, floor division or modulo whose right operand
  is a literal nonzero constant: `t % 8` cannot raise, so `state_at` (the hot function of
  lab/census/dev/t408.py) is accelerated.  A variable divisor still stays in CPython;
* the hybrid also accepts a call it can prove pure and non-raising: a str method whose receiver and
  arguments are the right type, and `len`/`sorted`/`reversed` over a proved sequence.  That is what
  puts `reverse_words` (`" ".join(reversed(line.split()))`) on the accelerated path.

The other hot functions need features recorded in lab/progfix/prog2.md: nested `list[list[T]]` /
`list[tuple[...]]` parameters, a `dict` or tuple result, a scalar `int | None` local, and a set
comprehension of `str`.
"""
import json
import os
import shutil
import subprocess
import sys
import sysconfig
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent
PKG = ROOT / 'python' / 'pkg-v12'
CLI = ROOT / 'ail_chatgpt.py'
HAVE_CC = shutil.which(os.environ.get('PIPE_CC') or 'gcc') is not None
HAVE_HEADERS = (Path(sysconfig.get_paths().get('include', '/nonexistent')) / 'Python.h').is_file()

REVERSE = '''import sys


def reverse_words(line: str) -> str:
    """Reverse the order of the words on a line, separated by single spaces."""
    return " ".join(reversed(line.split()))


def main() -> None:
    for line in sys.stdin.read().splitlines():
        print(reverse_words(line))


if __name__ == "__main__":
    main()
'''

REVERSE_INPUTS = [
    'hotel 東京 zulu\n',
    '  a   b  \n\none\n',
    '',
    'single\n',
    'trailing spaces   \n   leading\n',
    '日本語 smile\nźródło über\n',
    '\r\nwindows\r\n',
]

ISUP = '''def isup(line: str) -> int:
    return line.isupper()


def main() -> None:
    print(isup("HI"))
    print(isup("hi"))
    print(isup(""))


if __name__ == "__main__":
    main()
'''

STATE = '''def state_at(t: int) -> str:
    phase = t % 8
    if phase < 4:
        return "GREEN"
    if phase < 5:
        return "YELLOW"
    return "RED"


def down(t: int) -> int:
    return t // -3


def remainder(a: int, b: int) -> int:
    return a % b


def main() -> None:
    handlers = (state_at, down)
    for t in range(112):
        print(f"{t}: {handlers[0](t)}")
    for t in (37, -37, 0):
        print("down", handlers[1](t))
    for a, b in ((7, 3), (-7, 3), (7, 0), (0, 5)):
        try:
            print("rem", remainder(a, b))
        except Exception as error:
            print("rem-exc", type(error).__name__, error)


if __name__ == "__main__":
    main()
'''


def run(cmd, cwd=None, stdin='', env=None):
    return subprocess.run(cmd, cwd=cwd, input=stdin.encode(), env=env,
                          capture_output=True, timeout=900)


def compile_program(directory, text, name, general=False):
    source = Path(directory) / (name + '.py')
    source.write_text(text, encoding='utf-8')
    env = dict(os.environ, AIL_NO_CACHE='1')
    for key in ('AIL_NO_GENERAL', 'AIL_UNIFIED_FORCE', 'AIL_QUIET_FALLBACK',
                'AIL_EXACT_INT', 'AIL_IR'):
        env.pop(key, None)
    if general:
        env['AIL_UNIFIED_FORCE'] = '1'
    built = subprocess.run([sys.executable, '-B', str(CLI), 'compile', source.name,
                            '--syntax', 'python', '-o', name + '_x'],
                           cwd=directory, env=env, capture_output=True, text=True, timeout=900)
    return source, built, Path(directory) / (name + '_x')


def build_hybrid(directory, text, name):
    source = Path(directory) / (name + '.py')
    source.write_text(text, encoding='utf-8')
    out = Path(directory) / ('hy_' + name)
    env = dict(os.environ, AIL_NO_CACHE='1')
    built = run([sys.executable, '-B', str(CLI), 'build', '--cpython',
                 str(source), '-o', str(out)], directory, env=env)
    return source, out, built


class KindProof(unittest.TestCase):
    def test_str_method_result_is_proved(self):
        source = '''def reverse_words(line: str) -> str:
    return " ".join(reversed(line.split()))


def main() -> None:
    print(reverse_words("a b"))
'''
        sys.path.insert(0, str(PKG))
        import pymix
        report = pymix.analyze(source)
        self.assertIn('reverse_words', report.candidates)
        self.assertEqual(report.candidates['reverse_words']['ret'], pymix.STR)

    def test_a_bool_is_not_boxed_as_an_annotated_int(self):
        source = '''def isup(line: str) -> int:
    return line.isupper()


def main() -> None:
    print(isup("HI"))
'''
        sys.path.insert(0, str(PKG))
        import pymix
        report = pymix.analyze(source)
        self.assertIn('isup', report.candidates)
        self.assertEqual(report.candidates['isup']['ret'], pymix.BOOL)
        self.assertTrue(report.candidates['isup']['is_bool_ret'])

    def test_annotation_alone_does_not_fill_a_return_kind(self):
        source = '''def f(x: int) -> int:
    return unknown_call(x)


def main() -> None:
    print(f(1))
'''
        sys.path.insert(0, str(PKG))
        import pymix
        report = pymix.analyze(source)
        self.assertNotIn('f', report.candidates)
        self.assertEqual(report.rejected['f'][0], 'unresolved-return')

    def test_contradicting_return_branches_stay_off_the_typed_path(self):
        source = '''
def f(line: str) -> int:
    if line == "x":
        return 1
    return "text"
'''
        sys.path.insert(0, str(PKG))
        import pymix
        report = pymix.analyze(source)
        self.assertNotIn('f', report.candidates)
        self.assertEqual(report.rejected.get('f', (None,))[0], 'unresolved-return')


@unittest.skipUnless(HAVE_CC, 'needs a C compiler')
class TypedPrograms(unittest.TestCase):
    def check_reverse(self, general):
        with tempfile.TemporaryDirectory(prefix='ail-prog2-') as tmp:
            source, built, exe = compile_program(tmp, REVERSE, 'reverse', general=general)
            self.assertEqual(built.returncode, 0, built.stderr[-2000:])
            if not general:
                self.assertNotIn('built on the general path', built.stderr,
                                 'reverse_words stayed off the typed path: ' + built.stderr[-800:])
            for text in REVERSE_INPUTS:
                want = run([sys.executable, str(source)], tmp, text)
                got = run([str(exe)], tmp, text)
                self.assertEqual(got.stdout, want.stdout, repr(text))
                self.assertEqual(got.returncode, want.returncode, repr(text))

    def test_reverse_words_typed(self):
        self.check_reverse(general=False)

    def test_reverse_words_general(self):
        self.check_reverse(general=True)

    def test_raw_build_of_an_int_annotation_returning_a_bool_matches_cpython(self):
        """The raw pyc.build path (no Python-surface translation) must not trust `-> int`."""
        with tempfile.TemporaryDirectory(prefix='ail-prog2-raw-') as tmp:
            source = Path(tmp) / 'isup.py'
            source.write_text(ISUP, encoding='utf-8')
            exe = Path(tmp) / 'isup_x'
            env = dict(os.environ, AIL_NO_CACHE='1', AIL_SURFACE='python',
                       AIL_GENERAL='v2', AIL_QUIET_FALLBACK='1')
            env.pop('AIL_NO_GENERAL', None)
            env.pop('AIL_UNIFIED_FORCE', None)
            built = subprocess.run([sys.executable, '-B', str(PKG / 'pyc.py'),
                                    '--strict', '--file', str(source), str(exe)],
                                   cwd=tmp, env=env, capture_output=True, text=True, timeout=900)
            self.assertEqual(built.returncode, 0, built.stderr[-2000:])
            want = run([sys.executable, str(source)], tmp)
            got = run([str(exe)], tmp)
            self.assertEqual(got.stdout, want.stdout)
            self.assertEqual(got.returncode, want.returncode)


@unittest.skipUnless(HAVE_CC and HAVE_HEADERS, 'needs a C compiler and the CPython headers')
class HybridHotFunction(unittest.TestCase):
    def test_modulo_by_a_constant_is_accelerated(self):
        with tempfile.TemporaryDirectory(prefix='ail-prog2-hybrid-') as tmp:
            source, out, built = build_hybrid(tmp, STATE, 'state')
            self.assertEqual(built.returncode, 0, built.stderr[-3000:])
            report = json.loads((out / 'build.json').read_text(encoding='utf-8'))
            self.assertIn('state_at', report['accelerated'])
            self.assertIn('down', report['accelerated'])
            self.assertNotIn('remainder', report['accelerated'])
            want = run([sys.executable, str(source)], tmp)
            got = run([str(out / 'state')], tmp)
            self.assertEqual(got.stdout, want.stdout)
            self.assertEqual(got.returncode, want.returncode)

    def test_proved_str_calls_make_reverse_words_accelerated(self):
        with tempfile.TemporaryDirectory(prefix='ail-prog2-hybrid-') as tmp:
            source, out, built = build_hybrid(tmp, REVERSE, 'reverse')
            self.assertEqual(built.returncode, 0, built.stderr[-3000:])
            report = json.loads((out / 'build.json').read_text(encoding='utf-8'))
            self.assertIn('reverse_words', report['accelerated'])
            for text in REVERSE_INPUTS:
                want = run([sys.executable, str(source)], tmp, text)
                got = run([str(out / 'reverse')], tmp, text)
                self.assertEqual(got.stdout, want.stdout, repr(text))
                self.assertEqual(got.returncode, want.returncode, repr(text))


if __name__ == '__main__':
    unittest.main()

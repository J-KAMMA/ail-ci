"""An out-of-int64 integer constant in a module, class or default position is refused by name.

AIL integers are fixed width.  ``X = 1 << 64``, a class attribute ``X = 1 << 64`` and a default
``def f(x=1 << 64)`` used to compile and then stop at run time with ``integer overflow`` while
CPython kept a bignum.  The front end now evaluates the outermost constant expression of each
module/class value and each function default and refuses an out-of-int64 result before emitting C,
on the general and the default build.  An expression whose intermediate leaves int64 but whose
result fits (``(1 << 63) - 1``, ``2 ** 65 - 2 ** 65``) and values that only reach an operation as
variables keep their previous behaviour.
"""
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent

OUT_OF_RANGE = {
    'module_shift': '''X = 1 << 64
print("ok")
''',
    'module_pow': '''X = 2 ** 63
print("ok")
''',
    'unreachable_module': '''if False:
    X = 1 << 64
print("ok")
''',
    'class_attribute': '''class C:
    X = 1 << 64
print("ok")
''',
    'default_shift': '''def f(x=1 << 64):
    return x
print("ok")
''',
    'unreachable_default': '''if False:
    def f(x=1 << 64):
        return x
print("ok")
''',
    'list_item': '''X = [1 << 64]
print("ok")
''',
    'dict_value': '''X = {"k": 1 << 64}
print("ok")
''',
    'default_tuple': '''def f(x=(1 << 64,)):
    return x
print("ok")
''',
    'negative': '''X = -(1 << 64)
print("ok")
''',
}

IN_RANGE = '''A = (1 << 63) - 1
B = 1 << 62
C = 0 << 64
D = 0 << 1000
E = 2 ** 63 - 1
F = 2 ** 65 - 2 ** 65
G = (1 << 64) - (1 << 64)
H = 2 ** 64 // 2 - 1
I = (1 << 64) >> 64
J = 1 << 64 >> 64


class Box:
    value = (1 << 63) - 1


def ident(x: int = (1 << 63) - 1) -> int:
    return x


print(A, B, C, D, E, F, G, H, I, J, Box.value, ident())
'''


FUNCTION_BODY_UNARY = {
    'dead_unary_shift_after_return': '''def f():
    return 1
    x = -(1 << 64)
print(f())
''',
    'unreached_unary_shift_return': '''def f(flag):
    if flag:
        return 1
    return -(1 << 64)
print(f(True))
''',
    'live_unary_shift': '''def f():
    return -(1 << 62)
print(f())
''',
}


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


class Pre191Tests(unittest.TestCase):
    def test_out_of_int64_constants_are_refused_by_name(self):
        with tempfile.TemporaryDirectory(prefix='ail-pre191-') as directory:
            for label, text in OUT_OF_RANGE.items():
                for general in (True, False):
                    with self.subTest(label + ('_g' if general else '_d')):
                        built, _ = _build(directory, '%s_%s' % (label, 'g' if general else 'd'),
                                          text, general)
                        self.assertNotEqual(built.returncode, 0, label)
                        message = built.stdout + built.stderr
                        # The integration tree's general constant-expression rule may refuse a
                        # list/dict element or a default tuple before this pass sees it, with its
                        # own named message; accept that as well as this pass's wording.
                        named = ('int64 constant expression out of range',
                                 'outside the signed 64-bit range')
                        self.assertTrue(any(item in message for item in named), label)
                        self.assertNotIn('integer overflow', message, label)
                        self.assertNotIn('Traceback', message, label)

    def test_function_body_unary_shifts_still_match_cpython(self):
        # The integration tree's general constant-expression rule now refuses an out-of-int64
        # constant anywhere in a function body, even unreached (``not in the subset: ... outside
        # the signed 64-bit range``); the base tree still prints CPython's value for these dead
        # cases.  This pass must not be the one refusing them, so accept either a CPython match or
        # that other named refusal, and reject this pass's own message in a function body.
        with tempfile.TemporaryDirectory(prefix='ail-pre191-') as directory:
            for label, text in FUNCTION_BODY_UNARY.items():
                want, want_rc, err = _cpython(directory, label, text)
                self.assertEqual(want_rc, 0, err)
                for general in (True, False):
                    with self.subTest(label + ('_g' if general else '_d')):
                        got, build_err = _run(directory, '%s_%s' % (label, 'g' if general else 'd'),
                                              text, general)
                        if got is None:
                            self.assertIn('outside the signed 64-bit range', build_err, label)
                            self.assertNotIn('int64 constant expression out of range', build_err,
                                             label)
                            self.assertNotIn('integer overflow', build_err, label)
                            self.assertNotIn('Traceback', build_err, label)
                        else:
                            self.assertEqual(got, (want, want_rc), build_err)

    def test_in_range_constant_positions_still_match_cpython(self):
        with tempfile.TemporaryDirectory(prefix='ail-pre191-') as directory:
            want, want_rc, err = _cpython(directory, 'in_range', IN_RANGE)
            self.assertEqual(want_rc, 0, err)
            for general in (True, False):
                with self.subTest('in_range_' + ('g' if general else 'd')):
                    got, build_err = _run(directory, 'in_range_' + ('g' if general else 'd'),
                                          IN_RANGE, general)
                    self.assertIsNotNone(got, build_err)
                    self.assertEqual(got, (want, want_rc), build_err)


if __name__ == '__main__':
    unittest.main()

"""Pre-251: a bool constant in a constant integer expression is folded as CPython's int.

The review of job pre201 recorded that ``(True << 64) >> 64`` and
``(True << 100000) >> 100000`` still stopped with ``integer overflow`` on both builds
although the final value (1) fits int64.  The constant int folder did not accept a bool
constant even though CPython treats True as 1.  Bool constants now take part in constant
integer arithmetic, while an expression whose CPython result is a bool (``True & True``) is
still left to the run time, and an out-of-int64 bool expression (``True << 64``) is refused
by name like the same int expression.
"""
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent

ACCEPTED = r'''def main():
    print((True << 64) >> 64)
    print((True << 100000) >> 100000)
    print((True << 63) >> 63)
    print((True << 62) >> 62)
    print((False << 64) >> 64)
    print((False << 100000) >> 100000)
    print((-True << 64) >> 64)
    print((~True << 64) >> 64)
    print(((True + True) << 64) >> 64)
    print((True * 3 << 64) >> 64)
    print(((True & True) << 64) >> 64)
    print(((True | False) << 64) >> 64)


main()
'''

CONTEXTS = r'''class Box:
    v = (True << 64) >> 64

    def __init__(self):
        self.w = (True << 64) >> 64


def identity(v):
    return v


def show(v):
    print(v)


def main():
    value = (True << 64) >> 64
    print(value)
    print(identity(value))
    show((True << 64) >> 64)
    xs = [(True << 64) >> 64, (False << 64) >> 64]
    print(xs[0], xs[1])
    d = {"k": (True << 64) >> 64, "f": (False << 64) >> 64}
    print(d["k"], d["f"])
    print(Box.v)
    box = Box()
    print(box.w)
    ts = ((True << 64) >> 64,)
    print(ts[0])


main()
'''

BOOL_RESULTS = r'''def main():
    print(True & True)
    print(True & False)
    print(True | False)
    print(True ^ True)
    print(False | False)
    print(True + True)
    print(True - False)
    print(True * 3)
    print(~True)
    print(-True)
    print(+True)
    print(True << 2)
    print(True & 3)
    print(3 & True)
    print(True | 3)
    print(True ^ 1)
    print((True & True) == True)
    print(type(True & True).__name__)


main()
'''

MODULE_CONSTANTS = r'''M = (True << 64) >> 64
F = (False << 64) >> 64
N = (True << 100000) >> 100000


def main():
    print(M, F, N)


main()
'''

MAXSPLIT = r'''def main():
    s = "a b c d"
    print(s.split(" ", (True << 64) >> 64))
    print(s.split(" ", (False << 64) >> 64))
    print(s.split(" ", (-True << 64) >> 64))
    print(s.rsplit(" ", (True << 100000) >> 100000))
    print(s.split(" ", True))
    print(s.split(" ", False))


main()
'''

REFUSED = {
    'shift': '''def main():
    print(True << 64)


main()
''',
    'wide_shift': '''def main():
    print(True << 1000000)


main()
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


class Pre251Tests(unittest.TestCase):
    def refused(self, slug, text):
        with tempfile.TemporaryDirectory(prefix='ail-pre251-') as directory:
            for general in (True, False):
                name = '%s_%s' % (slug, 'g' if general else 'd')
                built, exe = _build(directory, name, text, general)
                output = built.stdout + built.stderr
                self.assertNotEqual(built.returncode, 0,
                                    '%s (general=%s) built\n%s' % (slug, general, output[-3000:]))
                self.assertFalse(exe.exists(), '%s (general=%s) built an executable' % (slug, general))
                self.assertIn('outside the signed 64-bit range', output,
                              '%s (general=%s)\n%s' % (slug, general, output[-3000:]))

    def matches(self, slug, text):
        with tempfile.TemporaryDirectory(prefix='ail-pre251-') as directory:
            want, want_rc, err = _cpython(directory, slug, text)
            self.assertEqual(want_rc, 0, err)
            for general in (True, False):
                got, build_err = _run(directory, '%s_%s' % (slug, 'g' if general else 'd'),
                                      text, general)
                self.assertIsNotNone(got, '%s (general=%s)\n%s' % (slug, general, build_err))
                self.assertEqual(got, (want, want_rc), '%s (general=%s)\n%s' % (slug, general, build_err))

    def test_bool_constant_shifts_match_cpython(self):
        self.matches('accepted', ACCEPTED)

    def test_bool_constant_shifts_in_other_positions(self):
        self.matches('contexts', CONTEXTS)

    def test_bool_only_results_keep_their_type(self):
        self.matches('bool_results', BOOL_RESULTS)

    def test_bool_module_constants(self):
        self.matches('module_constants', MODULE_CONSTANTS)

    def test_bool_maxsplit_constants(self):
        self.matches('maxsplit', MAXSPLIT)

    def test_out_of_range_bool_expression_is_refused(self):
        for slug, text in REFUSED.items():
            self.refused(slug, text)


if __name__ == '__main__':
    unittest.main()

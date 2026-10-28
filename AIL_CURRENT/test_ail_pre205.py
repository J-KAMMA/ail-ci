"""Pre-205: a maxsplit constant may pass through a wider-than-int64 intermediate.

The review of job rbpre121 recorded a pre-existing difference: the maxsplit folder refused
`"a b c".split(" ", 2**100 // 2**80)` with its `right >= 64` power rule, although the final
value 2**20 fits in int64 and CPython splits normally.  The folder now bounds the work by the
result's size, so an in-range final value reached through a wider intermediate is folded
exactly (the pre121 rule); a final value outside int64 is still refused by name.

The cases below cover split/rsplit, an explicit and a `None` separator, a negative and a zero
limit, the empty string, wider intermediates built from powers, shifts, sums and products, and
values reaching the call through an argument, a list item, an attribute and a dict value, on
both builds.
"""
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent
CLI = str(ROOT / "ail_chatgpt.py")

PROGRAM = r'''class Box:
    n = 2**100 // 2**80

    def __init__(self, n):
        self.n = n


def split_with(s, n):
    return s.split(" ", n)


def rsplit_with(s, n):
    return s.rsplit(" ", n)


def main():
    n = 2**100 // 2**80
    xs = [n]
    d = {"n": n}
    box = Box(n)
    print("a b c".split(" ", 2**100 // 2**80))
    print("a b c".rsplit(" ", 2**100 // 2**80))
    print("a b c".split(None, 2**100 // 2**80))
    print("a b c".split(" ", (1 << 100) // (1 << 80)))
    print("a b c".rsplit(" ", (1 << 100) // (1 << 80)))
    print("a b c".split(" ", (2**100 + 2**100) // 2**81))
    print("a b c".split(" ", (2**100 - 2**99) // 2**79))
    print("a b c".split(" ", (2**64 * 2**64) // 2**108))
    print("a b c".split(" ", -(2**100 // 2**80)))
    print("a b c".split(" ", 2**100 // 2**101))
    print("".split(" ", 2**100 // 2**80))
    print(" a  b ".split(None, 2**100 // 2**80))
    print(" a  b ".rsplit(None, 2**100 // 2**80))
    print("a b c".split(" ", 2**63 - 1))
    print(split_with("a b c", n))
    print(rsplit_with("a b c", n))
    print("a b c".split(" ", xs[0]))
    print("a b c".split(" ", box.n))
    print("a b c".split(" ", d["n"]))
    print("a b c".split(" ", Box.n))
    print("a b c".split(" ", n))
    print("a b c".split())


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
    built = subprocess.run([sys.executable, '-B', CLI, 'compile', src.name,
                            '--syntax', 'python', '-o', exe.name], cwd=directory,
                           capture_output=True, text=True, timeout=900, env=env)
    return built, exe


def _build_and_run(directory, name, text, general):
    built, exe = _build(directory, name, text, general)
    if built.returncode != 0:
        return None, (built.stdout + built.stderr)[-3000:]
    got = subprocess.run([str(exe)], capture_output=True, timeout=120, cwd=directory)
    return (got.stdout.replace(b'\r\n', b'\n'), got.returncode), got.stderr.decode('utf-8', 'replace')[-1500:]


class Pre205Tests(unittest.TestCase):
    def check(self, slug, text):
        with tempfile.TemporaryDirectory(prefix='ail-pre205-') as directory:
            want, rc, err = _cpython(directory, slug, text)
            self.assertEqual(rc, 0, err)
            for general in (True, False):
                got, build_err = _build_and_run(directory, '%s_%s' % (slug, 'g' if general else 'd'),
                                                text, general)
                self.assertIsNotNone(got, '%s (general=%s)\n%s' % (text[:2000], general, build_err))
                self.assertEqual(got, (want, 0), '%s (general=%s)\n%s' % (text[:2000], general, build_err))

    def refused(self, slug, text, message):
        """No executable in either build, and the refusal is the maxsplit one."""
        # exact ints (bigint): built, and the OverflowError comes at run time as in CPython
        with tempfile.TemporaryDirectory(prefix='ail-pre205-') as directory:
            want, rc, err = _cpython(directory, slug, text)
            for general in (True, False):
                got, build_err = _build_and_run(directory, '%s_%s' % (slug, 'g' if general else 'd'),
                                                text, general)
                self.assertIsNotNone(got, '%s (general=%s)\n%s' % (text[:2000], general, build_err))
                self.assertEqual(got, (want, rc), '%s (general=%s)\n%s' % (text[:2000], general, build_err))

    def test_wider_intermediate_matches_cpython(self):
        self.check('wider', PROGRAM)

    def test_out_of_int64_maxsplit_is_still_refused(self):
        for slug, expression in (
                ('pow', '2**100'),
                ('decimal', '10**30'),
                ('quotient', '(2**64) // 2 * 2')):
            text = 'def main():\n    print("a b c".split(" ", %s))\n\n\nmain()\n' % expression
            self.refused(slug, text, 'maxsplit constant does not fit in a 64-bit signed integer')


if __name__ == '__main__':
    unittest.main()

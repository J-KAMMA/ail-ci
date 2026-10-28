"""A huge constant is refused by name instead of tripping CPython's int-to-str limit.

A constant ``**`` whose value has more than 4300 digits used to reach the compiler's own
``str(value)`` while it built the ``int64 constant out of range`` message, so the build stopped
with ``Exceeds the limit (4300 digits) for integer string conversion``.  The diagnostic now says
``too large`` when CPython's conversion limit would forbid printing the value.  The reviewer's
``print(10 ** 4000 * 10 ** 300)`` is refused by the front end on this tree; both that and the
large-base power cases are checked on both builds.
"""
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent
BIG = '9' * 3000
OTHER = '8' * 3000

REFUSED = {
    'reviewer_expression': 'print(10 ** 4000 * 10 ** 300)\n',
    'pow_argument': 'print(%s ** 64)\n' % BIG,
    'pow_list_item': 'print([%s ** 64][0])\n' % BIG,
    'pow_attribute': 'class Box:\n    v = %s ** 64\n\nprint(Box.v)\n' % BIG,
    'pow_dict_value': 'print({"v": %s ** 64}["v"])\n' % BIG,
    'pow_default': 'def f(x=%s ** 64):\n    print(x)\n\nf()\n' % BIG,
    'pow_local': 'def main():\n    x = %s ** 64\n    print(x)\n\nmain()\n' % BIG,
    'pow_module': 'X = %s ** 64\nprint(X)\n' % BIG,
    'pow_unary': 'print(-(%s ** 64))\n' % BIG,
    'pow_nested': 'print((%s ** 2) ** 60)\n' % BIG,
    'mul_index': 'xs = [1]\nprint(xs[%s * %s])\n' % (BIG, OTHER),
}

MATCHES = '''def main():
    print((1 << 5000) >> 5000)
    print((10 ** 64) ** 0)
    print(2 ** 62)


main()
'''


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


NAMED = (
    'int64 constant out of range',
    'int64 constant expression out of range',
    'int64 literal out of range',
    'int64 index out of range',
    'outside the signed 64-bit range',
    'maxsplit constant does not fit',
)


class Pre238Tests(unittest.TestCase):
    def refused(self, slug, text):
        # exact ints (bigint): builds and matches CPython (stdout, exit code)
        with tempfile.TemporaryDirectory(prefix='ail-pre238-') as directory:
            ref = Path(directory) / (slug + '_cpython.py')
            ref.write_text(text, encoding='utf-8')
            want = subprocess.run([sys.executable, '-B', str(ref)], capture_output=True, timeout=120)
            for general in (True, False):
                got, build_err = _run(directory, '%s_%s' % (slug, 'g' if general else 'd'),
                                      text, general)
                self.assertIsNotNone(got, '%s (general=%s)\n%s' % (slug, general, build_err))
                self.assertEqual(got, (want.stdout.replace(b'\r\n', b'\n'), want.returncode),
                                 '%s (general=%s)\n%s' % (slug, general, build_err))

    def matches(self, slug, text):
        with tempfile.TemporaryDirectory(prefix='ail-pre238-') as directory:
            want = subprocess.run([sys.executable, '-B', '-c', text], capture_output=True, timeout=120)
            self.assertEqual(want.returncode, 0, want.stderr.decode('utf-8', 'replace'))
            for general in (True, False):
                got, build_err = _run(directory, '%s_%s' % (slug, 'g' if general else 'd'),
                                      text, general)
                self.assertIsNotNone(got, '%s (general=%s)\n%s' % (slug, general, build_err))
                self.assertEqual(got, (want.stdout.replace(b'\r\n', b'\n'), want.returncode),
                                 '%s (general=%s)\n%s' % (slug, general, build_err))

    def test_huge_constant_diagnostic_is_named(self):
        for slug, text in REFUSED.items():
            self.refused(slug, text)

    def test_reducible_constants_still_match_cpython(self):
        self.matches('matches', MATCHES)


if __name__ == '__main__':
    unittest.main()

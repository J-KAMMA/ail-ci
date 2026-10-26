"""Pre-177: a constant index that int64 cannot hold is refused by name.

CPython's ints are unbounded: `xs[10**20]` reaches the list and raises
`IndexError: cannot fit 'int' into an index-sized integer`.  AIL computes
`10**20` in int64 and used to stop with `integer overflow` (exit 1) before the
subscript, a pre-existing difference.  The compiler now refuses a constant
subscript index whose exact value leaves int64, and a constant `**` outside
int64 wherever it appears (an argument, a list item, an attribute and a dict
value), with `int64 index out of range` / `int64 constant out of range` and
exit 2.  An intermediate step may leave int64 when the final index fits
(pre269), and in-range constant index expressions match CPython on both
builds.
"""
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent

BOUNDARY = r'''def main():
    xs = [10, 20, 30]
    print(xs[2 ** 1], xs[1 << 1], xs[(2 ** 2) - 2], xs[-2 ** 1])
    print("abc"[2 ** 1], b"abc"[1 << 1], (1, 2, 3)[2 ** 1])
    print(xs[~-3], xs[(2 ** 62) // (2 ** 61)], xs[2 ** 62 - 2 ** 62])
    print(xs[2 ** 0], xs[-1], xs[-3])


main()
'''

FLOW_ARGUMENT = r'''def at(xs, i):
    return xs[i]


def main():
    print(at([10, 20, 30], 10 ** 20))


main()
'''

FLOW_LIST_ITEM = r'''def main():
    i = [10 ** 20][0]
    print([10, 20, 30][i])


main()
'''

FLOW_ATTRIBUTE = r'''class Box:
    i = 10 ** 20


def main():
    print([10, 20, 30][Box.i])


main()
'''

FLOW_DICT_VALUE = r'''def main():
    d = {"i": 10 ** 20}
    print([10, 20, 30][d["i"]])


main()
'''

HUGE_INDEXES = {
    'pow': ('xs[10 ** 20]', '100000000000000000000'),
    'negative_pow': ('xs[-(10 ** 20)]', '100000000000000000000'),
    'pow_63': ('xs[2 ** 63]', '9223372036854775808'),
    'shift_63': ('xs[1 << 63]', '9223372036854775808'),
    'str': ('"abc"[10 ** 20]', '100000000000000000000'),
    'bytes': ('b"abc"[10 ** 20]', '100000000000000000000'),
    'tuple': ('(1, 2, 3)[10 ** 20]', '100000000000000000000'),
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


def _build_and_run(directory, name, text, general):
    built, exe = _build(directory, name, text, general)
    if built.returncode != 0:
        return None, (built.stdout + built.stderr)[-3000:]
    got = subprocess.run([str(exe)], capture_output=True, timeout=120, cwd=directory)
    return (got.stdout.replace(b'\r\n', b'\n'), got.returncode), got.stderr.decode('utf-8', 'replace')[-1500:]


class Pre177Tests(unittest.TestCase):
    def check(self, slug, text, rc=0):
        with tempfile.TemporaryDirectory(prefix='ail-pre177-') as directory:
            want, got_rc, err = _cpython(directory, slug, text)
            self.assertEqual(got_rc, rc, err)
            for general in (True, False):
                got, build_err = _build_and_run(directory, '%s_%s' % (slug, 'g' if general else 'd'), text, general)
                self.assertIsNotNone(got, '%s (general=%s)\n%s' % (text[:2000], general, build_err))
                self.assertEqual(got, (want, rc), '%s (general=%s)\n%s' % (text[:2000], general, build_err))

    def refused(self, slug, text, message, value):
        """No executable in either build, exit 2, and the refusal names the value."""
        with tempfile.TemporaryDirectory(prefix='ail-pre177-') as directory:
            for general in (True, False):
                name = '%s_%s' % (slug, 'g' if general else 'd')
                built, exe = _build(directory, name, text, general)
                output = built.stdout + built.stderr
                self.assertEqual(built.returncode, 2, '%s (general=%s)\n%s' % (text[:2000], general, output[-3000:]))
                self.assertFalse(exe.exists(), '%s (general=%s) built an executable' % (slug, general))
                self.assertIn(message, output, '%s (general=%s)\n%s' % (slug, general, output[-3000:]))
                self.assertIn(value, output, '%s (general=%s)\n%s' % (slug, general, output[-3000:]))

    def test_huge_constant_index_is_refused(self):
        for slug, (expression, value) in HUGE_INDEXES.items():
            text = 'def main():\n    xs = [10, 20, 30]\n    print(%s)\n\n\nmain()\n' % expression
            self.refused('index_' + slug, text, 'int64 index out of range', value)

    def test_huge_constant_power_through_values_is_refused(self):
        for slug, text in (('argument', FLOW_ARGUMENT), ('list_item', FLOW_LIST_ITEM),
                           ('attribute', FLOW_ATTRIBUTE), ('dict_value', FLOW_DICT_VALUE)):
            self.refused('flow_' + slug, text, 'int64 constant out of range', '100000000000000000000')

    def test_huge_literal_index_keeps_the_literal_message(self):
        text = 'def main():\n    xs = [10, 20, 30]\n    print(xs[100000000000000000000])\n\n\nmain()\n'
        self.refused('literal_index', text, 'int64 literal out of range', '100000000000000000000')

    def test_in_range_constant_index_expressions_match_cpython(self):
        self.check('boundary', BOUNDARY)


if __name__ == '__main__':
    unittest.main()

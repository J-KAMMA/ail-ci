"""Pre-285: a local constant expression that cancels an out-of-int64 step is refused by name.

The reviewer of job rbrbpre32 recorded ``a = 2**62; b = a * 2 - 1`` as a pre-existing
difference: both builds computed ``a * 2`` in int64 and stopped with ``integer overflow`` at
run time, where CPython's unbounded int prints INT64_MAX.  A function's single-assignment int
constants (direct, aliased, annotated, or a module constant) are followed here; a step that
leaves int64 while the whole expression fits is refused at compile time with the existing
``int64 constant expression out of range`` wording on both builds.  In-range constants, plain
literal cancellation and expressions whose value only reaches them at run time are unchanged.
"""
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def _main(lines):
    return 'def main():\n%s\n\n\nmain()\n' % lines


REFUSED = {
    'reviewer_case': _main('    a = 2**62\n    b = a * 2 - 1\n    print(b)'),
    'returned': '''def f():
    a = 2**62
    return a * 2 - 1


print(f())
''',
    'alias': _main('    a = 2**62\n    b = a\n    print(b * 2 - 1)'),
    'annassign': _main('    a: int = 2**62\n    print(a * 2 - 1)'),
    'module_constant': '''N = 2**62


def main():
    print(N * 2 - 1)


main()
''',
    'sum': _main('    a = 2**62\n    print(a + a - 1)'),
    'divide': _main('    a = 2**62\n    print(a * 2 // 2)'),
    'shift': _main('    a = 2**62\n    print((a * 2) >> 1)'),
    'argument': '''def show(v):
    print(v)


def main():
    a = 2**62
    show(a * 2 - 1)


main()
''',
    'list_item': _main('    a = 2**62\n    print([a * 2 - 1][0])'),
    'attribute': '''class Box:
    pass


def main():
    a = 2**62
    box = Box()
    box.v = a * 2 - 1
    print(box.v)


main()
''',
    'dict_value': _main('    a = 2**62\n    print({"v": a * 2 - 1}["v"])'),
}

MATCHING = {
    'small_local': _main('    a = 5\n    print(a * 2 - 1, (a + a) * 3, a ** 3)'),
    'in_range_steps': _main('    a = 2**62\n    print(a, a + 1, a - 1)'),
    'literal_cancellation': _main('    print(2**63 - 1, 2**63 - 2**63, (2**64) // (2**64))'),
    'overwritten': _main('    a = 2**62\n    a = 5\n    print(a * 2 - 1)'),
    'unused_big': _main('    a = 2**62\n    print(7)'),
    'runtime_value': '''def f(a):
    return a * 2 - 1


print(f(5))
''',
}


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


def _cpython(directory, name, text):
    src = Path(directory) / (name + '_cpython.py')
    src.write_text(text, encoding='utf-8')
    done = subprocess.run([sys.executable, '-B', str(src)], capture_output=True, timeout=120,
                          env=dict(os.environ, PYTHONUTF8='1'))
    return done.stdout.replace(b'\r\n', b'\n'), done.returncode


class Pre285Tests(unittest.TestCase):
    def refused(self, slug, text):
        with tempfile.TemporaryDirectory(prefix='ail-pre285-') as directory:
            for general in (True, False):
                name = '%s_%s' % (slug, 'g' if general else 'd')
                built, exe = _build(directory, name, text, general)
                output = built.stdout + built.stderr
                self.assertEqual(built.returncode, 2, '%s (general=%s)\n%s' % (slug, general, output[-3000:]))
                self.assertFalse(exe.exists(), '%s (general=%s) built an executable' % (slug, general))
                self.assertIn('int64 constant expression out of range', output,
                              '%s (general=%s)\n%s' % (slug, general, output[-3000:]))

    def matches(self, slug, text):
        with tempfile.TemporaryDirectory(prefix='ail-pre285-') as directory:
            expected, expected_rc = _cpython(directory, slug, text)
            self.assertEqual(expected_rc, 0)
            for general in (True, False):
                name = '%s_%s' % (slug, 'g' if general else 'd')
                built, exe = _build(directory, name, text, general)
                output = built.stdout + built.stderr
                self.assertEqual(built.returncode, 0, '%s (general=%s)\n%s' % (slug, general, output[-3000:]))
                ran = subprocess.run([str(exe)], capture_output=True, timeout=120, cwd=directory)
                self.assertEqual((ran.returncode, ran.stdout.replace(b'\r\n', b'\n')),
                                 (expected_rc, expected), '%s (general=%s)\n%s'
                                 % (slug, general, ran.stderr.decode('utf-8', 'replace')[-1500:]))

    def test_local_cancellation_is_refused_by_name(self):
        for slug, text in REFUSED.items():
            with self.subTest(case=slug):
                self.matches(slug, text)      # exact ints (bigint): built, and CPython's answer

    def test_in_range_and_runtime_cases_match_cpython(self):
        for slug, text in MATCHING.items():
            with self.subTest(case=slug):
                self.matches(slug, text)


if __name__ == '__main__':
    unittest.main()

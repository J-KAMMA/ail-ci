"""pre297: one-argument round() of a constant float at the int64 boundary is refused.

CPython's round(float) is an unbounded int.  AIL integers are int64, so ``round(2.0 ** 63)``
used to compile and then stop with ``integer overflow`` where CPython prints
9223372036854775808.  A statically known float argument is rounded exactly at compile time and
an out-of-int64 result is refused by name on both builds, directly and through a module or local
constant.  The same folding reaches ``abs(round(-(2.0 ** 63)))``, whose result is INT64_MIN's
absolute value.  In-range constants, two-argument round(), run-time variables and a program that
binds its own ``round`` keep their previous behaviour.
"""
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent
CLI = str(ROOT / 'ail_chatgpt.py')

OUT_OF_RANGE = {
    'direct': '''def main():
    print(round(2.0 ** 63))


main()
''',
    'module_constant': '''LIMIT = 2.0 ** 63


def main():
    print(round(LIMIT))


main()
''',
    'local_constant': '''def main():
    v = 2.0 ** 63
    print(round(v))


main()
''',
    'computed_local': '''def main():
    v = 2.0 ** 63
    print(round(v - 0.0))


main()
''',
    'abs_of_min': '''def main():
    print(abs(round(-(2.0 ** 63))))


main()
''',
    'argument': '''def show(x):
    print(x)


def main():
    show(round(2.0 ** 63))


main()
''',
    'list_item': '''def main():
    print([round(2.0 ** 63)][0])


main()
''',
    'attribute': '''class Box:
    pass


def main():
    box = Box()
    box.value = round(2.0 ** 63)
    print(box.value)


main()
''',
    'dict_value': '''def main():
    print({'v': round(2.0 ** 63)}['v'])


main()
''',
}

MATCHING = {
    'in_range': '''def main():
    print(round(2.675))
    print(round(0.5), round(-0.5), round(2.5), round(3.5))
    print(round(-(2.0 ** 63)))
    print(round(2.0 ** 62), round(-(2.0 ** 62)))
    print(round(1.0), round(-1.0), round(0.0), round(-0.0))


main()
''',
    'two_arguments': '''def main():
    print(repr(round(2.0 ** 63, 2)))
    print(repr(round(2.675, 2)))


main()
''',
    'runtime_variable': '''def probe(v):
    return round(v)


def main():
    print(probe(2.5), probe(-2.5))
    v = 2.5
    print(round(v))


main()
''',
    'overwritten_local': '''def main():
    v = 2.0 ** 63
    v = 5.5
    print(round(v))


main()
''',
    'shadowed_module': '''LIMIT = 2.0 ** 63


def main():
    LIMIT = 5.5
    print(round(LIMIT))


main()
''',
    'bound_round': '''def round(x):
    return x


def main():
    print(round(2.0 ** 63))


main()
''',
}


def _cpython(directory, name, text):
    src = Path(directory) / (name + '_cpython.py')
    src.write_text(text, encoding='utf-8')
    return subprocess.run([sys.executable, '-B', str(src)], capture_output=True, text=True,
                          timeout=120, env=dict(os.environ, PYTHONUTF8='1'))


def _build(directory, name, text, general):
    src = Path(directory) / (name + '.py')
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


class Pre297Tests(unittest.TestCase):
    def test_constant_round_outside_int64_is_refused_by_name(self):
        for label, text in OUT_OF_RANGE.items():
            with tempfile.TemporaryDirectory(prefix='ail-pre297-') as directory:
                for general in (False, True):
                    with self.subTest(label=label, general=general):
                        built, exe = _build(directory, '%s_%s' % (label, 'g' if general else 'd'),
                                            text, general)
                        output = built.stdout + built.stderr
                        self.assertEqual(built.returncode, 2, output[-3000:])
                        self.assertFalse(exe.exists(), output[-3000:])
                        self.assertIn('int64 constant expression out of range', output,
                                      output[-3000:])
                        self.assertIn('9223372036854775808', output, output[-3000:])
                        self.assertNotIn('integer overflow', output, output[-3000:])
                        self.assertNotIn('Traceback', output, output[-3000:])

    def test_in_range_and_dynamic_round_matches_cpython(self):
        for label, text in MATCHING.items():
            with tempfile.TemporaryDirectory(prefix='ail-pre297-') as directory:
                want = _cpython(directory, label, text)
                self.assertEqual(want.returncode, 0, want.stderr)
                for general in (False, True):
                    with self.subTest(label=label, general=general):
                        built, exe = _build(directory, '%s_%s' % (label, 'g' if general else 'd'),
                                            text, general)
                        output = built.stdout + built.stderr
                        self.assertEqual(built.returncode, 0, output[-3000:])
                        got = subprocess.run([str(exe)], capture_output=True, text=True,
                                             timeout=120, cwd=directory)
                        self.assertEqual((got.returncode, got.stdout),
                                         (want.returncode, want.stdout), output[-3000:])


if __name__ == '__main__':
    unittest.main()

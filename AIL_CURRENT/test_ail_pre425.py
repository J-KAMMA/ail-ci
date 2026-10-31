"""pre425: an augmented power whose operands arrive through a call or container.

The rbpre385 review recorded as pre-existing that a routed ``b **= e`` still compiled and
then stopped with ``integer overflow`` where CPython prints the bignum: the augmented-power
check folded only parameterless straight-line statements, so a parameter bound by a module
call, or a list/dict/attribute route holding a wide constant expression, was not seen.  The
call graph is now followed from module-scope calls for augmented powers too, and the
straight-line folder can read a list item, a dict value or an attribute the body assigned.
The check path names the out-of-range result at compile time; a build falls back to the
general path, which computes the exact big integer, so both builds match CPython.  In-range,
dynamic, rebound and mutated values keep matching CPython.
"""
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent

REFUSED = (
    ('direct', 'def power(b, e):\n    b **= e\n    return b\n\n\n'
               'print(power(2, (3**100)>>150))\n'),
    ('nested_call', 'def power(b, e):\n    b **= e\n    return b\n\n\n'
                    'def apply(a, b):\n    return power(a, b)\n\n\n'
                    'print(apply(2, (3**100)>>150))\n'),
    ('keyword', 'def power(b, e):\n    b **= e\n    return b\n\n\n'
                'print(power(e=(3**100)>>150, b=2))\n'),
    ('list_argument', 'def power(b, e):\n    b **= e\n    return b\n\n\n'
                      'values = [2, (3**100)>>150]\n'
                      'print(power(values[0], values[1]))\n'),
    ('dict_argument', 'def power(b, e):\n    b **= e\n    return b\n\n\n'
                      'values = {"b": 2, "e": (3**100)>>150}\n'
                      'print(power(values["b"], values["e"]))\n'),
    ('module_list', 'values = [2, (3**100)>>150]\n'
                    'b = values[0]\ne = values[1]\nb **= e\nprint(b)\n'),
    ('module_dict', 'values = {"b": 2, "e": (3**100)>>150}\n'
                    'b = values["b"]\ne = values["e"]\nb **= e\nprint(b)\n'),
    ('module_attribute', 'class Box:\n    pass\n\n\nbox = Box()\n'
                         'box.b = 2\nbox.e = (3**100)>>150\n'
                         'b = box.b\ne = box.e\nb **= e\nprint(b)\n'),
    ('function_local_list', 'def power():\n    values = [2, (3**100)>>150]\n'
                            '    b = values[0]\n    e = values[1]\n    b **= e\n'
                            '    print(b)\n\n\npower()\n'),
)

SAFE = r'''def power(b, e):
    b **= e
    return b


def wrapper(a, b):
    return power(a, b)


def float_power(b, e):
    b **= e
    return b


def bool_power(b, e):
    b **= e
    return b


def store_before(b, e):
    b = 1
    b **= e
    return b


def dynamic(b, e):
    b **= e
    return b


class Box:
    pass


def main():
    print(power(2, 10), power(2, 62), power(-2, 63), power(3, 39))
    print(power(0, 100), power(1, 100000), power(-1, 100001))
    print(power(2, -3))
    print(float_power(2.0, 100), bool_power(True, 100))
    print(wrapper(2, 10), store_before(2, 100))
    b = 2
    e = 10
    print(dynamic(b, e))
    values = [2, (3**100)>>150]
    values[1] = 10
    print(power(values[0], values[1]))
    mapping = {"b": 2, "e": 10}
    print(power(mapping["b"], mapping["e"]))
    box = Box()
    box.b = 2
    box.e = 10
    print(power(box.b, box.e))


main()
'''


def build_run(directory, text, name, general):
    src = Path(directory) / ('%s.py' % name)
    exe = Path(directory) / ('%s_%s' % (name, 'g' if general else 'd'))
    src.write_text(text, encoding='utf-8')
    env = dict(os.environ, AIL_NO_CACHE='1', AIL_QUIET_FALLBACK='1')
    env.pop('AIL_NO_GENERAL', None)
    env.pop('AIL_UNIFIED_FORCE', None)
    env.pop('AIL_GENERAL', None)
    if general:
        env['AIL_UNIFIED_FORCE'] = '1'
    built = subprocess.run([sys.executable, '-B', str(ROOT / 'ail_chatgpt.py'), 'compile', src.name,
                            '--syntax', 'python', '-o', exe.name], cwd=directory,
                           capture_output=True, text=True, timeout=900, env=env)
    if built.returncode:
        return built.returncode, b'', built.stdout + built.stderr
    ran = subprocess.run([str(exe)], cwd=directory, capture_output=True, timeout=120)
    return ran.returncode, ran.stdout.replace(b'\r\n', b'\n'), built.stdout + built.stderr


def run_cpython(directory, text, name):
    src = Path(directory) / ('%s_cpython.py' % name)
    src.write_text(text, encoding='utf-8')
    return subprocess.run([sys.executable, '-B', src.name], cwd=directory,
                          capture_output=True, timeout=120, env=dict(os.environ, PYTHONUTF8='1'))


def check_run(directory, text, name):
    src = Path(directory) / ('%s_check.py' % name)
    src.write_text(text, encoding='utf-8')
    env = dict(os.environ, AIL_NO_CACHE='1', AIL_QUIET_FALLBACK='1')
    return subprocess.run([sys.executable, '-B', str(ROOT / 'ail_chatgpt.py'), 'check', src.name,
                           '--syntax', 'python'], cwd=directory, capture_output=True, text=True,
                          timeout=300, env=env)


class Pre425(unittest.TestCase):
    def test_routed_augmented_power_matches_cpython(self):
        with tempfile.TemporaryDirectory(prefix='ail-pre425-') as directory:
            for name, text in REFUSED:
                want = run_cpython(directory, text, name)
                self.assertEqual(want.returncode, 0, want.stderr)
                for general in (False, True):
                    with self.subTest(case=name, general=general):
                        status, got, output = build_run(directory, text, name, general)
                        self.assertEqual(status, 0, output)
                        self.assertEqual(got, want.stdout.replace(b'\r\n', b'\n'), output)
                        self.assertNotIn('integer overflow', output)
                        self.assertNotIn('Traceback', output)

    def test_routed_augmented_power_is_refused_by_name_in_check(self):
        with tempfile.TemporaryDirectory(prefix='ail-pre425-') as directory:
            for name, text in REFUSED:
                with self.subTest(case=name):
                    checked = check_run(directory, text, name)
                    self.assertNotEqual(checked.returncode, 0, checked.stdout + checked.stderr)
                    self.assertIn('int64 constant expression out of range',
                                  checked.stdout + checked.stderr)

    def test_safe_values_still_match_cpython(self):
        with tempfile.TemporaryDirectory(prefix='ail-pre425-') as directory:
            want = run_cpython(directory, SAFE, 'safe')
            self.assertEqual(want.returncode, 0, want.stderr)
            for general in (False, True):
                with self.subTest(general=general):
                    status, got, output = build_run(directory, SAFE, 'safe', general)
                    self.assertEqual(status, 0, output)
                    self.assertEqual(got, want.stdout.replace(b'\r\n', b'\n'), output)


if __name__ == '__main__':
    unittest.main()

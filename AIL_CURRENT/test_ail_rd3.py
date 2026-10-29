"""`check` accepts a top-level-only script, and `--strict` does not cut its construct in half.

CPython is the oracle: each accepted program below is ordinary Python, run once by CPython and
once as a compiled executable, and the two must print the same bytes.  `ail_chatgpt.py check`
must accept the same no-`def` scripts `compile` builds (the synthesised `main` of SEMANTICS
section 33), instead of failing with "no def found".

The last test pins the strict report: the construct named for `print(d)` with a `dict[str, int]`
must keep its whole type.  It used to stop at the comma inside `dict[str, int]`.
"""
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent
CLI = ROOT / 'ail_chatgpt.py'

TOP_LEVEL = '''total = 0
for i in range(6):
    if i % 2 == 0:
        total += i * i
    else:
        total -= i

words = []
for n in range(3):
    words.append(str(n) + "!")

print(total)
print(" ".join(words))
print(len(words) + total)
'''

CLASS_ONLY = '''class Point:
    def __init__(self, x: int, y: int):
        self.x = x
        self.y = y

p = Point(3, 4)
print(p.x * p.x + p.y * p.y)
'''

DICT_PRINT = '''def main() -> int:
    d: dict[str, int] = {}
    d["a"] = 1
    print(d)
    return 0

main()
'''

TOP_DICT_PRINT = '''d = {}
d["a"] = 1
print(d)
'''


class Rd3Tests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix='ail-rd3-')
        self.addCleanup(temporary.cleanup)
        self.dir = Path(temporary.name)

    def write(self, text, name='prog.py'):
        source = self.dir / name
        source.write_text(text, encoding='utf-8')
        return source

    def check(self, source):
        result = subprocess.run([sys.executable, '-B', str(CLI), 'check', str(source), '--syntax', 'python'],
                                cwd=self.dir, capture_output=True, text=True, timeout=300)
        return result, json.loads(result.stdout)

    def build(self, source, name):
        executable = self.dir / name
        result = subprocess.run([sys.executable, '-B', str(CLI), 'compile', str(source), '--syntax', 'python',
                                 '-o', str(executable)],
                                cwd=self.dir, capture_output=True, text=True, timeout=600)
        return result, executable

    def same_as_cpython(self, text, name):
        source = self.write(text, name + '.py')
        expected = subprocess.run([sys.executable, str(source)], cwd=self.dir,
                                  capture_output=True, text=True, timeout=60)
        self.assertEqual(expected.returncode, 0, expected.stderr)
        checked, report = self.check(source)
        self.assertEqual((checked.returncode, report['status'], report['stage']), (0, 'passed', 'type'),
                         checked.stdout)
        self.assertEqual(report['diagnostics'], [])
        built, executable = self.build(source, name)
        self.assertEqual(built.returncode, 0, built.stdout + built.stderr)
        ran = subprocess.run([str(executable)], cwd=self.dir, capture_output=True, text=True, timeout=60)
        self.assertEqual((ran.returncode, ran.stdout), (0, expected.stdout), ran.stderr)

    def test_top_level_script_matches_cpython(self):
        self.same_as_cpython(TOP_LEVEL, 'top_level')

    def test_single_print_script_matches_cpython(self):
        self.same_as_cpython('print("hello")\n', 'single_print')

    def test_class_only_script_matches_cpython(self):
        self.same_as_cpython(CLASS_ONLY, 'class_only')

    def test_check_refuses_a_top_level_only_script_by_name(self):
        source = self.write(TOP_DICT_PRINT, 'top_dict_print.py')
        # CPython prints the dict; the typed path refuses it by name, and `check` must say so
        # rather than reporting "no def found".
        expected = subprocess.run([sys.executable, str(source)], cwd=self.dir,
                                  capture_output=True, text=True, timeout=60)
        self.assertEqual(expected.stdout, "{'a': 1}\n")
        checked, report = self.check(source)
        self.assertEqual((checked.returncode, report['status'], report['stage']), (1, 'failed', 'type'))
        diagnostic = report['diagnostics'][0]
        self.assertEqual(diagnostic['code'], 'type')
        self.assertIn('dict', diagnostic['message'])
        self.assertNotIn('no def found', diagnostic['message'])

    def test_strict_construct_line_keeps_the_whole_type(self):
        source = self.write(DICT_PRINT, 'strict_dict.py')
        executable = self.dir / 'strict_dict'
        built = subprocess.run([sys.executable, '-B', str(CLI), 'compile', str(source), '--syntax', 'python',
                                '--strict', '-o', str(executable)],
                               cwd=self.dir, capture_output=True, text=True, timeout=600)
        self.assertEqual(built.returncode, 3, built.stdout + built.stderr)
        self.assertFalse(executable.exists())
        self.assertIn('construct:     print() given a dict[str, int]\n', built.stderr)
        self.assertNotIn('print() given a dict[str\n', built.stderr)
        report = json.loads(subprocess.run(
            [sys.executable, '-B', str(CLI), 'compile', str(source), '--syntax', 'python', '--strict', '--json',
             '-o', str(executable)],
            cwd=self.dir, capture_output=True, text=True, timeout=600).stdout)
        self.assertEqual(report['blockers'][0]['construct'], 'print() given a dict[str, int]')


if __name__ == '__main__':
    unittest.main()

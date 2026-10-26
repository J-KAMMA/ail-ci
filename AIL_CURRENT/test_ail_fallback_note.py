"""The compile-time note for a program the typed path refused and the general (boxed) path built, and the
refusal wording around it.

- `note: file:line:col: built on the general path (about 20x slower) because <typed reason>` goes to
  stderr at compile time; stdout (the JSON) and the exit status are unchanged; AIL_QUIET_FALLBACK=1 and
  --json silence it
- `sorted(range(n), key=lambda i: ...)` (an index sort) builds on the typed path and orders like CPython;
  when the program is refused for something else (print of a list), the refusal names that, not
  "'idx' is an int"
- a top-level `print({"a": 1})` refusal names its dict literal and its file:line:col
"""
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent
CLI = ROOT / 'ail_chatgpt.py'

OPTIONAL = '''from typing import Optional

def f(d: dict[int, int], x: int) -> Optional[int]:
    return d.get(x)

def main():
    r = f({3: 3}, 3)
    print(r)

main()
'''

TYPED = '''def main():
    total = 0
    for i in range(10):
        total += i
    print(total)

main()
'''

INDEX_SORT = '''def order(ys: list[int], n: int) -> int:
    ys2 = sorted(range(n), key=lambda i: (ys[i], i))
    acc = 0
    for k in ys2:
        acc = acc * 7 + k
    return acc

def main():
    ys = [3, 1, 4, 1, 5, 9, 2, 6]
    print(order(ys, len(ys)))
    idx = sorted(range(len(ys)), key=lambda i: -ys[i])
    for i in idx:
        print(i, ys[i])
    rv = sorted(range(4), key=lambda i: ys[i], reverse=True)
    print(rv[0], rv[3], len(rv))

main()
'''

# the general path now builds a key lambda that reads a local (`ys`), so the refusal is kept alive by something
# it still cannot build: str.encode()
PRINT_SORTED = '''def main():
    ys = [3, 1, 4, 1, 5]
    idx = sorted(range(len(ys)), key=lambda i: ys[i])
    print(idx)
    print(len(str(idx).encode()))

main()
'''

TOP_DICT = 'print({"a": 1})\n'


def expected_index_sort():
    ys = [3, 1, 4, 1, 5, 9, 2, 6]
    acc = 0
    for k in sorted(range(len(ys)), key=lambda i: (ys[i], i)):
        acc = acc * 7 + k
    lines = [str(acc)]
    for i in sorted(range(len(ys)), key=lambda i: -ys[i]):
        lines.append('%d %d' % (i, ys[i]))
    rv = sorted(range(4), key=lambda i: ys[i], reverse=True)
    lines.append('%d %d %d' % (rv[0], rv[3], len(rv)))
    return '\n'.join(lines) + '\n'


class FallbackNote(unittest.TestCase):
    def compile(self, text, name='prog', extra=(), **env):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        source = Path(directory.name, name + '.ail')
        source.write_text(text, encoding='utf-8')
        environment = {key: value for key, value in os.environ.items()
                       if key not in ('AIL_NO_GENERAL', 'AIL_QUIET_FALLBACK', 'AIL_IR')}
        environment.update(env)
        exe = Path(directory.name, name + '_exe')
        result = subprocess.run([sys.executable, '-B', str(CLI), 'compile', source.name, '--syntax', 'python',
                                 '-o', exe.name, *extra], cwd=directory.name, capture_output=True, text=True,
                                timeout=900, env=environment)
        return result, exe

    def test_note_names_position_reason_and_hint(self):
        result, exe = self.compile(OPTIONAL)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout)['output'], str(exe))
        lines = result.stderr.splitlines()
        self.assertEqual(len(lines), 1, result.stderr)
        # line 3; the column points at the refused annotation
        self.assertRegex(lines[0], r'^note: prog\.ail:3:\d+: built on the general path \(about 20x slower\) because ')
        self.assertIn('only a class type can be None', lines[0])
        self.assertIn('write instead:', lines[0])
        self.assertNotIn('ail-source-line', result.stderr)
        ran = subprocess.run([str(exe)], capture_output=True, text=True, timeout=60)
        self.assertEqual((ran.returncode, ran.stdout, ran.stderr), (0, '3\n', ''))

    def test_quiet_variable_and_json_silence_it(self):
        quiet, _ = self.compile(OPTIONAL, AIL_QUIET_FALLBACK='1')
        self.assertEqual((quiet.returncode, quiet.stderr), (0, ''))
        self.assertIn('"output"', quiet.stdout)
        loud, _ = self.compile(OPTIONAL, extra=('--json',))
        self.assertEqual(loud.returncode, 0, loud.stderr)
        self.assertNotIn('general path', loud.stderr)
        self.assertEqual(json.loads(loud.stdout)['status'], 'passed')

    def test_typed_program_prints_no_note(self):
        result, _ = self.compile(TYPED)
        self.assertEqual((result.returncode, result.stderr), (0, ''))

    def test_script_print_dict_refusal_names_construct_and_position(self):
        refused, _ = self.compile(TOP_DICT, name='top', AIL_NO_GENERAL='1')
        self.assertEqual(refused.returncode, 3)
        self.assertTrue(refused.stderr.startswith('top.ail:1:1: not in the subset: a dict literal; build a dict'),
                        refused.stderr)
        self.assertNotIn('ail-source-line', refused.stderr)
        built, exe = self.compile(TOP_DICT, name='top')
        self.assertEqual(built.returncode, 0, built.stderr)
        self.assertTrue(built.stderr.startswith('note: top.ail:1:1: built on the general path'), built.stderr)
        ran = subprocess.run([str(exe)], capture_output=True, text=True, timeout=60)
        self.assertEqual(ran.stdout, "{'a': 1}\n")

    def test_index_sort_builds_typed_and_orders_like_cpython(self):
        result, exe = self.compile(INDEX_SORT, AIL_NO_GENERAL='1')
        self.assertEqual((result.returncode, result.stderr), (0, ''))
        ran = subprocess.run([str(exe)], capture_output=True, text=True, timeout=60)
        self.assertEqual((ran.returncode, ran.stdout), (0, expected_index_sort()))
        default, default_exe = self.compile(INDEX_SORT)
        self.assertEqual((default.returncode, default.stderr), (0, ''))
        ran = subprocess.run([str(default_exe)], capture_output=True, text=True, timeout=60)
        self.assertEqual(ran.stdout, expected_index_sort())

    def test_refusal_after_index_sort_names_the_real_cause(self):
        # the general path builds it since branch safetynet (str.encode); the note still names the typed path's reason
        result, exe = self.compile(PRINT_SORTED)
        self.assertEqual(result.returncode, 0, result.stderr)
        # print(idx) is built on the typed path since branch typed2; str() of the list is the cause now
        self.assertIn('str() of a list is not built', result.stderr)
        self.assertNotIn('is an int', result.stderr)
        ran = subprocess.run([str(exe)], capture_output=True, text=True, timeout=60)
        self.assertEqual(ran.stdout, '[1, 3, 0, 2, 4]\n15\n')


if __name__ == '__main__':
    unittest.main()

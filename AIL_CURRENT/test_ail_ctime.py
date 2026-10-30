"""Compile-time trims that must not change what a build produces.

* the shipped unprintable-code-point table (unprintable_data.py) equals a scan of this Python's str.isprintable();
* the compiler child process keeps writing bytecode unless PYTHONDONTWRITEBYTECODE is set;
* a build leaves the same executable bytes whether the bytecode cache is cold or warm.
"""
import os
import re
import subprocess
import sys
import tempfile
import unicodedata
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / 'python/pkg-v12'))

import ail_chatgpt  # noqa: E402
import unprintable_data  # noqa: E402

SOURCE = 'fn main() -> int {\n    let t: int = 0;\n    for i in range(0, 10) { t = t + i; }\n    print(t);\n    return 0;\n}\n'


def scan_rows():
    ranges, start, end = [], None, None
    for codepoint in range(128, 0x110000):
        if not chr(codepoint).isprintable():
            if start is None:
                start = codepoint
            elif codepoint != end + 1:
                ranges.append((start, end))
                start = codepoint
            end = codepoint
    if start is not None:
        ranges.append((start, end))
    return ranges


class UnprintableTable(unittest.TestCase):
    def test_shipped_table_matches_a_scan(self):
        flat = unprintable_data.ROWS.get(unicodedata.unidata_version)
        if flat is None:
            self.skipTest('no shipped table for Unicode %s' % unicodedata.unidata_version)
        self.assertEqual(len(flat) % 2, 0)
        self.assertEqual([(flat[i], flat[i + 1]) for i in range(0, len(flat), 2)], scan_rows())

    def test_rows_text_comes_from_the_shipped_table(self):
        import cruntime
        if unicodedata.unidata_version not in unprintable_data.ROWS:
            self.skipTest('no shipped table')
        with mock.patch.object(cruntime, '_HOST_ROWS', None):
            text = cruntime._host_unprintable_rows()
        self.assertTrue(re.fullmatch(r'(    \{\d+, \d+\},\n)+', text))
        self.assertEqual(text, ''.join('    {%d, %d},\n' % row for row in scan_rows()))


class BytecodeSwitch(unittest.TestCase):
    def test_child_python_command(self):
        with mock.patch.dict(os.environ):
            os.environ.pop('PYTHONDONTWRITEBYTECODE', None)
            self.assertEqual(ail_chatgpt._compiler_python(), [sys.executable])
            os.environ['PYTHONDONTWRITEBYTECODE'] = '1'
            self.assertEqual(ail_chatgpt._compiler_python(), [sys.executable, '-B'])

    def test_build_output_does_not_depend_on_bytecode(self):
        with tempfile.TemporaryDirectory() as work:
            work = Path(work)
            source = work / 'p.ail'
            source.write_text(SOURCE, encoding='utf-8')
            digests = []
            for label, bytecode in (('nopyc', False), ('pyc', True)):
                env = dict(os.environ, AIL_CACHE=str(work / ('cache-' + label)))
                env.pop('PYTHONDONTWRITEBYTECODE', None)
                if not bytecode:
                    env['PYTHONDONTWRITEBYTECODE'] = '1'
                out = work / label
                done = subprocess.run([sys.executable, '-B', str(ROOT / 'ail_chatgpt.py'), 'compile', str(source), '-o', str(out)],
                                      env=env, capture_output=True, text=True, timeout=300)
                self.assertEqual(done.returncode, 0, done.stderr)
                run = subprocess.run([str(out)], capture_output=True, text=True, timeout=30)
                self.assertEqual((run.returncode, run.stdout), (0, '45\n'))
                digests.append(out.read_bytes())
            self.assertEqual(digests[0], digests[1])


if __name__ == '__main__':
    unittest.main()

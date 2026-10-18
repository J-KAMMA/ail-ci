"""Executables link the C library dynamically by default; `compile --static` links it statically.

Windows always links statically (no runtime DLLs beside a MinGW build), so the size check there
only confirms both builds run.
"""
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent


class LinkModeTests(unittest.TestCase):
    def build(self, work, *flags):
        source = work / 'hello.ail'
        source.write_text('fn main() -> int { print("hello"); return 0; }\n', encoding='utf8')
        output = work / ('hello' + ''.join(f.strip('-') for f in flags))
        result = subprocess.run([sys.executable, '-B', str(ROOT / 'ail_chatgpt.py'), 'compile', *flags,
                                 str(source), '-o', str(output)], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        return output if output.exists() else output.with_suffix('.exe')

    def test_default_dynamic_and_static_option(self):
        with tempfile.TemporaryDirectory() as tmp:
            work = Path(tmp)
            if sys.platform == 'darwin':
                # Apple ships no static C library: the option is refused by name, the default build runs
                refused = subprocess.run([sys.executable, '-B', str(ROOT / 'ail_chatgpt.py'), 'compile', '--static',
                                          str(work / 'x.ail'), '-o', str(work / 'x')], capture_output=True, text=True)
                self.assertEqual(refused.returncode, 2)
                self.assertIn('--static is not supported on macOS', refused.stderr)
                run = subprocess.run([str(self.build(work))], capture_output=True, text=True, timeout=30)
                self.assertEqual((run.returncode, run.stdout), (0, 'hello\n'))
                return
            dynamic, static = self.build(work), self.build(work, '--static')
            for binary in (dynamic, static):
                run = subprocess.run([str(binary)], capture_output=True, text=True, timeout=30)
                self.assertEqual((run.returncode, run.stdout), (0, 'hello\n'))
            if os.name != 'nt':
                self.assertLess(dynamic.stat().st_size * 4, static.stat().st_size)


if __name__ == '__main__':
    unittest.main()

"""`compile --target` cross-compiles with zig cc; skipped when zig is not installed.

Checks the executable format for Windows, macOS and Linux arm64, and runs a zig-built binary for
the host's own target.
"""
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def _zig():
    local = Path.home() / 'tools' / 'zig' / ('zig.exe' if os.name == 'nt' else 'zig')
    return os.environ.get('AIL_ZIG') or shutil.which('zig') or (str(local) if local.is_file() else None)


@unittest.skipUnless(_zig(), 'zig is not installed')
class CrossTargetTests(unittest.TestCase):
    def build(self, work, target):
        source = work / 'hello.ail'
        source.write_text('fn main() -> int { print("hello " + str(6 * 7)); return 0; }\n', encoding='utf8')
        output = work / ('hello-' + target)
        result = subprocess.run([sys.executable, '-B', str(ROOT / 'ail_chatgpt.py'), 'compile', '--target', target,
                                 str(source), '-o', str(output)], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        return output

    def test_executable_formats(self):
        with tempfile.TemporaryDirectory() as tmp:
            work = Path(tmp)
            self.assertEqual(self.build(work, 'windows').read_bytes()[:2], b'MZ')
            self.assertIn(self.build(work, 'macos').read_bytes()[:4], (b'\xcf\xfa\xed\xfe', b'\xfe\xed\xfa\xcf'))
            elf = self.build(work, 'linux-arm64').read_bytes()
            self.assertEqual((elf[:4], elf[18]), (b'\x7fELF', 0xB7))

    @unittest.skipUnless(sys.platform.startswith('linux') and os.uname().machine == 'x86_64', 'needs an x86_64 Linux host')
    def test_host_target_runs(self):
        with tempfile.TemporaryDirectory() as tmp:
            binary = self.build(Path(tmp), 'linux')
            run = subprocess.run([str(binary)], capture_output=True, text=True, timeout=30)
            self.assertEqual((run.returncode, run.stdout), (0, 'hello 42\n'))


if __name__ == '__main__':
    unittest.main()

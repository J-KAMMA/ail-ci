"""G6 platforms: UTF-8 text output, a BOM-led source, per-OS link flags (decision Q8, Q10)."""
import json
import os
from pathlib import Path
import subprocess
import sys
import unittest
import test_ail_c_objects as support

PKG = support.ROOT / 'python' / 'pkg-v12'
TEXT = 'こんにちは héllo 😀 Привет'
CONSOLE_FLAGS = ['-D_Exit=ail_wincon_exit', str(PKG / 'ail_wincon.c')]


def link_flags_with(**env):
    """pipeline.link_flags() in a fresh interpreter, so environment edits cannot leak between tests."""
    code = 'import pipeline, json; print(json.dumps(pipeline.link_flags()))'
    clean = {k: v for k, v in os.environ.items() if k not in ('AIL_STATIC', 'AIL_TARGET_OS')}
    out = subprocess.run([sys.executable, '-B', '-c', code], cwd=PKG, env=dict(clean, **env),
                         capture_output=True, text=True, timeout=60)
    assert out.returncode == 0, out.stderr
    return json.loads(out.stdout)


class PlatformTests(unittest.TestCase):
    setUp = support.CObjectTests.setUp
    command = support.CObjectTests.command

    def build_and_run(self, name, prefix):
        source = f"def main()->int:\n    print('{TEXT}')\n    print(len('{TEXT}'))\n    return 0\nmain()\n"
        path = self.root / (name + '.ail')
        path.write_bytes(prefix + source.encode('utf8'))
        output = self.root / name
        built = self.command('compile', path, '-o', output)
        self.assertEqual(built.returncode, 0, built.stderr.decode(errors='replace'))
        exe = output if output.is_file() else Path(str(output) + '.exe')
        return subprocess.run([str(exe)], capture_output=True, timeout=30)

    def test_utf8_text_and_line_ends_on_every_platform(self):
        newline = b'\r\n' if sys.platform == 'win32' else b'\n'
        want = TEXT.encode('utf8') + newline + str(len(TEXT)).encode() + newline
        for name, prefix in (('plain', b''), ('bom', b'\xef\xbb\xbf')):
            ran = self.build_and_run(name, prefix)
            self.assertEqual((ran.returncode, ran.stdout, ran.stderr), (0, want, b''), name)

    def test_link_flags_per_target(self):
        self.assertEqual(link_flags_with(), ['-static', *CONSOLE_FLAGS] if os.name == 'nt' else [])
        self.assertEqual(link_flags_with(AIL_TARGET_OS='windows'), ['-static', *CONSOLE_FLAGS])
        self.assertEqual(link_flags_with(AIL_STATIC='1')[:1], ['-static'])

    def test_console_unit_is_shipped_and_guarded(self):
        manifest = json.loads((support.ROOT / 'MANIFEST.json').read_text(encoding='utf8'))
        self.assertIn('python/pkg-v12/ail_wincon.c', manifest['sdk_files'])
        text = (PKG / 'ail_wincon.c').read_text(encoding='utf8')
        self.assertIn('SetConsoleOutputCP(CP_UTF8)', text)
        self.assertIn('#ifdef _WIN32', text)   # an empty unit everywhere else


if __name__ == '__main__':
    unittest.main()

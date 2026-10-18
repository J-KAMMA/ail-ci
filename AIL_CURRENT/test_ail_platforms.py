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

# Line ends written by the program: stdout and stderr (CPython's sys.stdout writes os.linesep on Windows), and text
# files with every newline= setting (default, "", "\n", "\r", "\r\n"), append, print(file=) and binary. The bytes
# are compared with what CPython itself produces on the same platform, so the expectation is CRLF on Windows and
# LF elsewhere without this file knowing which.
LINE_ENDS = """import sys


def hexb(b: bytes) -> None:
    for x in b:
        print(x, end=" ")
    print()


def main() -> int:
    print("plain line")
    print("two", "words", end="!\\n")
    print("cr\\rlf\\ncrlf\\r\\nend", end="")
    print()
    print("tail", file=sys.stderr)
    print("tail two\\nthree", file=sys.stderr)
    p = "w.txt"
    with open(p, "w") as f:
        f.write("a\\nb\\r\\nc\\n")
    with open(p, "rb") as f:
        hexb(f.read())
    with open(p, "w", newline="") as f:
        f.write("a\\nb\\r\\nc\\n")
    with open(p, "rb") as f:
        hexb(f.read())
    with open(p, "w", newline="\\n") as f:
        f.write("a\\nb\\r\\nc\\n")
    with open(p, "rb") as f:
        hexb(f.read())
    with open(p, "w", newline="\\r") as f:
        f.write("a\\nb\\r\\nc\\n")
    with open(p, "rb") as f:
        hexb(f.read())
    with open(p, "w", newline="\\r\\n") as f:
        print("x", file=f)
        print("y", "z", file=f)
    with open(p, "rb") as f:
        hexb(f.read())
    with open(p, "a") as f:
        f.write("tail\\n")
    with open(p, "rb") as f:
        hexb(f.read())
    with open(p, "wb") as f:
        f.write(b"raw\\nbytes\\r\\n")
    with open(p, "rb") as f:
        hexb(f.read())
    with open(p) as f:
        print(f.read(), end="")
    with open("last.txt", "w") as f:
        f.write("one\\ntwo\\n")
    return 0


main()
"""
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

    def test_text_output_and_files_have_the_line_ends_cpython_writes_here(self):
        source = self.root / 'lineends.py'
        source.write_text(LINE_ENDS, encoding='utf8')
        for name in ('cpy', 'ail'):
            (self.root / name).mkdir()
        env = dict(os.environ, PYTHONUTF8='1')
        env.pop('PYTHONPATH', None)
        want = subprocess.run([sys.executable, '-B', str(source)], cwd=self.root / 'cpy', capture_output=True,
                              timeout=60, env=env)
        self.assertEqual(want.returncode, 0, want.stderr.decode(errors='replace'))
        output = self.root / 'lineends_exe'
        built = self.command('compile', source, '-o', output)
        self.assertEqual(built.returncode, 0, built.stderr.decode(errors='replace'))
        exe = output if output.is_file() else Path(str(output) + '.exe')
        got = subprocess.run([str(exe)], cwd=self.root / 'ail', capture_output=True, timeout=60)
        self.assertEqual(got.returncode, 0, got.stderr.decode(errors='replace'))
        self.assertEqual(got.stdout, want.stdout)
        self.assertEqual(got.stderr, want.stderr)
        for name in ('w.txt', 'last.txt'):
            self.assertEqual((self.root / 'ail' / name).read_bytes(), (self.root / 'cpy' / name).read_bytes(), name)
        # what the comparison means on each platform, so that two equal wrong answers cannot pass
        newline = b'\r\n' if sys.platform == 'win32' else b'\n'
        self.assertTrue(got.stdout.startswith(b'plain line' + newline + b'two words!' + newline))
        self.assertEqual((self.root / 'ail' / 'last.txt').read_bytes(), b'one' + newline + b'two' + newline)

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

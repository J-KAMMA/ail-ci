#!/usr/bin/env python3
"""Windows UTF-8 output probe (decision Q8: text I/O is UTF-8).

Builds a small program with the compiler under AIL_CURRENT, runs it with its output redirected and
checks the bytes: UTF-8 text, '\\r\\n' line ends (the C library's text mode, which CPython's
sys.stdout also produces on Windows), and a source file that starts with a UTF-8 byte order mark
(Windows editors write one; CPython accepts it). The console path (SetConsoleOutputCP in
AIL_CURRENT/python/pkg-v12/ail_wincon.c) needs a real console and is exercised by hand.
"""
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2] / 'AIL_CURRENT'
TEXT = 'こんにちは héllo 😀 Привет'
SOURCE = "def main()->int:\n    print('%s')\n    print(len('%s'))\n    return 0\nmain()\n" % (TEXT, TEXT)


def main():
    with tempfile.TemporaryDirectory(prefix='ail-probe-') as directory:
        base = Path(directory)
        failures = 0
        for name, prefix in (('plain', b''), ('bom', b'\xef\xbb\xbf')):
            source = base / (name + '.ail')
            source.write_bytes(prefix + SOURCE.encode('utf8'))
            output = base / name
            built = subprocess.run([sys.executable, '-X', 'utf8', '-B', str(ROOT / 'ail_chatgpt.py'), 'compile',
                                    str(source), '-o', str(output)], capture_output=True)
            if built.returncode:
                print('FAIL build %s: %s' % (name, built.stderr.decode('utf8', 'replace')[-800:]))
                failures += 1
                continue
            exe = output.with_suffix('.exe') if sys.platform == 'win32' else output
            ran = subprocess.run([str(exe)], capture_output=True)
            newline = b'\r\n' if sys.platform == 'win32' else b'\n'
            want = (TEXT.encode('utf8') + newline + str(len(TEXT)).encode() + newline)
            ok = ran.returncode == 0 and ran.stdout == want
            print('%s %s: %r' % ('ok  ' if ok else 'FAIL', name, ran.stdout[:60]))
            failures += not ok
    return 1 if failures else 0


if __name__ == '__main__':
    sys.exit(main())

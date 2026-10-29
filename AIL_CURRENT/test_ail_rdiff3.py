"""rdiff3: ``repr(e)`` of a ``KeyError`` raised with a non-literal str argument matches CPython.

The general build raised ``KeyError(k)`` as a message-only exception whose message is ``repr(k)``,
so a program that printed only ``repr(e)`` (not ``e.args``) showed ``KeyError("'v'")`` instead of
``KeyError('v')``.  ``Color["BLUE"]`` of an Enum goes through the same raise.  The argument is now
always kept on a raised ``KeyError``.
"""
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent
CHATGPT = str(ROOT / 'ail_chatgpt.py')


def cpython(directory, name, text):
    src = Path(directory) / (name + '_cpython.py')
    src.write_text(text, encoding='utf-8')
    done = subprocess.run([sys.executable, '-B', str(src)], capture_output=True, timeout=120,
                          env=dict(os.environ, PYTHONUTF8='1', PYTHONWARNINGS='ignore'))
    return done.stdout.replace(b'\r\n', b'\n'), done.returncode


def build(directory, name, text, general):
    src = Path(directory) / (name + '.py')
    src.write_text(text, encoding='utf-8')
    exe = Path(directory) / ('exe_' + name + ('_g' if general else '_d'))
    env = dict(os.environ, AIL_NO_CACHE='1', AIL_QUIET_FALLBACK='1')
    env.pop('AIL_NO_GENERAL', None)
    if general:
        env['AIL_UNIFIED_FORCE'] = '1'
    else:
        env.pop('AIL_UNIFIED_FORCE', None)
    return exe, subprocess.run([sys.executable, '-B', CHATGPT, 'compile', src.name,
                                '--syntax', 'python', '-o', exe.name], cwd=directory,
                               capture_output=True, text=True, timeout=900, env=env)


MATCHING = {
    'str_param': 'def f(k: str) -> int:\n    raise KeyError(k)\n\n\ndef main() -> None:\n    try:\n        f("v")\n    except KeyError as e:\n        print(repr(e))\n    try:\n        f("it\'s")\n    except KeyError as e:\n        print(repr(e), str(e))\n\n\nmain()\n',
    'int_param': 'def f(k: int) -> int:\n    raise KeyError(k)\n\n\ndef main() -> None:\n    try:\n        f(7)\n    except KeyError as e:\n        print(repr(e), e)\n\n\nmain()\n',
    'enum_lookup': 'from enum import Enum\n\n\nclass Color(Enum):\n    RED = "red"\n    GREEN = "green"\n\n\ndef main() -> None:\n    try:\n        Color["BLUE"]\n    except KeyError as e:\n        print(repr(e))\n\n\nmain()\n',
}


class Rdiff3Tests(unittest.TestCase):
    def test_matches_cpython(self):
        with tempfile.TemporaryDirectory(prefix='ail-rdiff3-') as directory:
            for slug, text in MATCHING.items():
                want = cpython(directory, slug, text)
                for general in (True, False):
                    exe, built = build(directory, '%s_%s' % (slug, 'g' if general else 'd'), text, general)
                    self.assertEqual(built.returncode, 0, (slug, general, built.stdout + built.stderr))
                    got = subprocess.run([str(exe)], capture_output=True, timeout=120, cwd=directory)
                    self.assertEqual(got.stdout.replace(b'\r\n', b'\n'), want[0],
                                     (slug, general, got.stderr[-800:]))
                    self.assertEqual(got.returncode, want[1], (slug, general, got.stderr[-800:]))


if __name__ == '__main__':
    unittest.main()

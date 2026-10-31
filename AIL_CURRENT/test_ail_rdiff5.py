"""rdiff5: a class defining __getattr__, __getattribute__, __setattr__ or __delattr__ is refused.

The general build accepted these hooks and never called them: ``a.missing`` raised AttributeError
where CPython calls ``__getattr__``, and a ``__setattr__`` that logged ran silently without the log.
The program is now refused by name.
"""
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent
CHATGPT = str(ROOT / 'ail_chatgpt.py')
MESSAGE = 'attribute access hooks are not built'

REFUSED = {
    'getattr': 'class A:\n    def __init__(self):\n        self.x = 1\n\n    def __getattr__(self, name):\n        return "missing:" + name\n\n\ndef main():\n    a = A()\n    print(a.x)\n\n\nmain()\n',
    'getattribute': 'class A:\n    def __init__(self):\n        self.x = 1\n\n    def __getattribute__(self, name):\n        return "ga:" + name\n\n\ndef main():\n    a = A()\n    print(a.x)\n\n\nmain()\n',
    'setattr': 'class A:\n    def __init__(self):\n        self.x = 1\n\n    def __setattr__(self, name, value):\n        print("set", name)\n        self.__dict__[name] = value\n\n\ndef main():\n    a = A()\n    print(a.x)\n\n\nmain()\n',
    'delattr': 'class A:\n    def __init__(self):\n        self.x = 1\n\n    def __delattr__(self, name):\n        print("del", name)\n\n\ndef main():\n    a = A()\n    print(a.x)\n\n\nmain()\n',
}


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
    return subprocess.run([sys.executable, '-B', CHATGPT, 'compile', src.name,
                           '--syntax', 'python', '-o', exe.name], cwd=directory,
                          capture_output=True, text=True, timeout=900, env=env)


class Rdiff5Tests(unittest.TestCase):
    def test_refused_by_name(self):
        with tempfile.TemporaryDirectory(prefix='ail-rdiff5-') as directory:
            for slug, text in REFUSED.items():
                for general in (True, False):
                    built = build(directory, '%s_%s' % (slug, 'g' if general else 'd'), text, general)
                    output = built.stdout + built.stderr
                    self.assertNotEqual(built.returncode, 0, (slug, general, output[-800:]))
                    self.assertIn(MESSAGE, output, (slug, general, output[-800:]))


if __name__ == '__main__':
    unittest.main()

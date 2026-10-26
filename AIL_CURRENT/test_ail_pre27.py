"""The optional-import idiom (`try: import X ... except ImportError`) is refused by name and located.

Job errmsg3 recorded that this refusal had no file:line:col. The import inside the try is resolved
at build time, so a module that may be missing cannot be tested at run time; the general emitter now
names the import, points at it, and gives the rewrite. Other unsupported caught exception types are
located at their `try` too. A handler for `Exception` is unchanged.
"""
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent

REFUSED = {
    'html_import_error': ('try:\n    import html\nexcept ImportError:\n    print("no")\n',
                          'prog.py:2:5:', ["import of 'html'", 'guarded by `except ImportError`',
                                            'move the import to the top']),
    'html_from_import': ('try:\n    from html import escape\nexcept ImportError:\n    print("no")\n',
                         'prog.py:2:5:', ["import of 'html'", 'guarded by `except ImportError`']),
    'two_modules': ('try:\n    import math, html\nexcept ImportError:\n    print("no")\n',
                    'prog.py:2:5:', ["import of 'math', 'html'", 'guarded by `except ImportError`']),
    'module_not_found': ('try:\n    import html\nexcept ModuleNotFoundError:\n    print("no")\n',
                         'prog.py:2:5:', ["import of 'html'", 'guarded by `except ModuleNotFoundError`']),
    'tuple_handler': ('try:\n    import html\nexcept (ValueError, ImportError):\n    print("no")\n',
                      'prog.py:2:5:', ["import of 'html'", 'guarded by `except ImportError`']),
    'alias': ('try:\n    import html as h\nexcept ImportError:\n    print("no")\n',
              'prog.py:2:5:', ["import of 'html'", 'guarded by `except ImportError`']),
    'in_a_function': ('def f():\n    try:\n        import html\n    except ImportError:\n        return 0\n'
                      '    return 1\n\n\nprint(f())\n',
                      'prog.py:3:9:', ["import of 'html'", 'guarded by `except ImportError`']),
    'no_import_still_located': ('try:\n    x = 1\nexcept ImportError:\n    print("no")\nprint("done")\n',
                                'prog.py:1:1:', ['a caught exception type ImportError']),
    'other_type_still_located': ('try:\n    x = 1\nexcept KeyboardInterrupt:\n    print("no")\n',
                                 'prog.py:1:1:', ['a caught exception type KeyboardInterrupt']),
}

ACCEPTED = ('try:\n    import html\nexcept Exception:\n    print("no")\nprint("done")\n', b'done\n')


def compile_case(directory, text, name, general):
    src = Path(directory) / 'prog.py'
    src.write_text(text, encoding='utf-8')
    env = dict(os.environ, AIL_NO_CACHE='1', AIL_QUIET_FALLBACK='1')
    env.pop('AIL_NO_GENERAL', None)
    if general:
        env['AIL_UNIFIED_FORCE'] = '1'
    else:
        env.pop('AIL_UNIFIED_FORCE', None)
    return subprocess.run([sys.executable, '-B', str(ROOT / 'ail_chatgpt.py'), 'compile', src.name,
                           '--syntax', 'python', '-o', 'prog'], cwd=directory,
                          capture_output=True, text=True, timeout=900, env=env)


class OptionalImportRefusal(unittest.TestCase):
    def test_refusals_name_the_import_and_its_position(self):
        for name, (text, where, phrases) in REFUSED.items():
            for general in (True, False):
                with self.subTest(name=name, general=general), tempfile.TemporaryDirectory() as directory:
                    built = compile_case(directory, text, name, general)
                    message = built.stdout + built.stderr
                    self.assertIn(built.returncode, (2, 3), message)
                    self.assertFalse(Path(directory, 'prog').exists(), message)
                    self.assertTrue(message.startswith(where), message)
                    for phrase in phrases:
                        self.assertIn(phrase, message)

    def test_a_handler_for_exception_is_unchanged(self):
        text, want = ACCEPTED
        for general in (True, False):
            with self.subTest(general=general), tempfile.TemporaryDirectory() as directory:
                built = compile_case(directory, text, 'accepted', general)
                self.assertEqual(built.returncode, 0, built.stdout + built.stderr)
                got = subprocess.run([str(Path(directory, 'prog'))], capture_output=True, timeout=120,
                                     cwd=directory)
                self.assertEqual(got.stdout.replace(b'\r\n', b'\n'), want)


if __name__ == '__main__':
    unittest.main()

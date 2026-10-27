"""The optional-import idiom (`try: import X ... except ImportError`) is refused by name and located.

Job errmsg3 recorded that this refusal had no file:line:col. The import inside the try is resolved
at build time, so a module that may be missing cannot be tested at run time; the general emitter now
names the import in the try body, points at it, and gives the rewrite. An import only in a handler,
`else` or `finally` is not called guarded: the caught type itself is located at the `try`. A handler
for `Exception` is unchanged.
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
    'math_import': ('try:\n    import math\nexcept ImportError:\n    print("no")\n'
                    'print(math.floor(2.5))\n',
                    'prog.py:2:5:', ["import of 'math'", 'guarded by `except ImportError`']),
    'in_a_function': ('def f():\n    try:\n        import html\n    except ImportError:\n        return 0\n'
                      '    return 1\n\n\nprint(f())\n',
                      'prog.py:3:9:', ["import of 'html'", 'guarded by `except ImportError`']),
    'inside_if': ('def f(flag):\n    try:\n        if flag:\n            import html\n'
                  '    except ImportError:\n        return 0\n    return 1\n\n\nprint(f(True))\n',
                  'prog.py:4:13:', ["import of 'html'", 'guarded by `except ImportError`']),
    'inside_loop': ('try:\n    for name in ["html"]:\n        import html\n'
                    'except ImportError:\n    print("no")\n',
                    'prog.py:3:9:', ["import of 'html'", 'guarded by `except ImportError`']),
    'no_import_still_located': ('try:\n    x = 1\nexcept ImportError:\n    print("no")\nprint("done")\n',
                                'prog.py:1:1:', ['a caught exception type ImportError']),
    'other_type_still_located': ('try:\n    x = 1\nexcept KeyboardInterrupt:\n    print("no")\n',
                                 'prog.py:1:1:', ['a caught exception type KeyboardInterrupt']),
    'import_only_in_handler': ('try:\n    x = 1\nexcept ImportError:\n    import html\n'
                               'print("done")\n',
                               'prog.py:1:1:', ['a caught exception type ImportError']),
    'import_only_in_else': ('try:\n    x = 1\nexcept ImportError:\n    pass\nelse:\n    import html\n'
                            'print("done")\n',
                            'prog.py:1:1:', ['a caught exception type ImportError']),
    'import_only_in_finally': ('try:\n    x = 1\nexcept ImportError:\n    pass\nfinally:\n'
                               '    import math\nprint("done")\n',
                               'prog.py:1:1:', ['a caught exception type ImportError']),
}

ACCEPTED = {
    'exception_handler': ('try:\n    import html\nexcept Exception:\n    print("no")\nprint("done")\n',
                          b'done\n'),
    'zero_division': ('try:\n    x = 1 // 0\nexcept ZeroDivisionError:\n    print("caught")\n'
                      'else:\n    print("not caught")\n',
                      b'caught\n'),
    'plain_two_unused': ('import math, html\nprint(math.floor(2.5))\n', b'2\n'),
    'plain_html_unused': ('import html\nprint("done")\n', b'done\n'),
}


def compile_case(directory, text, general):
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
                    built = compile_case(directory, text, general)
                    message = built.stdout + built.stderr
                    self.assertIn(built.returncode, (2, 3), message)
                    self.assertFalse(Path(directory, 'prog').exists(), message)
                    self.assertTrue(message.startswith(where), message)
                    for phrase in phrases:
                        self.assertIn(phrase, message)

    def test_accepted_programs_still_run(self):
        for name, (text, want) in ACCEPTED.items():
            for general in (True, False):
                with self.subTest(name=name, general=general), tempfile.TemporaryDirectory() as directory:
                    built = compile_case(directory, text, general)
                    self.assertEqual(built.returncode, 0, built.stdout + built.stderr)
                    got = subprocess.run([str(Path(directory, 'prog'))], capture_output=True, timeout=120,
                                         cwd=directory)
                    self.assertEqual(got.stdout.replace(b'\r\n', b'\n'), want)


if __name__ == '__main__':
    unittest.main()

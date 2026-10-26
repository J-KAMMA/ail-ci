"""Pre-270: a relative import below the top level is refused by name at its own line.

The reviewer of job rbpre52 recorded the relative/local import refusal and the user class
shadowing ``ImportError`` as pre-existing.  A relative import inside a module-level ``try`` used
to hit the generic local-import-below-the-top-level message, which did not name the relative
form; the entry-file relative-import check now runs first, so the refusal names
``from . import ...`` and points at the import.  A local import inside a module-level ``try`` is
now described as being in a try block rather than in a condition or loop.  A user class named
``ImportError`` keeps its existing named refusal.
"""
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def compile_files(directory, files, entry='prog.py', general=False):
    for name, text in files.items():
        path = Path(directory, name)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding='utf-8')
    env = dict(os.environ, AIL_NO_CACHE='1', AIL_QUIET_FALLBACK='1')
    env.pop('AIL_NO_GENERAL', None)
    if general:
        env['AIL_UNIFIED_FORCE'] = '1'
    else:
        env.pop('AIL_UNIFIED_FORCE', None)
    return subprocess.run([sys.executable, '-B', str(ROOT / 'ail_chatgpt.py'), 'compile', entry,
                           '--syntax', 'python', '-o', 'prog'], cwd=directory,
                          capture_output=True, text=True, timeout=900, env=env)


RELATIVE = {
    'from_import_in_try': (
        'try:\n    from . import thing\nexcept ImportError:\n    print("caught")\n',
        'prog.py:2:5:', ['relative import', '`from . import ...`', 'entry file']),
    'module_import_in_try': (
        'try:\n    from .thing import x\nexcept ImportError:\n    print("caught")\n',
        'prog.py:2:5:', ['relative import', '`from .thing import ...`', 'entry file']),
    'top_level_relative': (
        'from . import thing\nprint("ran")\n',
        'prog.py:1:1:', ['relative import', '`from . import ...`', 'entry file']),
}

SHADOW = (
    'class ImportError(Exception):\n    pass\n\ntry:\n    raise ImportError("x")\n'
    'except ImportError as e:\n    print("caught", e)\n',
    'prog.py:', ['AIL class \'ImportError\'', 'shadows the built-in exception ImportError',
                 'cannot be redefined'],
)

LOCAL_TRY = (
    'try:\n    import lib\nexcept ImportError:\n    print("no")\nprint("done")\n',
    'main.py:2:5:', ['below the top level', 'inside a try block'])


class Pre270Refusals(unittest.TestCase):
    def test_relative_imports_are_named(self):
        for name, (text, where, phrases) in RELATIVE.items():
            for general in (True, False):
                with self.subTest(name=name, general=general), tempfile.TemporaryDirectory() as directory:
                    built = compile_files(directory, {'prog.py': text}, general=general)
                    message = built.stdout + built.stderr
                    self.assertIn(built.returncode, (2, 3), message)
                    self.assertFalse(Path(directory, 'prog').exists(), message)
                    self.assertTrue(message.startswith(where), message)
                    for phrase in phrases:
                        self.assertIn(phrase, message)

    def test_import_in_a_module_level_try_is_named(self):
        text, where, phrases = LOCAL_TRY
        for general in (True, False):
            with self.subTest(general=general), tempfile.TemporaryDirectory() as directory:
                built = compile_files(directory, {'main.py': text, 'lib.py': 'K = 1\n'},
                                      entry='main.py', general=general)
                message = built.stdout + built.stderr
                self.assertIn(built.returncode, (2, 3), message)
                self.assertFalse(Path(directory, 'prog').exists(), message)
                self.assertTrue(message.startswith(where), message)
                for phrase in phrases:
                    self.assertIn(phrase, message)

    def test_user_import_error_class_keeps_its_named_refusal(self):
        text, where, phrases = SHADOW
        for general in (True, False):
            with self.subTest(general=general), tempfile.TemporaryDirectory() as directory:
                built = compile_files(directory, {'prog.py': text}, general=general)
                message = built.stdout + built.stderr
                self.assertIn(built.returncode, (2, 3), message)
                self.assertFalse(Path(directory, 'prog').exists(), message)
                self.assertTrue(message.startswith(where), message)
                for phrase in phrases:
                    self.assertIn(phrase, message)


if __name__ == '__main__':
    unittest.main()

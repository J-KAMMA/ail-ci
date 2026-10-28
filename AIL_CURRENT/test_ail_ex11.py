"""ex11: `__file__` is the source path CPython gives the module, on both builds.

The exercise's Python-syntax examples under `language_examples` most often stop at the loader's
`__file__ is not available` refusal (row_codec_compare, row_decimal_quad, row_state_quad_compare,
row_store_identity_compare and test_row_cpu_profile all reach it through row_locals_compare).
A module now reads its own source path, and `imported.__file__` reads the imported module's path;
a namespace package has None.  The entry keeps the spelling CPython uses: an absolute argument is
kept, a relative one is joined to the compile-time working directory, so `./name.py`, `../name.py`
and a symlink name match.  Rebinding or deleting `__file__` is refused by name (CPython would let
the module replace its own path, which a compiled program cannot follow).
"""
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent
CHATGPT = str(ROOT / 'ail_chatgpt.py')
REFUSED = '__file__ cannot be rebound or deleted'


def cpython(directory, name, text):
    src = Path(directory) / name
    src.write_text(text, encoding='utf-8')
    done = subprocess.run([sys.executable, '-B', str(src)], capture_output=True, timeout=120,
                          cwd=directory, env=dict(os.environ, PYTHONUTF8='1', PYTHONWARNINGS='ignore'))
    return done.stdout.replace(b'\r\n', b'\n'), done.returncode


def build(directory, name, text, general, *, path=None):
    src = Path(directory) / name
    src.write_text(text, encoding='utf-8')
    exe = Path(directory) / ('exe_' + name + ('_g' if general else '_d'))
    env = dict(os.environ, AIL_NO_CACHE='1', AIL_QUIET_FALLBACK='1')
    env.pop('AIL_NO_GENERAL', None)
    if general:
        env['AIL_UNIFIED_FORCE'] = '1'
    else:
        env.pop('AIL_UNIFIED_FORCE', None)
    if path is not None:
        env['AIL_PATH'] = str(path)
    return subprocess.run([sys.executable, '-B', CHATGPT, 'compile', name,
                           '--syntax', 'python', '-o', exe.name], cwd=directory,
                          capture_output=True, text=True, timeout=900, env=env), exe


MATCHING = {
    'basic': 'print(__file__)\n',
    'repr': 'print(repr(__file__)); print(__file__.endswith(".py"), len(__file__) > 0)\n',
    'function': 'def show():\n    print(__file__)\n\ndef main():\n    show()\n\nmain()\n',
    'routes': '''class Box:
    pass

def ident(value):
    return value

box = Box()
box.path = __file__
print(__file__)
print(ident(__file__))
print([__file__][0])
print({"k": __file__}["k"])
print(box.path)
''',
    'local_shadow': 'def f():\n    __file__ = "local"\n    return __file__\n\nprint(f())\n',
    'class_shadow': 'class C:\n    __file__ = "class-file"\n\nprint(C.__file__)\n',
    'pathlib': 'from pathlib import Path\nprint(Path(__file__).name)\nprint(Path(__file__).is_absolute())\n',
    'nested': 'def outer():\n    def inner():\n        return __file__\n    return inner()\n\nprint(outer())\nprint([__file__ for _ in range(2)])\n',
    'comprehension': 'print({key: __file__ for key in ("a", "b")})\n',
}

REFUSED_PROGRAMS = {
    'module_assign': '__file__ = "changed"\nprint(__file__)\n',
    'delete': 'del __file__\n',
    'global_assign': 'def f():\n    global __file__\n    __file__ = "changed"\n\nf()\nprint(__file__)\n',
}


class Ex11Tests(unittest.TestCase):
    def test_file_matches_cpython(self):
        with tempfile.TemporaryDirectory(prefix='ail-ex11-') as directory:
            for slug, text in MATCHING.items():
                for general in (True, False):
                    name = '%s_%s.py' % (slug, 'g' if general else 'd')
                    want = cpython(directory, name, text)
                    built, exe = build(directory, name, text, general)
                    self.assertEqual(built.returncode, 0, (slug, general, built.stdout + built.stderr))
                    got = subprocess.run([str(exe)], capture_output=True, timeout=120, cwd=directory)
                    self.assertEqual(got.stdout.replace(b'\r\n', b'\n'), want[0],
                                     (slug, general, got.stderr[-800:]))
                    self.assertEqual(got.returncode, want[1], (slug, general, got.stderr[-800:]))

    def test_imported_module_file_matches_cpython(self):
        with tempfile.TemporaryDirectory(prefix='ail-ex11-mod-') as directory:
            helper = 'HERE = __file__\n\ndef path():\n    return __file__\n'
            entry = ('import helper\nfrom helper import path\n\n'
                     'print(helper.__file__)\nprint(helper.HERE)\n'
                     'print(path())\nprint(helper.path())\nprint(__file__)\n')
            for general in (True, False):
                name = 'entry_%s.py' % ('g' if general else 'd')
                (Path(directory) / 'helper.py').write_text(helper, encoding='utf-8')
                want = cpython(directory, name, entry)
                (Path(directory) / 'helper.py').write_text(helper, encoding='utf-8')
                built, exe = build(directory, name, entry, general, path=directory)
                self.assertEqual(built.returncode, 0, (general, built.stdout + built.stderr))
                got = subprocess.run([str(exe)], capture_output=True, timeout=120, cwd=directory)
                self.assertEqual(got.stdout.replace(b'\r\n', b'\n'), want[0],
                                 (general, got.stderr[-800:]))
                self.assertEqual(got.returncode, want[1], (general, got.stderr[-800:]))

    def test_entry_path_spelling_matches_cpython(self):
        with tempfile.TemporaryDirectory(prefix='ail-ex11-path-') as directory:
            root = Path(directory)
            (root / 'sub').mkdir()
            (root / 'sub' / 'rel.py').write_text('print(__file__)\n', encoding='utf-8')
            (root / 'link.py').symlink_to(root / 'sub' / 'rel.py')
            for index, spelling in enumerate(('./sub/rel.py', '../' + root.name + '/sub/rel.py', 'link.py')):
                want = subprocess.run([sys.executable, '-B', spelling], capture_output=True,
                                      timeout=120, cwd=directory,
                                      env=dict(os.environ, PYTHONUTF8='1'))
                for general in (True, False):
                    exe = root / ('exe_path_%d_%s' % (index, 'g' if general else 'd'))
                    env = dict(os.environ, AIL_NO_CACHE='1', AIL_QUIET_FALLBACK='1')
                    env.pop('AIL_NO_GENERAL', None)
                    if general:
                        env['AIL_UNIFIED_FORCE'] = '1'
                    else:
                        env.pop('AIL_UNIFIED_FORCE', None)
                    built = subprocess.run([sys.executable, '-B', CHATGPT, 'compile', spelling,
                                            '--syntax', 'python', '-o', str(exe)], cwd=directory,
                                           capture_output=True, text=True, timeout=900, env=env)
                    self.assertEqual(built.returncode, 0, (spelling, general, built.stdout + built.stderr))
                    got = subprocess.run([str(exe)], capture_output=True, timeout=120, cwd=directory)
                    self.assertEqual(got.stdout.replace(b'\r\n', b'\n'),
                                     want.stdout.replace(b'\r\n', b'\n'), (spelling, general))
                    self.assertEqual(got.returncode, want.returncode, (spelling, general))

    def test_rebinding_is_refused_by_name(self):
        with tempfile.TemporaryDirectory(prefix='ail-ex11-refuse-') as directory:
            for slug, text in REFUSED_PROGRAMS.items():
                for general in (True, False):
                    built, _ = build(directory, '%s_%s.py' % (slug, 'g' if general else 'd'),
                                     text, general)
                    output = built.stdout + built.stderr
                    self.assertNotEqual(built.returncode, 0, (slug, general, output[-1200:]))
                    self.assertIn(REFUSED, output, (slug, general, output[-1200:]))


if __name__ == '__main__':
    unittest.main()

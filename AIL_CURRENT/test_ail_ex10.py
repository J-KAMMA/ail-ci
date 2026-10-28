"""ex10: `__file__` is the source file's absolute path, as in CPython 3.12.

The general and the default build both expose `__file__` as a compile-time constant naming the
source file, so a program can report it, pass it around and locate files beside it.  A local
module's `__file__` (and `module.__file__`) names that module's own source file.
"""
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent
CHATGPT = str(ROOT / 'ail_chatgpt.py')

CASES = {
    'direct': 'print(__file__)\n',
    'path': 'from pathlib import Path\np = Path(__file__)\nprint(p.name, p.suffix, p.stem)\n',
    'alias': 'p = __file__\nq = [p, {"k": p}]\nprint(q)\nprint(p == __file__)\n',
    'fstring': 'print(f"file={__file__}")\nprint(__file__ + "!")\n',
    'argument': 'def show(x):\n    print(x)\nshow(__file__)\n',
    'attribute': 'class Box:\n    pass\nb = Box()\nb.path = __file__\nprint(b.path)\n',
}

MODULE_HELPER = 'def where():\n    return __file__\n'
MODULE_MAIN = ('import helper\n'
               'print(helper.where())\n'
               'print(helper.__file__)\n'
               'print(__file__)\n'
               'print(helper.__name__)\n')


def cpython(directory):
    done = subprocess.run([sys.executable, '-B', 'case.py'], cwd=directory, capture_output=True,
                          timeout=120, env=dict(os.environ, PYTHONUTF8='1', PYTHONWARNINGS='ignore'))
    return done.stdout.replace(b'\r\n', b'\n'), done.returncode


def build(directory, name, general):
    exe = Path(directory) / ('exe_' + name + ('_g' if general else '_d'))
    env = dict(os.environ, AIL_NO_CACHE='1', AIL_QUIET_FALLBACK='1')
    env.pop('AIL_NO_GENERAL', None)
    if general:
        env['AIL_UNIFIED_FORCE'] = '1'
    else:
        env.pop('AIL_UNIFIED_FORCE', None)
    done = subprocess.run([sys.executable, '-B', CHATGPT, 'compile', 'case.py',
                           '--syntax', 'python', '-o', exe.name], cwd=directory,
                          capture_output=True, text=True, timeout=900, env=env)
    return exe, done


class Ex10Tests(unittest.TestCase):
    def test_file_constant_matches_cpython(self):
        with tempfile.TemporaryDirectory(prefix='ail-ex10-') as directory:
            for slug, text in CASES.items():
                Path(directory, 'case.py').write_text(text, encoding='utf-8')
                want = cpython(directory)
                for general in (True, False):
                    exe, built = build(directory, '%s_%s' % (slug, 'g' if general else 'd'), general)
                    self.assertEqual(built.returncode, 0, (slug, general, built.stdout + built.stderr))
                    got = subprocess.run([str(exe)], cwd=directory, capture_output=True, timeout=120)
                    self.assertEqual(got.stdout.replace(b'\r\n', b'\n'), want[0],
                                     (slug, general, got.stderr[-800:]))
                    self.assertEqual(got.returncode, want[1], (slug, general, got.stderr[-800:]))

    def test_module_binding_is_refused(self):
        with tempfile.TemporaryDirectory(prefix='ail-ex10-bind-') as directory:
            Path(directory, 'helper.py').write_text('__file__ = "custom"\nX = __file__\n', encoding='utf-8')
            Path(directory, 'case.py').write_text(
                'import helper\nprint(helper.X)\nprint(helper.__file__)\n', encoding='utf-8')
            for general in (True, False):
                exe, built = build(directory, 'bind_%s' % ('g' if general else 'd'), general)
                self.assertEqual(built.returncode, 2, (general, built.stdout + built.stderr))
                self.assertIn('__file__', built.stderr)
                self.assertIn('write instead', built.stderr)
                self.assertNotIn('Traceback', built.stderr)

    def test_module_file_matches_cpython(self):
        with tempfile.TemporaryDirectory(prefix='ail-ex10-mod-') as directory:
            Path(directory, 'helper.py').write_text(MODULE_HELPER, encoding='utf-8')
            Path(directory, 'case.py').write_text(MODULE_MAIN, encoding='utf-8')
            want = cpython(directory)
            for general in (True, False):
                exe, built = build(directory, 'module_%s' % ('g' if general else 'd'), general)
                self.assertEqual(built.returncode, 0, (general, built.stdout + built.stderr))
                got = subprocess.run([str(exe)], cwd=directory, capture_output=True, timeout=120)
                self.assertEqual(got.stdout.replace(b'\r\n', b'\n'), want[0],
                                 (general, got.stderr[-800:]))
                self.assertEqual(got.returncode, want[1], (general, got.stderr[-800:]))


if __name__ == '__main__':
    unittest.main()

"""ex16: a definitions-only Python-syntax module with a non-array entry builds.

`language_examples/math.ail` has a module constant and a function whose first parameter is not
the file array.  The typed path built that function but then refused to synthesise its `main`;
the refusal was raised after the try that falls back to the general path, so the DEFAULT build
failed by name even though the boxed emitter builds the file as an ordinary script.  CPython
runs the same file with no output and exit 0, and the general build already did too.  Main
synthesis now sits inside that try, so the default build falls back and both builds match.

Each program is built on both builds and compared with CPython.
"""
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent
EXAMPLE = ROOT / 'language_examples' / 'math.ail'

MODULE = r'''LIMIT = 6

def sum_to(n):
    total = 0
    for i in range(n + 1):
        total += i
    return total
'''

PURE_DEFS = r'''def sum_to(n):
    return n + 1
'''


def _cpython(directory, name, text, args=()):
    src = Path(directory) / (name + '_cpython.py')
    src.write_text(text, encoding='utf-8')
    done = subprocess.run([sys.executable, '-B', str(src)] + list(args), capture_output=True,
                          timeout=120, env=dict(os.environ, PYTHONUTF8='1'))
    return done.stdout.replace(b'\r\n', b'\n'), done.returncode


def _build_and_run(directory, name, text, general, run_args=()):
    src = Path(directory) / (name + '.ail')
    src.write_text(text, encoding='utf-8')
    exe = Path(directory) / ('exe_' + name)
    env = dict(os.environ, AIL_NO_CACHE='1', AIL_QUIET_FALLBACK='1')
    env.pop('AIL_NO_GENERAL', None)
    if general:
        env['AIL_UNIFIED_FORCE'] = '1'
    else:
        env.pop('AIL_UNIFIED_FORCE', None)
    built = subprocess.run([sys.executable, '-B', str(ROOT / 'ail_chatgpt.py'), 'compile', src.name,
                            '--syntax', 'python', '-o', exe.name], cwd=directory,
                           capture_output=True, text=True, timeout=900, env=env)
    if built.returncode != 0:
        return None, (built.stdout + built.stderr)[-3000:]
    got = subprocess.run([str(exe)] + list(run_args), capture_output=True, timeout=120, cwd=directory)
    return (got.stdout.replace(b'\r\n', b'\n'), got.returncode), got.stderr.decode('utf-8', 'replace')[-1500:]


class Ex16Tests(unittest.TestCase):
    def check(self, slug, text):
        with tempfile.TemporaryDirectory(prefix='ail-ex16-') as directory:
            want, want_rc = _cpython(directory, slug, text)
            for general in (True, False):
                got, build_err = _build_and_run(directory, '%s_%s' % (slug, 'g' if general else 'd'),
                                                text, general)
                self.assertIsNotNone(got, '%s (general=%s)\n%s' % (text[:2000], general, build_err))
                self.assertEqual(got, (want, want_rc),
                                 '%s (general=%s)\n%s' % (text[:2000], general, build_err))

    def test_non_array_first_parameter_falls_back_to_the_general_path(self):
        self.check('module', MODULE)

    def test_language_example_math(self):
        self.check('math_example', EXAMPLE.read_text(encoding='utf-8'))

    def test_definitions_only_non_array_entry_still_refuses_by_name(self):
        with tempfile.TemporaryDirectory(prefix='ail-ex16-') as directory:
            src = Path(directory) / 'pure_defs.ail'
            src.write_text(PURE_DEFS, encoding='utf-8')
            env = dict(os.environ, AIL_NO_CACHE='1', AIL_QUIET_FALLBACK='1')
            env.pop('AIL_UNIFIED_FORCE', None)
            env.pop('AIL_NO_GENERAL', None)
            built = subprocess.run([sys.executable, '-B', str(ROOT / 'ail_chatgpt.py'), 'compile',
                                    src.name, '--syntax', 'python', '-o', 'pure_defs'],
                                   cwd=directory, capture_output=True, text=True, timeout=900, env=env)
            self.assertNotEqual(built.returncode, 0, built.stdout + built.stderr)
            self.assertIn('the first parameter must be the sequence read from the file',
                          built.stdout + built.stderr)


if __name__ == '__main__':
    unittest.main()

"""pre296: a local binding of a built-in name wins over the built-in call.

The pre54 reviewer recorded that a parameter (or local) named `round` was not honoured: a call
`round(x)` still used the built-in, so passing a callable printed the built-in's int where CPython
calls the parameter.  The typed path now refuses such a call by name and the general path reads
the activation's own binding, for a parameter, a local, a closure cell, and values arriving
through a list item, an attribute and a dict value.  A non-callable binding keeps CPython's
TypeError, and an unshadowed `round` is unchanged.
"""
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent

PROGRAMS = {
    'parameter': '''
def apply(round, x):
    return round(x)


print(apply(lambda v: v * 3, -5.5))
print(type(apply(lambda v: v * 3, -5.5)).__name__)
''',
    'local': '''
def f(x):
    round = lambda v: v * 3
    return round(x)


print(f(-5.5))
print(type(f(-5.5)).__name__)
''',
    'closure': '''
def outer(x):
    round = lambda v: v * 3

    def inner():
        return round(x)

    return inner()


print(outer(-5.5))
''',
    'list_item': '''
def apply(round, x):
    return round(x)


def main():
    print(apply([lambda v: v * 2][0], -5.5))


main()
''',
    'attribute': '''
class Box:
    pass


def apply(round, x):
    return round(x)


def main():
    box = Box()
    box.fn = lambda v: v - 1
    print(apply(box.fn, -5.5))


main()
''',
    'dict_value': '''
def apply(round, x):
    return round(x)


def main():
    print(apply({"fn": lambda v: v * 4}["fn"], -5.5))


main()
''',
    'noncallable': '''
def apply(round, x):
    return round(x)


try:
    apply(7, -5.5)
except Exception as e:
    print(type(e).__name__, str(e))
''',
    'unshadowed': '''
print(round(-5.5))
print(round(2.5), round(3.5), round(-0.0))
print(round(12.345, 2))
''',
}


def _run_cpython(directory, name, text):
    src = Path(directory) / (name + '_cpython.py')
    src.write_text(text, encoding='utf-8')
    done = subprocess.run([sys.executable, '-B', str(src)], capture_output=True, timeout=120,
                          env=dict(os.environ, PYTHONUTF8='1'))
    return done.stdout.replace(b'\r\n', b'\n'), done.returncode


def _build_and_run(directory, name, text, general):
    src = Path(directory) / (name + '.ail')
    src.write_text(text, encoding='utf-8')
    exe = Path(directory) / ('exe_' + name + ('_g' if general else '_d'))
    env = dict(os.environ, AIL_NO_CACHE='1', AIL_QUIET_FALLBACK='1')
    env.pop('AIL_NO_GENERAL', None)
    if general:
        env['AIL_UNIFIED_FORCE'] = '1'
    else:
        env.pop('AIL_UNIFIED_FORCE', None)
    built = subprocess.run([sys.executable, '-B', str(ROOT / 'ail_chatgpt.py'), 'compile', src.name,
                            '--syntax', 'python', '-o', exe.name], cwd=directory,
                           capture_output=True, text=True, timeout=1200, env=env)
    if built.returncode != 0:
        return None, (built.stdout + built.stderr)[-3000:]
    got = subprocess.run([str(exe)], capture_output=True, timeout=120, cwd=directory)
    return (got.stdout.replace(b'\r\n', b'\n'), got.returncode), got.stderr.decode('utf-8', 'replace')[-1500:]


class Pre296Tests(unittest.TestCase):
    def test_local_builtin_shadow_matches_cpython(self):
        with tempfile.TemporaryDirectory(prefix='ail-pre296-') as directory:
            for slug, text in PROGRAMS.items():
                want, want_rc = _run_cpython(directory, slug, text)
                for general in (True, False):
                    got, build_err = _build_and_run(directory, '%s_%s' % (slug, 'g' if general else 'd'),
                                                    text, general)
                    self.assertIsNotNone(got, '%s (general=%s)\n%s' % (slug, general, build_err))
                    self.assertEqual(got, (want, want_rc), '%s (general=%s)\n%s'
                                     % (slug, general, build_err))


if __name__ == '__main__':
    unittest.main()

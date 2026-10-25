"""A local that shadows a module-level function and is called before its assignment.

The pre141 reviewer recorded `print(side(1)); side = None` in a function: CPython makes `side`
local for the whole activation, so the call reads an unbound local and raises UnboundLocalError,
while both AIL builds called the module function. The general path now reads the local slot when
a call's name is bound in the activation; the typed path refuses the call by name and the default
build falls back to the general path. The same cause through a default expression is refused by
name too. Calls after a binding, a parameter, a loop target, and values arriving through a list
item, an attribute and a dict value all match CPython on both builds.
"""
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent

PROGRAMS = {
    'plain_shadow': '''
def side(x):
    return x


def main():
    print(side(1))
    side = None


main()
''',
    'bound_callable': '''
def side(x):
    return x


def main():
    side = lambda x: x + 1
    print(side(1))


main()
''',
    'bound_none': '''
def side(x):
    return x


def main():
    side = None
    print(side(1))


main()
''',
    'parameter': '''
def side(x):
    return x


def helper(x):
    return x * 10


def main(side):
    print(side(1))


main(helper)
''',
    'parameter_none': '''
def side(x):
    return x


def main(side):
    print(side(1))


main(None)
''',
    'for_target': '''
def side(x):
    return x


def helper(x):
    return x + 5


def main():
    for side in [helper]:
        print(side(1))


main()
''',
    'branch_unbound': '''
def side(x):
    return x


def main():
    if False:
        side = None
    print(side(1))


main()
''',
    'alias_list_item': '''
def side(x):
    return x


def helper(x):
    return x + 2


def main():
    side = [helper][0]
    print(side(1))


main()
''',
    'alias_attribute': '''
class Box:
    pass


def side(x):
    return x


def helper(x):
    return x + 3


def main():
    b = Box()
    b.fn = helper
    side = b.fn
    print(side(1))


main()
''',
    'alias_dict_value': '''
def side(x):
    return x


def helper(x):
    return x + 4


def main():
    side = {"f": helper}["f"]
    print(side(1))


main()
''',
    'normal_call': '''
def side(x):
    return x + 7


def main():
    print(side(1))


main()
''',
    'optional_not_called': '''
def side(x):
    return x


def main():
    side = None
    side = 3
    print(side)


main()
''',
}

DEFAULT_EXPRESSION = '''
def side(x):
    return x


def main():
    f = lambda v=side(1): v
    print(f())
    side = None


main()
'''


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


class Pre218Tests(unittest.TestCase):
    def test_local_shadow_matches_cpython(self):
        with tempfile.TemporaryDirectory(prefix='ail-pre218-') as directory:
            for slug, text in PROGRAMS.items():
                want, want_rc = _run_cpython(directory, slug, text)
                for general in (True, False):
                    got, build_err = _build_and_run(directory, '%s_%s' % (slug, 'g' if general else 'd'),
                                                    text, general)
                    self.assertIsNotNone(got, '%s (general=%s)\n%s' % (slug, general, build_err))
                    self.assertEqual(got, (want, want_rc), '%s (general=%s)\n%s'
                                     % (slug, general, build_err))

    def test_plain_shadow_names_unbound_local(self):
        text = PROGRAMS['plain_shadow']
        with tempfile.TemporaryDirectory(prefix='ail-pre218-') as directory:
            for general in (True, False):
                got, err = _build_and_run(directory, 'unbound_%s' % ('g' if general else 'd'),
                                          text, general)
                self.assertIsNotNone(got, err)
                self.assertEqual(got[1], 1)
                self.assertIn('UnboundLocalError', err)
                self.assertIn("cannot access local variable 'side'", err)

    def test_default_expression_shadow_is_refused_by_name(self):
        with tempfile.TemporaryDirectory(prefix='ail-pre218-') as directory:
            for general in (True, False):
                got, err = _build_and_run(directory, 'default_%s' % ('g' if general else 'd'),
                                          DEFAULT_EXPRESSION, general)
                self.assertIsNone(got, err)
                self.assertIn('side', err)
                self.assertIn('default', err)


if __name__ == '__main__':
    unittest.main()

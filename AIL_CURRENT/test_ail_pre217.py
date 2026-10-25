"""Pre-existing difference from CPython recorded by the pre141 reviewer.

A local that shadows a module-level function was not consulted by a direct call: the call
resolved to the module function for the whole activation, so calling before the local was bound
printed the module function's result instead of raising UnboundLocalError, and calling after a
non-callable assignment printed that result instead of raising TypeError.  The general path now
reads the activation's own binding, and the typed path refuses the shape by name so the default
build falls back to it.  Values reaching the call through a parameter, an alias, a list item, an
attribute, a dict value, a loop target and an except target are covered, as are int64 bounds,
float, empty str and zero arguments.
"""
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent
CLI = str(ROOT / 'ail_chatgpt.py')

PROGRAMS = {
    'unbound_before_assignment': '''
def side(x):
    return x


def main():
    print(side(1))
    side = None


main()
''',
    'none_before_call': '''
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


def twice(x):
    return x * 2


def main(side):
    print(side(1))
    side = None


main(twice)
''',
    'alias_assignment': '''
def side(x):
    return x


def twice(x):
    return x * 2


def main():
    side = twice
    print(side(1))


main()
''',
    'list_item': '''
def side(x):
    return x


def twice(x):
    return x * 2


def main():
    side = [twice][0]
    print(side(1))


main()
''',
    'attribute': '''
def side(x):
    return x


def twice(x):
    return x * 2


class Box:
    def __init__(self, fn):
        self.fn = fn


def main():
    side = Box(twice).fn
    print(side(1))


main()
''',
    'dict_value': '''
def side(x):
    return x


def twice(x):
    return x * 2


def main():
    side = {"f": twice}["f"]
    print(side(1))


main()
''',
    'loop_target': '''
def side(x):
    return x


def twice(x):
    return x * 2


def main():
    for side in [twice]:
        print(side(1))


main()
''',
    'except_target': '''
def side(x):
    return x


def twice(x):
    return x * 2


def main():
    try:
        raise ValueError("x")
    except ValueError as side:
        print(type(side).__name__)
    side = twice
    print(side(1))


main()
''',
    'int64_widths': '''
def side(x):
    return x * 3


def other(x):
    return x - 100


def main():
    side = other
    print(side(-7))
    print(side(9223372036854775807))
    print(side(0))


main()
''',
    'float_and_empty_str': '''
def side_float(x):
    return x + 0.5


def other_float(x):
    return x * 2.0


def side_str(s):
    return s + "!"


def other_str(s):
    return s + "?"


def main():
    side_float = other_float
    side_str = other_str
    print(side_float(-1.5), side_float(0.0))
    print(side_str(""), side_str("ab"))


main()
''',
    'zero_arguments': '''
def side():
    return 1


def other():
    return 2


def main(fn):
    side = fn
    print(side())


main(other)
''',
}


def _run_cpython(directory, name, text):
    src = Path(directory) / (name + '_cpython.py')
    src.write_text(text, encoding='utf-8')
    done = subprocess.run([sys.executable, '-B', str(src)], capture_output=True, timeout=120,
                          env=dict(os.environ, PYTHONUTF8='1'))
    return done.stdout.replace(b'\r\n', b'\n'), done.returncode, done.stderr


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
    built = subprocess.run([sys.executable, '-B', CLI, 'compile', src.name,
                            '--syntax', 'python', '-o', exe.name], cwd=directory,
                           capture_output=True, text=True, timeout=1200, env=env)
    if built.returncode != 0:
        return None, (built.stdout + built.stderr)[-3000:]
    got = subprocess.run([str(exe)], capture_output=True, timeout=120, cwd=directory)
    return ((got.stdout.replace(b'\r\n', b'\n'), got.returncode),
            got.stderr.decode('utf-8', 'replace')[-1500:])


class Pre217Tests(unittest.TestCase):
    def test_local_shadow_matches_cpython(self):
        with tempfile.TemporaryDirectory(prefix='ail-pre217-') as directory:
            for slug, text in PROGRAMS.items():
                want, want_rc, cpython_err = _run_cpython(directory, slug, text)
                self.assertEqual(want_rc, 1 if slug in ('unbound_before_assignment', 'none_before_call') else 0,
                                 cpython_err)
                for general in (True, False):
                    got, build_err = _build_and_run(directory, '%s_%s' % (slug, 'g' if general else 'd'),
                                                    text, general)
                    self.assertIsNotNone(got, '%s (general=%s)\n%s' % (slug, general, build_err))
                    self.assertEqual(got, (want, want_rc), '%s (general=%s)\n%s'
                                     % (slug, general, build_err))

    def test_error_messages_match_cpython(self):
        expected = {
            'unbound_before_assignment': ('UnboundLocalError',
                                          "cannot access local variable 'side'"),
            'none_before_call': ('TypeError', "'NoneType' object is not callable"),
        }
        with tempfile.TemporaryDirectory(prefix='ail-pre217-') as directory:
            for slug, needles in expected.items():
                text = PROGRAMS[slug]
                for general in (True, False):
                    got, err = _build_and_run(directory, '%s_err_%s' % (slug, 'g' if general else 'd'),
                                              text, general)
                    self.assertIsNotNone(got, err)
                    self.assertEqual(got[1], 1)
                    for needle in needles:
                        self.assertIn(needle, err, 'general=%s\n%s' % (general, err))


if __name__ == '__main__':
    unittest.main()

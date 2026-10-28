"""pre322: int() of an out-of-int64 float held in an aliased container.

The pre39 review left `r26` (a list reached through an alias) as a pre-existing difference: both
builds compiled the program and stopped at run time with `integer overflow`, while CPython prints
the exact big integer.  A container bound once to a flat list/tuple/dict literal, and aliases of
it, are now folded only while the name never escapes (no mutation, call, return or other use), so
the int() call is refused by name.  An alias that is mutated before the call stays dynamic and
matches CPython.  In-range values, nested/mutable containers and values that only arrive at run
time are unchanged.
"""
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent
CHATGPT = str(ROOT / 'ail_chatgpt.py')
HAVE_CC = shutil.which('gcc') is not None


def cpython(directory, name, text):
    src = Path(directory) / (name + '_cpython.py')
    src.write_text(text, encoding='utf-8')
    done = subprocess.run([sys.executable, '-B', str(src)], capture_output=True, timeout=120,
                          env=dict(os.environ, PYTHONUTF8='1', PYTHONWARNINGS='ignore'))
    return done.stdout.replace(b'\r\n', b'\n'), done.returncode


def build(directory, name, text, general):
    src = Path(directory) / (name + '.ail')
    src.write_text(text, encoding='utf-8')
    exe = Path(directory) / ('exe_' + name + ('_g' if general else '_d'))
    env = dict(os.environ, AIL_NO_CACHE='1', AIL_QUIET_FALLBACK='1')
    env.pop('AIL_NO_GENERAL', None)
    if general:
        env['AIL_UNIFIED_FORCE'] = '1'
    return exe, subprocess.run([sys.executable, '-B', CHATGPT, 'compile', src.name, '--syntax', 'python',
                                '-o', exe.name], cwd=directory, capture_output=True, text=True, timeout=900, env=env)


def cpython_last_line(directory, name, text):
    src = Path(directory) / (name + '_cpython_full.py')
    src.write_text(text, encoding='utf-8')
    done = subprocess.run([sys.executable, '-B', str(src)], capture_output=True, timeout=120,
                          env=dict(os.environ, PYTHONUTF8='1', PYTHONWARNINGS='ignore'))
    lines = done.stderr.decode('utf-8', 'replace').strip().splitlines()
    return done.stdout.replace(b'\r\n', b'\n'), done.returncode, (lines[-1] if lines else '')


def check_exact(test, name, text):
    """Exact ints: a value beyond int64 builds on both builds and matches CPython's stdout, exit code
    and last stderr line (the int64-era tests refused these programs by name)."""
    with tempfile.TemporaryDirectory(prefix='ail-pre322-') as directory:
        want = cpython_last_line(directory, name, text)
        for general in (True, False):
            exe, built = build(directory, name, text, general)
            test.assertEqual(built.returncode, 0, (name, general, (built.stdout + built.stderr)[-1200:]))
            got = subprocess.run([str(exe)], capture_output=True, timeout=120, cwd=directory)
            err = got.stderr.decode('utf-8', 'replace')
            test.assertEqual(got.stdout.replace(b'\r\n', b'\n'), want[0], (name, general, err[-800:]))
            test.assertEqual(got.returncode, want[1], (name, general, err[-800:]))
            if want[2]:
                test.assertIn(want[2], err, (name, general))


def check_refused(test, name, text):
    with tempfile.TemporaryDirectory(prefix='ail-pre322-') as directory:
        for general in (True, False):
            _, built = build(directory, name + ('g' if general else 'd'), text, general)
            test.assertNotEqual(built.returncode, 0, (name, general))
            message = built.stdout + built.stderr
            test.assertIn('int() of a float outside int64', message, (name, general, message[-1200:]))
            test.assertIn('big integer', message, (name, general, message[-1200:]))


def check_program(test, name, text):
    with tempfile.TemporaryDirectory(prefix='ail-pre322-') as directory:
        want = cpython(directory, name, text)
        for general in (True, False):
            exe, built = build(directory, name, text, general)
            test.assertEqual(built.returncode, 0, built.stdout + built.stderr)
            got = subprocess.run([str(exe)], capture_output=True, timeout=120, cwd=directory)
            test.assertEqual(got.stdout.replace(b'\r\n', b'\n'), want[0], (name, general, got.stderr[-800:]))
            test.assertEqual(got.returncode, want[1], (name, general, got.stderr[-800:]))


REFUSED = {
    'module_alias': '''
items = [1e300]
alias = items
print(int(alias[0]))
''',
    'function_alias': '''
def convert():
    items = [1e300]
    alias = items
    return int(alias[0])


print(convert())
''',
    'alias_chain': '''
def convert():
    items = [1e300]
    first = items
    second = first
    return int(second[0])


print(convert())
''',
    'negative_alias': '''
items = [-1e300]
alias = items
print(int(alias[0]))
''',
    'computed_index_alias': '''
items = [1e300, 2.5]
alias = items
index = 0
print(int(alias[index]))
''',
    'wrapper_alias': '''
def take(value):
    return int(value)


items = [1e300]
alias = items
print(take(alias[0]))
''',
    'dict_variable': '''
def convert():
    values = {"v": 1e300}
    alias = values
    key = "v"
    return int(alias[key])


print(convert())
''',
    'builtin_len_alias': '''
items = [1e300]
alias = items
len(alias)
print(int(alias[0]))
''',
    'builtin_print_alias': '''
items = [1e300]
alias = items
print(alias)
print(int(alias[0]))
''',
}

MATCH = {
    'in_range_alias': '''
items = [1.9, -1.9, 9.0e18]
alias = items
print(int(alias[0]), int(alias[1]), int(alias[2]))
''',
    'mutated_before_call': '''
def convert():
    items = [1e300]
    alias = items
    alias[0] = 1.5
    return int(alias[0])


print(convert())
''',
    'rebound_alias': '''
items = [1e300]
alias = items
alias = [1.5]
print(int(alias[0]))
''',
    'mutated_module_before_call': '''
items = [1e300]
alias = items
items[0] = 2.5
print(int(alias[0]))
''',
    'in_range_dict': '''
values = {"v": 1.5}
alias = values
key = "v"
print(int(alias[key]))
''',
    'empty_alias': '''
items = []
alias = items
print(len(alias))
''',
    'alias_passed_and_printed': '''
items = [1.5]
alias = items
print(alias)
print(int(alias[0]))
''',
    'shadowed_len_mutates': '''
def len(seq):
    seq[0] = 1.5
    return 7


def convert():
    items = [1e300]
    alias = items
    len(alias)
    return int(alias[0])


print(convert())
''',
    'enclosing_shadow_len_mutates': '''
def outer():
    def len(seq):
        seq[0] = 7.5
        return 0

    def convert():
        items = [-1e300]
        alias = items
        len(alias)
        return int(alias[0])

    return convert()


print(outer())
''',
    'shadowed_repr_mutates': '''
def repr(seq):
    seq[0] = 2.5
    return "x"


def convert():
    items = [1e300]
    alias = items
    repr(alias)
    return int(alias[0])


print(convert())
''',
    'shadowed_print_mutates': '''
def outer():
    def print(seq):
        seq[0] = 4.5

    def convert():
        items = [1e300]
        alias = items
        print(alias)
        return int(alias[0])

    return convert()


print(outer())
''',
}


@unittest.skipUnless(HAVE_CC, 'gcc is required')
class IntFloatAlias(unittest.TestCase):
    def test_refused_by_name(self):
        for name, text in sorted(REFUSED.items()):
            check_exact(self, 'refuse_' + name, text)

    def test_in_range_and_mutated_aliases_match_cpython(self):
        for name, text in sorted(MATCH.items()):
            check_program(self, 'match_' + name, text)


if __name__ == '__main__':
    unittest.main()

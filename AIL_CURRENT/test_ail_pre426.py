"""pre426: a function body effect applies when the function is used, not when defined.

The pre417 review recorded as pre-existing that a module-level container mutated only in a
function that is defined but never called still stopped at the later read with
``integer overflow``: the escape analysis counted the function body against its definition
statement, so the container was dropped before the read was checked.  A function body now
contributes its effects at the statement that names the function, and a function that is
never named cannot run.  A never-called mutation is therefore refused by name at compile
time, a call (direct, through an alias, or as a callback) keeps its effects in order, and
nested functions follow their enclosing function.
"""
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent

PROGRAMS = {
    'in_range_uncalled': '''
d = {"k": 7.9}
def mutate():
    d["k"] = 1.5
print(int(d.get("k")))
''',
    'called_before_read': '''
d = {"k": 1e300}
def mutate():
    d["k"] = 1.5
mutate()
print(int(d.get("k")))
''',
    'callback_before_read': '''
d = {"k": 1e300}
def mutate(x):
    d["k"] = 1.5
    return x
sorted([1, 2], key=mutate)
print(int(d.get("k")))
''',
    'alias_called_before_read': '''
d = {"k": 1e300}
def mutate():
    d["k"] = 1.5
h = mutate
h()
print(int(d.get("k")))
''',
    'nested_called_before_read': '''
d = {"k": 1e300}
def outer():
    def inner():
        d["k"] = 1.5
    inner()
outer()
print(int(d.get("k")))
''',
}

REFUSALS = {
    'uncalled': '''
d = {"k": 1e300}
def mutate():
    d["k"] = 1.5
print(int(d.get("k")))
''',
    'called_after_read': '''
d = {"k": 1e300}
def mutate():
    d["k"] = 1.5
print(int(d.get("k")))
mutate()
''',
    'alias_uncalled': '''
d = {"k": 1e300}
def mutate():
    d["k"] = 1.5
h = mutate
print(int(d.get("k")))
''',
    'alias_called_after_read': '''
d = {"k": 1e300}
def mutate():
    d["k"] = 1.5
h = mutate
print(int(d.get("k")))
h()
''',
    'nested_uncalled': '''
d = {"k": 1e300}
def outer():
    def inner():
        d["k"] = 1.5
    return inner
print(int(d.get("k")))
''',
    'read_through_argument': '''
d = {"k": 1e300}
def mutate():
    d["k"] = 1.5
def read(x):
    print(int(x.get("k")))
read(d)
''',
}


def _run_cpython(directory, name, text):
    source = Path(directory) / (name + '_cpython.py')
    source.write_text(text, encoding='utf-8')
    done = subprocess.run([sys.executable, '-B', str(source)], capture_output=True, timeout=120,
                          env=dict(os.environ, PYTHONUTF8='1'))
    return done.stdout.replace(b'\r\n', b'\n'), done.returncode


def _build(directory, name, text, general):
    source = Path(directory) / (name + '.py')
    source.write_text(text, encoding='utf-8')
    exe = Path(directory) / ('exe_' + name + ('_g' if general else '_d'))
    env = dict(os.environ, AIL_NO_CACHE='1', AIL_QUIET_FALLBACK='1')
    env.pop('AIL_NO_GENERAL', None)
    if general:
        env['AIL_UNIFIED_FORCE'] = '1'
    else:
        env.pop('AIL_UNIFIED_FORCE', None)
    return exe, subprocess.run([sys.executable, '-B', str(ROOT / 'ail_chatgpt.py'), 'compile',
                                source.name, '--syntax', 'python', '-o', exe.name], cwd=directory,
                               capture_output=True, text=True, timeout=1200, env=env)


def _build_and_run(directory, name, text, general):
    exe, built = _build(directory, name, text, general)
    if built.returncode != 0:
        return None, (built.stdout + built.stderr)[-3000:]
    got = subprocess.run([str(exe)], capture_output=True, timeout=120, cwd=directory)
    return ((got.stdout.replace(b'\r\n', b'\n'), got.returncode),
            got.stderr.decode('utf-8', 'replace')[-1500:])


class Pre426Tests(unittest.TestCase):
    def test_used_function_effects_stay_in_order(self):
        with tempfile.TemporaryDirectory(prefix='ail-pre426-') as directory:
            for slug, text in PROGRAMS.items():
                want = _run_cpython(directory, slug, text)
                for general in (True, False):
                    got, build_err = _build_and_run(
                        directory, '%s_%s' % (slug, 'g' if general else 'd'), text, general)
                    self.assertIsNotNone(got, '%s (general=%s)\n%s' % (slug, general, build_err))
                    self.assertEqual(got, want, '%s (general=%s)\n%s' % (slug, general, build_err))

    def test_unused_function_mutation_is_refused_by_name(self):
        with tempfile.TemporaryDirectory(prefix='ail-pre426-') as directory:
            for slug, text in REFUSALS.items():
                self.assertEqual(_run_cpython(directory, slug, text)[1], 0, slug)
                for general in (True, False):
                    _, built = _build(directory, '%s_%s' % (slug, 'g' if general else 'd'),
                                      text, general)
                    output = built.stdout + built.stderr
                    self.assertNotEqual(built.returncode, 0, '%s (general=%s)\n%s' %
                                        (slug, general, output))
                    self.assertIn('int() of a float outside int64', output,
                                  '%s (general=%s)\n%s' % (slug, general, output))


if __name__ == '__main__':
    unittest.main()

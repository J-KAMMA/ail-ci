"""pre417: a module-level container read before a later mutation matches CPython.

The pre402 review recorded, as pre-existing, that a module-level
``d = {"k": 1e300}; print(int(d.get("k"))); d.update({"k": 1.5})`` compiled and
then stopped with ``integer overflow`` where CPython prints the exact big
integer.  The module constant map kept only the final environment, so a
container mutated later was dropped before the earlier read was checked.  The
int() check now visits each top-level statement with the constants visible at
that statement, and a ``dict.get`` read no longer makes the container dynamic.
For the int64 era a value outside int64 read before a later mutation was refused
by name; under exact ints it builds on both builds and prints the exact integer,
and a mutation that comes first still matches CPython.  Calls that may mutate a
tracked container drop it, so a callback can only lose a refusal and never
invent one.
"""
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent

PROGRAMS = {
    'in_range_before_mutation': '''
d = {"k": 7.9}
print(int(d.get("k")))
d.update({"k": 1.5})
''',
    'mutation_before_read': '''
d = {"k": 1e300}
d.update({"k": 1.5})
print(int(d.get("k")))
''',
    'callback_alias': '''
d = {"k": 1e300}
def g(x):
    d["k"] = 1.5
    return x
h = g
sorted([1, 2], key=h)
print(int(d.get("k")))
''',
    'callback_direct': '''
d = {"k": 1e300}
def g(x):
    d["k"] = 1.5
    return x
sorted([1, 2], key=g)
print(int(d.get("k")))
''',
    'map_alias': '''
d = {"k": 1e300}
def g(x):
    d["k"] = 1.5
    return x
h = g
list(map(h, [1, 2]))
print(int(d.get("k")))
''',
    'function_mutation_before_read': '''
d = {"k": 1e300}
def setk(x):
    x["k"] = 1.5
setk(d)
print(int(d.get("k")))
''',
    'in_range_subscript_before_mutation': '''
xs = [7.9]
print(int(xs[0]))
xs[0] = 1.5
''',
    'read_without_mutation': '''
d = {"k": 7.9}
print(int(d.get("k")))
''',
    'no_conversion': '''
d = {"k": 2.5}
print(d["k"])
d.update({"k": 3.5})
''',
}

EXACT = {
    'module_dict_get': '''
d = {"k": 1e300}
print(int(d.get("k")))
d.update({"k": 1.5})
''',
    'dict_subscript': '''
d = {"k": 1e300}
print(int(d["k"]))
d["k"] = 1.5
''',
    'list_subscript': '''
xs = [1e300]
print(int(xs[0]))
xs[0] = 1.5
''',
    'alias_get': '''
d = {"k": 1e300}
e = d
print(int(e.get("k")))
d.update({"k": 1.5})
''',
    'item_mutation': '''
d = {"k": 1e300}
print(int(d.get("k")))
d["k"] = 1.5
''',
    'alias_mutates': '''
d = {"k": 1e300}
e = d
print(int(d.get("k")))
e.update({"k": 1.5})
''',
    'later_call_mutation': '''
d = {"k": 1e300}
def mut(x):
    x["k"] = 1.5
print(int(d.get("k")))
mut(d)
''',
    'argument_get': '''
d = {"k": 1e300}
def f(x):
    print(int(x.get("k")))
f(d)
d.update({"k": 1.5})
''',
    'argument_subscript': '''
d = {"k": 1e300}
def f(x):
    print(int(x["k"]))
f(d)
d.update({"k": 1.5})
''',
    'get_default': '''
d = {"j": 1}
print(int(d.get("k", 1e300)))
d.update({"j": 1.5})
''',
    'string_key_other_mutation': '''
d = {"k": 1e300}
print(int(d.get("k")))
d["other"] = 1.5
''',
    'negative_list': '''
xs = [1.5, 1e300]
print(int(xs[-1]))
xs[-1] = 2.5
''',
    'constant_key_name': '''
d = {"k": 1e300}
k = "k"
print(int(d.get(k)))
d.update({"k": 1.5})
''',
    'alias_subscript': '''
d = {"k": 1e300}
e = d
print(int(e["k"]))
d.update({"k": 1.5})
''',
    'safe_read_then_int': '''
d = {"k": 1e300}
print(d.get("k"))
print(int(d.get("k")))
d.update({"k": 1.5})
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


class Pre417Tests(unittest.TestCase):
    def test_read_before_mutation_matches_cpython(self):
        with tempfile.TemporaryDirectory(prefix='ail-pre417-') as directory:
            for slug, text in PROGRAMS.items():
                want = _run_cpython(directory, slug, text)
                for general in (True, False):
                    got, build_err = _build_and_run(
                        directory, '%s_%s' % (slug, 'g' if general else 'd'), text, general)
                    self.assertIsNotNone(got, '%s (general=%s)\n%s' % (slug, general, build_err))
                    self.assertEqual(got, want, '%s (general=%s)\n%s' % (slug, general, build_err))

    def test_out_of_int64_read_before_mutation_matches_cpython(self):
        with tempfile.TemporaryDirectory(prefix='ail-pre417-') as directory:
            for slug, text in EXACT.items():
                want = _run_cpython(directory, slug, text)
                self.assertEqual(want[1], 0, slug)
                for general in (True, False):
                    got, build_err = _build_and_run(
                        directory, '%s_%s' % (slug, 'g' if general else 'd'), text, general)
                    self.assertIsNotNone(got, '%s (general=%s)\n%s' % (slug, general, build_err))
                    self.assertEqual(got, want, '%s (general=%s)\n%s' % (slug, general, build_err))


if __name__ == '__main__':
    unittest.main()

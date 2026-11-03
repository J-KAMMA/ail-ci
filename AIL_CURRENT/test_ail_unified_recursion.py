"""Deep recursion on the general/unified path stops by name at the typed path's depth.

The general path had no recursion depth counter at all, so a self-recursive function
built with AIL_UNIFIED_FORCE=1 ran the C stack off its end (SIGSEGV) instead of raising
at AIL_MAX_RECURSION_DEPTH.  The guard now fires at the same call as the default build,
with the same bare "recursion depth exceeded" message and exit status 1.  A unified frame
is larger than a typed one, so the generated main also raises the soft stack limit for a
program with a recursive function; without that the stack would run out before call 50,000.

T1  49,999 calls succeed on the default build and with AIL_UNIFIED_FORCE=1
T2  50,001 calls stop with "recursion depth exceeded", exit 1, on both
T3  100,000 calls stop the same way on the unified path (no SIGSEGV)
T4  recursion through a local alias, a list item, a dict value or an attribute stops
    the same way on the unified path (all four used to segfault there)
"""
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent
HAVE_CC = shutil.which('gcc') is not None or shutil.which('cc') is not None

BOUNDARY = '''def f(n):
    if n <= 0:
        return 0
    return f(n - 1) + 1


print("low", f(49999))
print("high", f(50001))
'''

DEEP = '''def f(n):
    if n <= 0:
        return 0
    return f(n - 1) + 1


print(f(100000))
'''

VIA_VALUE = {
    'alias': '''def f(n):
    if n <= 0:
        return 0
    g = f
    return g(n - 1) + 1


print(f(100000))
''',
    'list': '''def f(n):
    if n <= 0:
        return 0
    fs = [f]
    return fs[0](n - 1) + 1


print(f(100000))
''',
    'dict': '''def f(n):
    if n <= 0:
        return 0
    d = {"f": f}
    return d["f"](n - 1) + 1


print(f(100000))
''',
    'attr': '''class H:
    pass


def f(n):
    if n <= 0:
        return 0
    h = H()
    h.f = f
    return h.f(n - 1) + 1


print(f(100000))
''',
}


def build(directory, text, name, unified):
    source, exe = Path(directory, name + '.py'), Path(directory, name)
    source.write_text(text, encoding='utf-8')
    env = dict(os.environ, AIL_NO_CACHE='1', AIL_QUIET_FALLBACK='1')
    for key in ('AIL_UNIFIED', 'AIL_NO_MIX', 'AIL_UNIFIED_FORCE', 'AIL_NO_GENERAL'):
        env.pop(key, None)
    if unified:
        env['AIL_UNIFIED_FORCE'] = '1'
    res = subprocess.run([sys.executable, '-B', str(ROOT / 'ail_chatgpt.py'), 'compile', source.name,
                          '--syntax', 'python', '-o', exe.name], cwd=directory,
                         capture_output=True, text=True, timeout=900, env=env)
    return res, exe


def run(exe):
    res = subprocess.run([str(exe)], capture_output=True, text=True, timeout=120)
    return res.returncode, res.stdout, res.stderr


@unittest.skipUnless(HAVE_CC, 'needs a C compiler')
class UnifiedRecursion(unittest.TestCase):
    def test_boundary_matches_the_default_build(self):
        with tempfile.TemporaryDirectory() as directory:
            results = {}
            for mode, unified in (('default', False), ('unified', True)):
                res, exe = build(directory, BOUNDARY, 'boundary_' + mode, unified)
                self.assertEqual(res.returncode, 0, res.stdout + res.stderr)
                results[mode] = run(exe)
            for mode, (code, out, err) in results.items():
                self.assertEqual((code, out), (1, 'low 49999\n'), (mode, out, err))
                self.assertEqual(err, 'recursion depth exceeded\n', (mode, err))
            self.assertEqual(results['unified'], results['default'])

    def test_100000_calls_do_not_segfault(self):
        with tempfile.TemporaryDirectory() as directory:
            res, exe = build(directory, DEEP, 'deep_unified', True)
            self.assertEqual(res.returncode, 0, res.stdout + res.stderr)
            code, out, err = run(exe)
            self.assertEqual((code, out), (1, ''), (out, err))
            self.assertEqual(err, 'recursion depth exceeded\n')


    def test_recursion_through_a_value_does_not_segfault(self):
        with tempfile.TemporaryDirectory() as directory:
            for name, text in VIA_VALUE.items():
                res, exe = build(directory, text, 'via_' + name, True)
                self.assertEqual(res.returncode, 0, name + '\n' + res.stdout + res.stderr)
                code, out, err = run(exe)
                self.assertEqual((code, out), (1, ''), (name, out, err))
                self.assertEqual(err, 'recursion depth exceeded\n', (name, err))


if __name__ == '__main__':
    unittest.main()

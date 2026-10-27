"""pre330: a wide constant pow() exponent folds before the int64 refusal.

The rbrbpre299 reviewer recorded ``pow(2, (3**100) >> 150)`` as a pre-existing difference:
both builds compiled it and then stopped with ``integer overflow`` where CPython prints the
bignum.  The pow() operand folder now uses the exact constant folder, so the exponent 361 is
known and the out-of-int64 result is refused by name on both builds.  The same fold follows a
module or function-local constant and an alias of ``pow``; an exponent that reduces to an
in-range value keeps its ordinary lowering and matches CPython.
"""
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent

REFUSED = {
    'direct': '''
print(pow(2, (3**100) >> 150))
''',
    'module_alias': '''
E = (3**100) >> 150
p = pow
print(p(2, E))
''',
    'local': '''
def f():
    e = (3**100) >> 150
    return pow(2, e)
print(f())
''',
    'boundary_from_wide': '''
print(pow(2, (1 << 63) >> 57))
''',
    'negative_base': '''
print(pow(-2, (1 << 63) >> 57))
''',
}

MATCH = {
    'in_range_wide': '''
print(pow(2, (1 << 63) >> 58))
''',
    'safe_bases': '''
print(pow(0, (3**100)>>150), pow(1, (3**100)>>150), pow(-1, (3**100)>>150))
''',
    'wide_base': '''
print(pow((3**100)>>150, 2))
''',
    'local_in_range': '''
def f():
    e = (1 << 63) >> 58
    return pow(2, e)
print(f())
''',
    'module_in_range': '''
E = (1 << 63) >> 58
print(pow(2, E))
''',
    'routes': '''
def power(b, e):
    return pow(b, e)
n = (1 << 63) >> 58
xs = [n]
class Box:
    e = n
d = {"e": n}
print(power(2, n), pow(2, xs[0]), pow(2, Box.e), pow(2, d["e"]))
''',
    'bounds': '''
print(pow(2, 62), pow(-2, 63), pow(2, True), pow(2, False))
''',
    'alias_in_range': '''
p = pow
print(p(3, (1 << 63) >> 58))
''',
}

REFUSAL = 'int64 constant expression out of range'


def build_run(directory, name, source, general):
    src = Path(directory) / (name + '.py')
    exe = Path(directory) / (name + ('_g' if general else '_d'))
    src.write_text(source, encoding='utf-8')
    env = dict(os.environ, AIL_NO_CACHE='1', AIL_QUIET_FALLBACK='1')
    env.pop('AIL_NO_GENERAL', None)
    env.pop('AIL_GENERAL', None)
    if general:
        env['AIL_UNIFIED_FORCE'] = '1'
    else:
        env.pop('AIL_UNIFIED_FORCE', None)
    built = subprocess.run([sys.executable, '-B', str(ROOT / 'ail_chatgpt.py'), 'compile', src.name,
                            '--syntax', 'python', '-o', exe.name], cwd=directory,
                           capture_output=True, text=True, timeout=900, env=env)
    if built.returncode:
        return built.returncode, b'', built.stdout + built.stderr, exe.exists()
    ran = subprocess.run([str(exe)], cwd=directory, capture_output=True, timeout=60)
    return ran.returncode, ran.stdout.replace(b'\r\n', b'\n'), built.stdout + built.stderr, exe.exists()


class Pre330(unittest.TestCase):
    def test_wide_constant_exponent_is_refused_by_name(self):
        for slug, source in REFUSED.items():
            with tempfile.TemporaryDirectory(prefix='ail-pre330-') as directory:
                for general in (False, True):
                    with self.subTest(slug=slug, general=general):
                        status, _, output, exists = build_run(directory, 'pre330_' + slug, source, general)
                        self.assertNotEqual(status, 0, output)
                        self.assertFalse(exists, 'built an executable: %s' % output[-2000:])
                        self.assertIn(REFUSAL, output)

    def test_in_range_wide_exponents_match_cpython(self):
        for slug, source in MATCH.items():
            with tempfile.TemporaryDirectory(prefix='ail-pre330-') as directory:
                want = subprocess.run([sys.executable, '-B', '-c', source], capture_output=True,
                                      timeout=60)
                self.assertEqual(want.returncode, 0, want.stderr)
                for general in (False, True):
                    with self.subTest(slug=slug, general=general):
                        status, got, output, _ = build_run(directory, 'pre330_' + slug, source, general)
                        self.assertEqual(status, 0, output)
                        self.assertEqual(got, want.stdout.replace(b'\r\n', b'\n'), output)


if __name__ == '__main__':
    unittest.main()

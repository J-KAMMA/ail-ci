"""Pre-249: negation of a statically known int64 minimum held in a variable is refused.

AIL integers are fixed width.  ``b = -(1 << 63); print(-b)`` used to compile and then stop at
run time with ``integer overflow`` on both builds, while CPython prints the bignum
``9223372036854775808``.  The compile-time unary check now follows simple assignments in module,
function and class scopes, so this construct is refused by name before C is emitted.  Values in
range, a parameter that shadows a module constant, and a value that is only known at run time keep
their previous behaviour.
"""
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent

OUT_OF_RANGE = {
    'local': '''def main():
    b = -(1 << 63)
    print(-b)


main()
''',
    'local_literal': '''def main():
    b = -9223372036854775808
    print(-b)


main()
''',
    'alias': '''def main():
    b = -(1 << 63)
    c = b
    print(-c)


main()
''',
    'reassigned': '''def main():
    b = -(1 << 63)
    b = -b
    print(b)


main()
''',
    'argument': '''def show(v):
    print(v)


def main():
    b = -(1 << 63)
    show(-b)


main()
''',
    'list_item': '''def main():
    b = -(1 << 63)
    print([-b][0])


main()
''',
    'attribute': '''class Box:
    pass


def main():
    b = -(1 << 63)
    box = Box()
    box.v = -b
    print(box.v)


main()
''',
    'dict_value': '''def main():
    b = -(1 << 63)
    print({"k": -b}["k"])


main()
''',
    'module_constant': '''MIN = -(1 << 63)


def main():
    print(-MIN)


main()
''',
    'class_scope': '''class C:
    b = -(1 << 63)
    print(-b)
''',
    'abs_module_constant': '''MIN = -(1 << 63)


def f():
    return abs(MIN)


print(f())
''',
}

IN_RANGE = '''class Box:
    pass


def show(v):
    print(v)


def main():
    a = -9223372036854775807
    show(-a)
    print([-a][0])
    box = Box()
    box.v = -a
    print(box.v)
    print({"k": -a}["k"])
    c = a
    print(-c)
    x = 1 << 62
    print(-x, -(-x))
    y = 5
    y = -y
    print(y)
    for d in (a, 5):
        print(-d)


main()
'''

PARAMETER = '''MIN = -9223372036854775808


def neg(MIN):
    return -MIN


def main():
    print(neg(3))


main()
'''

REBINDING = {
    'abs_before_rebind': '''b = 2
print(abs(b))
b = -(1 << 63)
''',
    'abs_after_rebind': '''b = -(1 << 63)
b = 2
print(abs(b))
''',
    'global_rebind': '''MIN = -(1 << 63)


def f():
    return -MIN


MIN = 1
print(f())
''',
    'global_rebind_local': '''b = -(1 << 63)


def f():
    return -b


b = 3
print(f())
''',
    'closure_rebind': '''def outer():
    b = -(1 << 63)

    def inner():
        return -b

    b = 1
    return inner()


print(outer())
''',
    'global_declaration_mutates': '''MIN = -(1 << 63)


def f():
    return -MIN


def g():
    global MIN
    MIN = 1


g()
print(f())
''',
    'walrus_statement': '''def main():
    b = -(1 << 63)
    (b := 5)
    print(-b)


main()
''',
    'walrus_test': '''def main():
    b = -(1 << 63)
    if (b := 5):
        pass
    print(-b)


main()
''',
    'walrus_abs': '''def main():
    b = -(1 << 63)
    (b := 5)
    print(abs(b))


main()
''',
    'import_alias': '''b = -(1 << 63)
import math as b
print(b.pi > 3)
''',
    'delete_then_rebind': '''b = -(1 << 63)
del b
b = 5
print(-b)
''',
    'annotated_rebind': '''b = -(1 << 63)
b: int = 5
print(-b)
''',
    'tuple_rebind': '''b = -(1 << 63)
b, c = 5, 6
print(-b)
''',
    'augmented_rebind': '''b = -(1 << 63)
b += 1
print(-b)
''',
    'match_capture': '''def main():
    b = -(1 << 63)
    match 5:
        case b:
            print(-b)


main()
''',
}


def _cpython(directory, name, text):
    src = Path(directory) / (name + '_cpython.py')
    src.write_text(text, encoding='utf-8')
    done = subprocess.run([sys.executable, '-B', str(src)], capture_output=True, timeout=120,
                          env=dict(os.environ, PYTHONUTF8='1'))
    return done.stdout.replace(b'\r\n', b'\n'), done.returncode, done.stderr


def _build(directory, name, text, general):
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
                           capture_output=True, text=True, timeout=900, env=env)
    return built, exe


def _run(directory, name, text, general):
    built, exe = _build(directory, name, text, general)
    if built.returncode != 0:
        return None, (built.stdout + built.stderr)[-3000:]
    got = subprocess.run([str(exe)], capture_output=True, timeout=120, cwd=directory)
    return (got.stdout.replace(b'\r\n', b'\n'), got.returncode), got.stderr.decode('utf-8', 'replace')[-1500:]


class Pre249Tests(unittest.TestCase):
    def refused(self, slug, text):
        with tempfile.TemporaryDirectory(prefix='ail-pre249-') as directory:
            for general in (True, False):
                name = '%s_%s' % (slug, 'g' if general else 'd')
                built, exe = _build(directory, name, text, general)
                output = built.stdout + built.stderr
                self.assertEqual(built.returncode, 2, '%s (general=%s)\n%s' % (slug, general, output[-3000:]))
                self.assertFalse(exe.exists(), '%s (general=%s) built an executable' % (slug, general))
                self.assertIn('int64 constant expression out of range', output,
                              '%s (general=%s)\n%s' % (slug, general, output[-3000:]))
                self.assertIn('9223372036854775808', output,
                              '%s (general=%s)\n%s' % (slug, general, output[-3000:]))

    def matches(self, slug, text):
        with tempfile.TemporaryDirectory(prefix='ail-pre249-') as directory:
            want, want_rc, err = _cpython(directory, slug, text)
            self.assertEqual(want_rc, 0, err)
            for general in (True, False):
                got, build_err = _run(directory, '%s_%s' % (slug, 'g' if general else 'd'),
                                      text, general)
                self.assertIsNotNone(got, '%s (general=%s)\n%s' % (slug, general, build_err))
                self.assertEqual(got, (want, want_rc), '%s (general=%s)\n%s' % (slug, general, build_err))

    def test_dynamic_negation_of_a_known_int64_minimum_is_refused(self):
        for slug, text in OUT_OF_RANGE.items():
            self.refused(slug, text)

    def test_in_range_variable_negation_matches_cpython(self):
        self.matches('in_range', IN_RANGE)

    def test_parameter_with_the_constant_name_is_not_folded(self):
        self.matches('parameter', PARAMETER)

    def test_rebinding_after_use_matches_cpython(self):
        for slug, text in REBINDING.items():
            self.matches(slug, text)


if __name__ == '__main__':
    unittest.main()

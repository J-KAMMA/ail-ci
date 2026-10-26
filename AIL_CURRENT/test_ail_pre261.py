"""pre261: a constant abs() of INT64_MIN reached through a container or attribute.

The pre214/pre215/pre248 checks fold a constant ``abs`` argument written directly or as a local
name.  A value that only reaches ``abs`` as a list item, a dict value or an attribute was still
built and then stopped with ``integer overflow`` at run time, where CPython prints the bignum.
The same exact fold now follows a literal list/tuple/dict element, a class attribute and a simple
instance attribute (``self.v`` in a class body or ``obj.v = ...`` in the same scope), so the call
is refused by name at compile time.  A mutated container, an overridden instance/class
attribute, a class name shadowed by a parameter or binding, and an ``abs`` in a default argument
keep CPython's result or the named refusal; in-range elements, float/bool elements, a parameter
or a shadowed ``abs`` keep their previous behaviour.
"""
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent
CLI = str(ROOT / 'ail_chatgpt.py')
MIN = '-(2 ** 63)'


def _local(tail):
    return 'def main():\n%s\n\n\nmain()\n' % tail


REFUSED = {
    'list_literal': _local('    print(abs([%s][0]))' % MIN),
    'list_spelling': _local('    print(abs([-9223372036854775808][0]))'),
    'list_second': _local('    print(abs([0, %s][1]))' % MIN),
    'nested_list': _local('    print(abs([[[%s]][0][0]][0]))' % MIN),
    'list_alias': _local('    xs = [%s]\n    ys = xs\n    print(abs(ys[0]))' % MIN),
    'dict_literal': _local('    print(abs({"v": %s}["v"]))' % MIN),
    'dict_alias': _local('    d = {"v": %s}\n    e = d\n    print(abs(e["v"]))' % MIN),
    'dict_last_key': _local('    print(abs({"v": -5, "v": %s}["v"]))' % MIN),
    'class_attribute': '''class Box:
    v = %s


def main():
    print(abs(Box.v))


main()
''' % MIN,
    'instance_init': '''class Box:
    def __init__(self):
        self.v = %s


def main():
    box = Box()
    print(abs(box.v))


main()
''' % MIN,
    'instance_assigned': '''class Box:
    pass


def main():
    box = Box()
    box.v = %s
    print(abs(box.v))


main()
''' % MIN,
    'module_level': 'print(abs([%s][0]))\n' % MIN,
    'module_attribute': 'class Box:\n    v = %s\n\n\nprint(abs(Box.v))\n' % MIN,
    'default_argument': 'def f(x=abs(%s)):\n    print(x)\n\n\ndef main():\n    f()\n\n\nmain()\n' % MIN,
    'nested_default_argument': '''def main():
    def f(x=abs(%s)):
        print(x)
    f()


main()
''' % MIN,
}

MATCHING = {
    'list_in_range': _local('    xs = [%s, -5, 7]\n    print(abs(xs[1]), abs(xs[2]))' % MIN),
    'list_negative_index': _local('    xs = [-8, %s]\n    print(abs(xs[0]))' % MIN),
    'tuple_in_range': _local('    print(abs((%s, -9)[1]))' % MIN),
    'dict_in_range': _local('    d = {"a": %s, "b": -5}\n    print(abs(d["b"]))' % MIN),
    'dict_missing': _local('    d = {"a": %s}\n    print("a" in d)' % MIN),
    'attributes_in_range': '''class Box:
    v = -5

    def __init__(self):
        self.w = -7


def main():
    box = Box()
    box.z = -9
    print(abs(Box.v), abs(box.w), abs(box.z))


main()
''',
    'float_bool_elements': _local('    xs = [-2.5, True, False]\n'
                                  '    d = {"f": -0.0, "b": False}\n'
                                  '    print(repr(abs(xs[0])), abs(xs[1]), abs(xs[2]), '
                                  'repr(abs(d["f"])), abs(d["b"]))'),
    'argument_in_range': _local('    def show(v):\n        print(abs(v))\n'
                                '    show(-5)\n    show(-2.5)\n'
                                '    def first(xs):\n        print(abs(xs[0]))\n'
                                '    first([-8, %s])' % MIN),
    'empty_containers': _local('    print([], {}, ())'),
    'shadowed_abs': '''def abs(x):
    return 42


def main():
    print(abs([%s][0]))


main()
''' % MIN,
    'list_mutation': _local('    xs = [%s]\n    xs[0] = 5\n    print(abs(xs[0]))' % MIN),
    'list_alias_mutation': _local('    xs = [%s]\n    ys = xs\n    ys[0] = 5\n'
                                  '    print(abs(xs[0]))' % MIN),
    'list_append_clear': _local('    xs = []\n    xs.append(%s)\n    xs.clear()\n'
                                '    xs.append(5)\n    print(abs(xs[0]))' % MIN),
    'dict_mutation': _local('    d = {"v": %s}\n    d["v"] = 5\n'
                            '    print(abs(d["v"]))' % MIN),
    'loop_mutation': _local('    xs = [%s]\n    for _ in range(1):\n'
                            '        xs[0] = 5\n    print(abs(xs[0]))' % MIN),
    'instance_alias_override': '''class Box:
    v = %s


def main():
    b = Box()
    b2 = b
    b2.v = 5
    print(abs(b.v))


main()
''' % MIN,
    'instance_method_never_called': '''class Box:
    v = 5

    def set(self):
        self.v = %s


def main():
    b = Box()
    print(abs(b.v))


main()
''' % MIN,
    'instance_method_called': '''class Box:
    v = %s

    def set(self):
        self.v = 5


def main():
    b = Box()
    b.set()
    print(abs(b.v))


main()
''' % MIN,
    'instance_init_override': '''class Box:
    def __init__(self):
        self.v = %s


def main():
    b = Box()
    b.v = 5
    print(abs(b.v))


main()
''' % MIN,
    'instance_conditional_override': '''class Box:
    v = %s

    def __init__(self, flag):
        if flag:
            self.v = 5


def main():
    b = Box(True)
    print(abs(b.v))


main()
''' % MIN,
    'instance_override_via_function': '''class Box:
    v = %s


def override(box):
    box.v = 5


def main():
    b = Box()
    override(b)
    print(abs(b.v))


main()
''' % MIN,
    'shadowed_class_parameter': '''class C:
    v = %s


class D:
    v = 5


def show(C):
    print(abs(C.v))


def main():
    show(D())


main()
''' % MIN,
    'shadowed_class_assignment': '''class C:
    v = %s


class D:
    v = 5


def make():
    return D()


C = make()


def main():
    print(abs(C.v))


main()
''' % MIN,
}


def _cpython(directory, name, text):
    src = Path(directory) / (name + '_cpython.py')
    src.write_text(text, encoding='utf-8')
    return subprocess.run([sys.executable, '-B', str(src)], capture_output=True, text=True,
                          timeout=120, env=dict(os.environ, PYTHONUTF8='1'))


def _build(directory, name, text, general):
    src = Path(directory) / (name + '.py')
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
                           capture_output=True, text=True, timeout=900, env=env)
    return built, exe


def _run(directory, name, text, general):
    built, exe = _build(directory, name, text, general)
    if built.returncode != 0:
        return None, built.stdout + built.stderr
    return subprocess.run([str(exe)], cwd=directory, capture_output=True, text=True,
                          timeout=120), ''


class Pre261Tests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix='ail-pre261-')
        self.dir = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def test_container_and_attribute_abs_outside_int64_is_refused(self):
        for label, text in REFUSED.items():
            for general in (False, True):
                with self.subTest(label + ('_g' if general else '_d')):
                    built, exe = _build(self.dir, '%s_%s' % (label, 'g' if general else 'd'),
                                        text, general)
                    output = built.stdout + built.stderr
                    self.assertEqual(built.returncode, 2, '%s\n%s' % (label, output[-3000:]))
                    self.assertFalse(exe.exists(), label)
                    self.assertIn('int64 constant expression out of range', output,
                                  '%s\n%s' % (label, output[-3000:]))
                    self.assertIn('9223372036854775808', output,
                                  '%s\n%s' % (label, output[-3000:]))

    def test_in_range_container_and_attribute_abs_matches_cpython(self):
        for label, text in MATCHING.items():
            want = _cpython(self.dir, label, text)
            self.assertEqual(want.returncode, 0, label + '\n' + want.stderr[-3000:])
            for general in (False, True):
                with self.subTest(label + ('_g' if general else '_d')):
                    got, build_err = _run(self.dir, '%s_%s' % (label, 'g' if general else 'd'),
                                          text, general)
                    self.assertIsNotNone(got, '%s\n%s' % (label, build_err[-3000:]))
                    self.assertEqual(got.stdout, want.stdout,
                                     '%s\n%s' % (label, build_err[-3000:]))
                    self.assertEqual(got.returncode, want.returncode, label)


if __name__ == '__main__':
    unittest.main()

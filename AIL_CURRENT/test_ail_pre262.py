"""Pre-262: ``abs()`` of the int64 minimum reached through a container, attribute or argument.

AIL integers are 64-bit.  A value such as ``-(2 ** 63)`` fits, but its absolute value is 2**63,
which int64 cannot hold, so both builds used to stop at run time with ``integer overflow`` while
CPython prints the bignum.  A constant value is now followed through list/tuple items, dict
values, instance attributes (including ``__init__``), aliases, literal loop targets and function
arguments, and the ``abs`` call is refused at compile time with the pre214 wording.  In-range
values keep matching CPython, including when the same container also holds the minimum at an
unused index.
"""
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent


REFUSED = {
    'list_item': '''def main():
    xs = [-(2 ** 63)]
    print(abs(xs[0]))


main()
''',
    'list_literal': '''def main():
    print(abs([-(2 ** 63)][0]))


main()
''',
    'list_alias': '''def main():
    xs = [-(2 ** 63)]
    ys = xs
    print(abs(ys[0]))


main()
''',
    'tuple_item': '''def main():
    xs = (-(2 ** 63),)
    print(abs(xs[0]))


main()
''',
    'dict_value': '''def main():
    d = {"v": -(2 ** 63)}
    print(abs(d["v"]))


main()
''',
    'dict_literal': '''def main():
    print(abs({"v": -(2 ** 63)}["v"]))


main()
''',
    'attribute': '''class Box:
    pass


def main():
    box = Box()
    box.value = -(2 ** 63)
    print(abs(box.value))


main()
''',
    'attribute_init': '''class Box:
    def __init__(self):
        self.value = -(2 ** 63)


def main():
    box = Box()
    print(abs(box.value))


main()
''',
    'argument': '''def show(value):
    print(abs(value))


def main():
    show(-(2 ** 63))


main()
''',
    'list_argument': '''def show(values):
    print(abs(values[0]))


def main():
    show([-(2 ** 63)])


main()
''',
    'dict_argument': '''def show(values):
    print(abs(values["v"]))


def main():
    show({"v": -(2 ** 63)})


main()
''',
    'object_argument': '''class Box:
    def __init__(self):
        self.value = -(2 ** 63)


def show(box):
    print(abs(box.value))


def main():
    show(Box())


main()
''',
    'loop_target': '''def main():
    for value in [-(2 ** 63)]:
        print(abs(value))


main()
''',
}

MATCHING = {
    'in_range_containers': '''class Box:
    def __init__(self, value):
        self.value = value


def show(value):
    print(abs(value))


def main():
    values = [-8, 0, 9, -(2 ** 63)]
    print(abs(values[0]), abs(values[1]), abs(values[2]))
    print(abs({"v": -10}["v"]))
    print(abs(Box(-11).value))
    show(-12)
    show(13)
    for value in [-14, 15]:
        print(abs(value))


main()
''',
    'boundaries': '''def main():
    xs = [-(2 ** 63), -(2 ** 63) + 1, 9223372036854775807]
    print(abs(xs[1]), abs(xs[2]))
    print(abs(-5), abs(0), abs(5))
    print(repr(abs(-0.0)), repr(abs(-2.5)))


main()
''',
    'mutation_and_reassignment': '''class Box:
    def __init__(self, value):
        self.value = value

    def reset(self):
        self.value = 5


def change(values):
    values[0] = 5


def show(value):
    value = 5
    print(abs(value))


def mutate(box):
    box.value = 5
    print(abs(box.value))


def method(box):
    box.reset()
    print(abs(box.value))


def main():
    xs = [-(2 ** 63)]
    xs[0] = 5
    print(abs(xs[0]))
    xs = [-(2 ** 63)]
    ys = xs
    ys[0] = 5
    print(abs(xs[0]))
    d = {"v": -(2 ** 63)}
    d["v"] = 5
    print(abs(d["v"]))
    xs = [-(2 ** 63)]
    xs.clear()
    xs.append(7)
    print(abs(xs[0]))
    show(-(2 ** 63))
    mutate(Box(-(2 ** 63)))
    method(Box(-(2 ** 63)))
    for value in [-(2 ** 63)]:
        value = 5
        print(abs(value))
    value = -(2 ** 63)
    value += 1
    print(abs(value))
    xs = [-(2 ** 63)]
    if True:
        xs[0] = 5
    print(abs(xs[0]))
    xs = [-(2 ** 63)]
    change(xs)
    print(abs(xs[0]))


main()
''',
    'unused_minimum': '''MIN = -(2 ** 63)


def main():
    print(abs(-5))
    print(abs([-6][0]))
    print(abs({"v": -7}["v"]))


main()
''',
    'shadowed': '''def abs(value):
    return 42


def main():
    print(abs(-(2 ** 63)))


main()
''',
}


def _cpython(directory, name, text):
    source = Path(directory) / (name + '_cpython.py')
    source.write_text(text, encoding='utf-8')
    done = subprocess.run([sys.executable, '-B', str(source)], capture_output=True, timeout=120,
                          env=dict(os.environ, PYTHONUTF8='1'))
    return done.stdout.replace(b'\r\n', b'\n'), done.returncode, done.stderr


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
    built = subprocess.run([sys.executable, '-B', str(ROOT / 'ail_chatgpt.py'), 'compile',
                            source.name, '--syntax', 'python', '-o', exe.name],
                           cwd=directory, capture_output=True, text=True, timeout=900, env=env)
    return built, exe


def _run(directory, name, text, general):
    built, exe = _build(directory, name, text, general)
    if built.returncode != 0:
        return None, (built.stdout + built.stderr)[-3000:]
    done = subprocess.run([str(exe)], capture_output=True, timeout=120, cwd=directory)
    return (done.stdout.replace(b'\r\n', b'\n'), done.returncode), done.stderr.decode(
        'utf-8', 'replace')[-1500:]


class Pre262Tests(unittest.TestCase):
    def refused(self, slug, text):
        with tempfile.TemporaryDirectory(prefix='ail-pre262-') as directory:
            for general in (True, False):
                name = '%s_%s' % (slug, 'g' if general else 'd')
                built, exe = _build(directory, name, text, general)
                output = built.stdout + built.stderr
                self.assertEqual(built.returncode, 2,
                                 '%s (general=%s)\n%s' % (slug, general, output[-3000:]))
                self.assertFalse(exe.exists(),
                                 '%s (general=%s) built an executable' % (slug, general))
                self.assertIn('int64 constant expression out of range', output,
                              '%s (general=%s)\n%s' % (slug, general, output[-3000:]))
                self.assertIn('9223372036854775808', output,
                              '%s (general=%s)\n%s' % (slug, general, output[-3000:]))

    def matches(self, slug, text):
        with tempfile.TemporaryDirectory(prefix='ail-pre262-') as directory:
            want, want_rc, err = _cpython(directory, slug, text)
            self.assertEqual(want_rc, 0, err)
            for general in (True, False):
                got, build_err = _run(directory, '%s_%s' % (slug, 'g' if general else 'd'),
                                      text, general)
                self.assertIsNotNone(got, '%s (general=%s)\n%s' % (slug, general, build_err))
                self.assertEqual(got, (want, want_rc),
                                 '%s (general=%s)\n%s' % (slug, general, build_err))

    def test_container_abs_of_int64_minimum_is_refused(self):
        for slug, text in REFUSED.items():
            self.refused(slug, text)

    def test_in_range_absolutes_still_match_cpython(self):
        for slug, text in MATCHING.items():
            self.matches(slug, text)


if __name__ == '__main__':
    unittest.main()

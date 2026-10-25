"""Pre-247: a constant ``abs(MIN)`` stored in a container is refused by name.

The pre-214 check found the int64 minimum only where the ``abs`` call's own argument folded.
A value first stored in an attribute, list item or dict value reached ``abs`` at run time and
stopped with ``integer overflow``, while CPython prints the bignum.  The same straight-line
constant tracking now follows those containers (including an attribute set by ``__init__`` and
an alias), and both builds refuse the construct by name.  In-range container values and a
reassignment before the call still match CPython.
"""
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent

OUT_OF_RANGE = {
    'attribute_class': '''class Box:
    v = -(1 << 63)


def main():
    print(abs(Box.v))


main()
''',
    'attribute_instance': '''class Box:
    pass


def main():
    b = Box()
    b.v = -(1 << 63)
    print(abs(b.v))


main()
''',
    'attribute_init': '''class Box:
    def __init__(self):
        self.v = -(1 << 63)


def main():
    b = Box()
    print(abs(b.v))


main()
''',
    'attribute_init_argument': '''class Box:
    def __init__(self, v):
        self.v = v


def main():
    b = Box(-(1 << 63))
    print(abs(b.v))


main()
''',
    'attribute_alias': '''class Box:
    pass


def main():
    b = Box()
    b.v = -(1 << 63)
    c = b
    print(abs(c.v))


main()
''',
    'list_item': '''def main():
    xs = [-(1 << 63)]
    print(abs(xs[0]))


main()
''',
    'dict_value': '''def main():
    d = {"k": -(1 << 63)}
    print(abs(d["k"]))


main()
''',
    'nested_expression': '''class Box:
    pass


def main():
    b = Box()
    b.v = -(2 ** 63)
    print(abs(b.v + 0))


main()
''',
}

MATCHES = {
    'in_range_containers': '''class Box:
    pass


def main():
    b = Box()
    b.v = -9223372036854775807
    xs = [-(1 << 63) + 1, -0]
    d = {"k": -5}
    print(abs(b.v), abs(xs[0]), abs(xs[1]), abs(d["k"]))


main()
''',
    'reassigned_attribute': '''class Box:
    pass


def main():
    b = Box()
    b.v = -(1 << 63)
    b.v = 5
    print(abs(b.v))


main()
''',
    'mutated_attribute': '''class Box:
    def reset(self):
        self.v = 5


def main():
    b = Box()
    b.v = -(1 << 63)
    b.reset()
    print(abs(b.v))


main()
''',
    'branch_reassignment': '''class Box:
    pass


def main():
    b = Box()
    b.v = -(1 << 63)
    if int("1"):
        b.v = 5
    print(abs(b.v))


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


class Pre247Tests(unittest.TestCase):
    def refused(self, slug, text):
        with tempfile.TemporaryDirectory(prefix='ail-pre247-') as directory:
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
        with tempfile.TemporaryDirectory(prefix='ail-pre247-') as directory:
            want, want_rc, err = _cpython(directory, slug, text)
            self.assertEqual(want_rc, 0, err)
            for general in (True, False):
                got, build_err = _run(directory, '%s_%s' % (slug, 'g' if general else 'd'),
                                      text, general)
                self.assertIsNotNone(got, '%s (general=%s)\n%s' % (slug, general, build_err))
                self.assertEqual(got, (want, want_rc), '%s (general=%s)\n%s' % (slug, general, build_err))

    def test_container_constants_are_refused(self):
        for slug, text in OUT_OF_RANGE.items():
            self.refused(slug, text)

    def test_in_range_and_reassigned_container_constants_match_cpython(self):
        for slug, text in MATCHES.items():
            self.matches(slug, text)


if __name__ == '__main__':
    unittest.main()

"""Pre-248: ``abs()`` of a local variable holding the int64 minimum is refused by name.

AIL integers are fixed width.  A local binding such as ``x = -(2 ** 63)`` is in range, but
``abs(x)`` is 2**63, which int64 cannot hold, so both builds used to stop at run time with
``integer overflow`` while CPython prints the bignum.  The local constant is now followed into
``abs`` and the call is refused at compile time with the pre214 wording.  In-range locals,
locals overwritten before the call, float/bool locals and a local that shadows a module
constant still match CPython.
"""
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def _local(value, tail):
    return 'def main():\n    x = %s\n%s\n\n\nmain()\n' % (value, tail)


REFUSED = {
    'direct': _local('-(2 ** 63)', '    print(abs(x))'),
    'shift': _local('-(1 << 63)', '    print(abs(x))'),
    'module_constant': '''MIN = -(2 ** 63)


def main():
    x = MIN
    print(abs(x))


main()
''',
    'alias': _local('-(2 ** 63)', '    y = x\n    print(abs(y))'),
    'annassign': '''def main():
    x: int = -(2 ** 63)
    print(abs(x))


main()
''',
    'argument': '''def show(v):
    print(v)


def main():
    x = -(2 ** 63)
    show(abs(x))


main()
''',
    'list_item': _local('-(2 ** 63)', '    print([abs(x)][0])'),
    'attribute': '''class Box:
    pass


def main():
    x = -(2 ** 63)
    box = Box()
    box.v = abs(x)
    print(box.v)


main()
''',
    'dict_value': _local('-(2 ** 63)', '    print({"v": abs(x)}["v"])'),
}

MATCHING = {
    'in_range': '''def main():
    a = -(2 ** 62)
    b = -(2 ** 63 - 1)
    c = -5
    d = 0
    print(abs(a), abs(b), abs(c), abs(d))


main()
''',
    'overwritten': _local('-(2 ** 63)', '    x = 5\n    print(abs(x))'),
    'float_bool': '''def main():
    a = -2.5
    b = -0.0
    c = True
    print(repr(abs(a)), repr(abs(b)), abs(c))


main()
''',
    'shadowed_module': '''MIN = -(2 ** 63)


def main():
    MIN = 5
    print(abs(MIN))


main()
''',
    'unused_local': _local('-(2 ** 63)', '    print(7)'),
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


class Pre248Tests(unittest.TestCase):
    def refused(self, slug, text):
        with tempfile.TemporaryDirectory(prefix='ail-pre248-') as directory:
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
        with tempfile.TemporaryDirectory(prefix='ail-pre248-') as directory:
            want, want_rc, err = _cpython(directory, slug, text)
            self.assertEqual(want_rc, 0, err)
            for general in (True, False):
                got, build_err = _run(directory, '%s_%s' % (slug, 'g' if general else 'd'),
                                      text, general)
                self.assertIsNotNone(got, '%s (general=%s)\n%s' % (slug, general, build_err))
                self.assertEqual(got, (want, want_rc), '%s (general=%s)\n%s' % (slug, general, build_err))

    def test_local_abs_of_int64_minimum_is_refused(self):
        for slug, text in REFUSED.items():
            self.refused(slug, text)

    def test_matching_local_absolutes(self):
        for slug, text in MATCHING.items():
            self.matches(slug, text)


if __name__ == '__main__':
    unittest.main()

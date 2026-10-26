"""Pre-274: a zero base raised to a negative power names CPython's ZeroDivisionError.

The review of job rbpre69 recorded that ``0 ** -1`` still stopped with
``division by zero`` on the default build where CPython raises
``ZeroDivisionError: 0.0 cannot be raised to a negative power``.  The typed
float-power helper treated every non-finite zero-base result as a division by
zero, and the integer helper used its generic negative-exponent trap.  Both now
name CPython's message (and stay catchable), while a zero base with ``-inf``,
``inf`` or ``nan`` keeps its finite/infinite result and a non-zero variable
negative exponent keeps its documented trap.
"""
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent
MESSAGE = '0.0 cannot be raised to a negative power'

UNCAUGHT = {
    'literal': '''def main():
    print(0 ** -1)


main()
''',
    'float_base': '''def main():
    print(0.0 ** -1)


main()
''',
    'float_exp': '''def main():
    print(0 ** -1.0)


main()
''',
    'int_var': '''def main():
    n = -1
    print(0 ** n)


main()
''',
    'float_var': '''def main():
    z = 0.0
    n = -2.0
    print(z ** n)


main()
''',
    'negative_zero': '''def main():
    z = -0.0
    print(z ** -1)


main()
''',
    'half': '''def main():
    print(0 ** -0.5)


main()
''',
    'argument': '''def power(b, e):
    return b ** e


def main():
    print(power(0, -1))


main()
''',
    'list_item': '''def main():
    pair = [0, -1]
    print(pair[0] ** pair[1])


main()
''',
    'attribute': '''class Box:
    pass


def main():
    box = Box()
    box.base = 0
    box.exp = -1
    print(box.base ** box.exp)


main()
''',
    'dict_value': '''def main():
    values = {"base": 0, "exp": -1}
    print(values["base"] ** values["exp"])


main()
''',
}

CAUGHT = r'''class Box:
    pass


def main():
    values = {"base": 0.0, "exp": -4.0}
    box = Box()
    box.base = 0
    box.exp = -2
    pair = [0, -3]
    cases = (
        (0, -1),
        (0.0, -2.0),
        (0, -1.0),
        (-0.0, -3),
        (pair[0], pair[1]),
        (values["base"], values["exp"]),
        (box.base, box.exp),
    )
    for base, exp in cases:
        try:
            print(base ** exp)
        except ZeroDivisionError as exc:
            print(type(exc).__name__)
            print(exc)


main()
'''

EDGES = r'''def main():
    print(0 ** -0.0)
    print(0 ** 0)
    print(0 ** 1)
    print(0 ** 2)
    print(0.0 ** 0)
    print(0.0 ** 2.5)
    print((-0.0) ** 2)
    print((-0.0) ** 3)
    print(0 ** float("-inf"))
    print(0 ** float("inf"))
    print(0.0 ** float("-inf"))
    print(0 ** float("nan"))


main()
'''


def _cpython(directory, name, text):
    src = Path(directory) / (name + '_cpython.py')
    src.write_text(text, encoding='utf-8')
    done = subprocess.run([sys.executable, '-B', str(src)], capture_output=True, timeout=120,
                          env=dict(os.environ, PYTHONUTF8='1'))
    return done.stdout.replace(b'\r\n', b'\n'), done.returncode, done.stderr


def _build(directory, name, text, general, v1=False):
    src = Path(directory) / (name + '.ail')
    src.write_text(text, encoding='utf-8')
    exe = Path(directory) / ('exe_' + name + ('_g' if general else '_d'))
    env = dict(os.environ, AIL_NO_CACHE='1', AIL_QUIET_FALLBACK='1')
    env.pop('AIL_NO_GENERAL', None)
    env.pop('AIL_GENERAL', None)
    if v1:
        env['AIL_GENERAL'] = 'v1'
    elif general:
        env['AIL_UNIFIED_FORCE'] = '1'
    else:
        env.pop('AIL_UNIFIED_FORCE', None)
    built = subprocess.run([sys.executable, '-B', str(ROOT / 'ail_chatgpt.py'), 'compile', src.name,
                            '--syntax', 'python', '-o', exe.name], cwd=directory,
                           capture_output=True, text=True, timeout=900, env=env)
    return built, exe


def _run(directory, name, text, general, v1=False):
    built, exe = _build(directory, name, text, general, v1)
    if built.returncode != 0:
        return None, (built.stdout + built.stderr)[-3000:]
    got = subprocess.run([str(exe)], capture_output=True, timeout=120, cwd=directory)
    return ((got.stdout.replace(b'\r\n', b'\n'), got.returncode),
            got.stderr.decode('utf-8', 'replace')[-3000:])


def _last_message(stderr):
    lines = [line for line in stderr.splitlines() if line.strip()]
    last = lines[-1] if lines else ''
    if last.startswith('ZeroDivisionError: '):
        last = last[len('ZeroDivisionError: '):]
    return last


class Pre274Tests(unittest.TestCase):
    def test_zero_base_negative_power_message(self):
        for slug, text in UNCAUGHT.items():
            with self.subTest(slug):
                with tempfile.TemporaryDirectory(prefix='ail-pre274-') as directory:
                    want, want_rc, want_err = _cpython(directory, slug, text)
                    self.assertEqual(want_rc, 1, want_err)
                    for general in (True, False):
                        label = '%s_%s' % (slug, 'g' if general else 'd')
                        got, err = _run(directory, label, text, general)
                        self.assertIsNotNone(got, '%s (general=%s)\n%s' % (slug, general, err))
                        self.assertEqual(got, (want, want_rc),
                                         '%s (general=%s)\n%s' % (slug, general, err))
                        self.assertEqual(_last_message(err), MESSAGE,
                                         '%s (general=%s)\n%s' % (slug, general, err))

    def test_caught_message_and_type(self):
        with tempfile.TemporaryDirectory(prefix='ail-pre274-') as directory:
            want, want_rc, want_err = _cpython(directory, 'caught', CAUGHT)
            self.assertEqual(want_rc, 0, want_err)
            for general in (True, False):
                label = 'caught_%s' % ('g' if general else 'd')
                got, err = _run(directory, label, CAUGHT, general)
                self.assertIsNotNone(got, 'caught (general=%s)\n%s' % (general, err))
                self.assertEqual(got, (want, want_rc),
                                 'caught (general=%s)\n%s' % (general, err))

    def test_zero_base_other_exponents(self):
        with tempfile.TemporaryDirectory(prefix='ail-pre274-') as directory:
            want, want_rc, want_err = _cpython(directory, 'edges', EDGES)
            self.assertEqual(want_rc, 0, want_err)
            for general in (True, False):
                label = 'edges_%s' % ('g' if general else 'd')
                got, err = _run(directory, label, EDGES, general)
                self.assertIsNotNone(got, 'edges (general=%s)\n%s' % (general, err))
                self.assertEqual(got, (want, want_rc),
                                 'edges (general=%s)\n%s' % (general, err))

    def test_v1_zero_base_negative_power_message(self):
        with tempfile.TemporaryDirectory(prefix='ail-pre274-') as directory:
            text = UNCAUGHT['literal']
            want, want_rc, want_err = _cpython(directory, 'v1', text)
            self.assertEqual(want_rc, 1, want_err)
            got, err = _run(directory, 'v1', text, False, v1=True)
            self.assertIsNotNone(got, 'v1\n%s' % err)
            self.assertEqual(got, (want, want_rc), 'v1\n%s' % err)
            self.assertEqual(_last_message(err), MESSAGE, 'v1\n%s' % err)


if __name__ == '__main__':
    unittest.main()

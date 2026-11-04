"""fz226: a constant integer subtraction beyond int64 is refused by name.

The daily fuzzer (seed 2076102845) printed `((3 - -9223372036854775807) ** 1)`.  CPython's int is
unbounded and prints `9223372036854775810`; on this tree the int64 build already refuses the
constant expression at compile time (`int64 constant out of range`), so the seed no longer shows
the silent DIFF.  This module pins that refusal, in-range neighbours, and the routed values (an
argument, a list item, an attribute and a dict value) that cannot be folded: they keep the
declared int64 overflow contract (exit 1, `integer overflow`, stdout a prefix of CPython's), and
with `--exact-int` they match CPython.
"""
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent

MODES = (
    ('default', {}),
    ('default_ir', {'AIL_IR': '1'}),
)
EXACT_MODES = tuple((name, dict(extra, AIL_EXACT_INT='1')) for name, extra in MODES)

MINIMAL = '''\
print(((3 - -9223372036854775807) ** 1))
'''

WIDE_CONSTANTS = (
    ('subtraction', 'print(3 - -9223372036854775807)\n'),
    ('addition', 'print(9223372036854775807 + 3)\n'),
    ('negation', 'print(-(-9223372036854775807 - 3))\n'),
    ('multiplication', 'print(4611686018427387904 * 2 + 2)\n'),
)

IN_RANGE = '''\
print(3 - -9223372036854775800)
print(9223372036854775807 - 9223372036854775807)
print(-9223372036854775807 + 0)
print((-2) ** 62)
'''

ROUTES = (
    ('argument', '''\
def take(x: int) -> None:
    print(((3 - x) ** 1))


print("before")
take(-9223372036854775807)
'''),
    ('list_item', '''\
xs: list[int] = [-9223372036854775807]
print("before")
print(((3 - xs[0]) ** 1))
'''),
    ('attribute', '''\
class Holder:
    def __init__(self, v: int) -> None:
        self.v = v


h: Holder = Holder(-9223372036854775807)
print("before")
print(((3 - h.v) ** 1))
'''),
    ('dict_value', '''\
d: dict[str, int] = {"v": -9223372036854775807}
print("before")
print(((3 - d["v"]) ** 1))
'''),
    ('try_finally_argument', '''\
def take(x: int) -> None:
    print(((3 - x) ** 1))


print("before")
try:
    take(-9223372036854775807)
finally:
    print(287)
print("after")
'''),
)


def _cpython(directory, name, text):
    src = Path(directory) / (name + '_cpython.py')
    src.write_text(text, encoding='utf-8')
    done = subprocess.run([sys.executable, '-B', str(src)], capture_output=True, timeout=120,
                          env=dict(os.environ, PYTHONUTF8='1'))
    return done.stdout.replace(b'\r\n', b'\n'), done.returncode


def _build_and_run(directory, name, text, extra):
    src = Path(directory) / (name + '.ail')
    src.write_text(text, encoding='utf-8')
    exe = Path(directory) / ('exe_' + name)
    env = dict(os.environ, AIL_NO_CACHE='1', AIL_QUIET_FALLBACK='1')
    for key in ('AIL_NO_GENERAL', 'AIL_UNIFIED_FORCE', 'AIL_IR', 'AIL_EXACT_INT'):
        env.pop(key, None)
    env.update(extra)
    built = subprocess.run([sys.executable, '-B', str(ROOT / 'ail_chatgpt.py'), 'compile', src.name,
                            '--syntax', 'python', '-o', exe.name], cwd=directory,
                           capture_output=True, text=True, timeout=900, env=env)
    if built.returncode != 0:
        return None, built.returncode, (built.stdout + built.stderr)
    got = subprocess.run([str(exe)], capture_output=True, timeout=120, cwd=directory)
    return got, built.returncode, ''


class Fz226Tests(unittest.TestCase):
    def refused(self, name, text):
        with tempfile.TemporaryDirectory(prefix='ail-fz226-') as directory:
            for mode, extra in MODES:
                with self.subTest(name=name, mode=mode):
                    got, build_rc, err = _build_and_run(directory, name + '_' + mode, text, extra)
                    self.assertIsNone(got, (name, mode, err[-3000:]))
                    self.assertNotEqual(build_rc, 0, (name, mode))
                    self.assertIn('int64 constant', err, (name, mode))
                    self.assertIn('out of range', err, (name, mode))
                    self.assertNotIn('Traceback', err, (name, mode))

    def same(self, name, text, modes=MODES):
        with tempfile.TemporaryDirectory(prefix='ail-fz226-') as directory:
            want, want_rc = _cpython(directory, name, text)
            for mode, extra in modes:
                with self.subTest(name=name, mode=mode):
                    got, build_rc, err = _build_and_run(directory, name + '_' + mode, text, extra)
                    self.assertIsNotNone(got, '%s %s\n%s' % (name, mode, err[-3000:]))
                    self.assertEqual(build_rc, 0, err[-3000:])
                    self.assertEqual(got.stdout.replace(b'\r\n', b'\n'), want, (name, mode))
                    self.assertEqual(got.returncode, want_rc, (name, mode, got.stderr[-1500:]))

    def wide(self, name, text, modes=MODES):
        with tempfile.TemporaryDirectory(prefix='ail-fz226-') as directory:
            want, want_rc = _cpython(directory, name, text)
            for mode, extra in modes:
                with self.subTest(name=name, mode=mode):
                    got, build_rc, err = _build_and_run(directory, name + '_' + mode, text, extra)
                    if got is None:
                        self.assertIn('int64 constant', err, (name, mode, err[-3000:]))
                        self.assertIn('out of range', err, (name, mode, err[-3000:]))
                        continue
                    self.assertEqual(build_rc, 0, err[-3000:])
                    out = got.stdout.replace(b'\r\n', b'\n')
                    err_text = got.stderr.decode('utf-8', 'replace')
                    if (out, got.returncode) == (want, want_rc):
                        continue
                    self.assertEqual(got.returncode, 1, (name, mode, err_text[-1500:]))
                    self.assertIn('integer overflow', err_text, (name, mode))
                    self.assertTrue(want.startswith(out), (name, mode, out[-500:], want[-500:]))

    def test_minimized_fuzzer_seed_is_refused_in_int64(self):
        self.refused('minimal', MINIMAL)

    def test_other_wide_constant_expressions_are_refused_in_int64(self):
        for name, text in WIDE_CONSTANTS:
            self.refused(name, text)

    def test_in_range_constant_expressions_match_cpython(self):
        self.same('in_range', IN_RANGE)

    def test_wide_runtime_values_stay_in_the_declared_overflow(self):
        for name, text in ROUTES:
            self.wide(name, text)

    def test_wide_constants_match_cpython_with_exact_ints(self):
        self.same('minimal_exact', MINIMAL, EXACT_MODES)
        for name, text in WIDE_CONSTANTS:
            self.same(name + '_exact', text, EXACT_MODES)

    def test_wide_runtime_values_match_cpython_with_exact_ints(self):
        for name, text in ROUTES:
            self.same(name + '_exact', text, EXACT_MODES)


if __name__ == '__main__':
    unittest.main()

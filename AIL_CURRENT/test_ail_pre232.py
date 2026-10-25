"""Pre-232: huge `r` for combinations()/combinations_with_replacement() is a MemoryError.

The review of job pre219 left the first recorded difference open: CPython allocates the
r-entry index array (and the r-tuple) before its empty-result checks, so
`combinations([1, 2], 10**18)` and `combinations_with_replacement([1, 2], 10**18)` raise
MemoryError even though no item would be produced.  AIL printed `ok 0` for one call and
stopped with the runtime's uncatchable out-of-memory output for the other.

The general path now raises a catchable MemoryError from the same up-front allocation
check, before the `r > n` and empty-pool returns.  The typed path cannot raise MemoryError
and lowered the stream to an eager `list(range(r))`; it therefore refuses a *constant* r
no machine could allocate, which sends the default build to the general path.  A run-time
r stays on the typed path for the values it already supports.

The cases below cover small/zero/negative r, r > n, empty pools with a huge r, the huge r
reaching the call through an argument, a list item, an attribute and a dict value, the
constructor, `list(...)`, a for loop, and the typed-only refusal (by name) of a constant
huge r.  A typed-only run with a small run-time r keeps the existing lowering alive.
"""
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent
CLI = str(ROOT / "ail_chatgpt.py")

PROGRAM = r'''import itertools


class Box:
    def __init__(self, r: int) -> None:
        self.r = r


def comb(r):
    try:
        return len(list(itertools.combinations([1, 2], r)))
    except MemoryError:
        return "MemoryError"


def cwr(r):
    try:
        return len(list(itertools.combinations_with_replacement([1, 2], r)))
    except MemoryError:
        return "MemoryError"


def ctor(r):
    try:
        itertools.combinations([1, 2], r)
        return "made"
    except MemoryError:
        return "MemoryError"


def ctor_cwr(r):
    try:
        itertools.combinations_with_replacement([1, 2], r)
        return "made"
    except MemoryError:
        return "MemoryError"


def main():
    print("small", comb(0), cwr(0), comb(2), cwr(2), comb(3), cwr(3))
    print("empty", len(list(itertools.combinations([], 0))),
          len(list(itertools.combinations_with_replacement([], 0))))
    try:
        list(itertools.combinations([], 10**18))
        print("empty comb no error")
    except MemoryError:
        print("empty comb MemoryError")
    try:
        list(itertools.combinations_with_replacement([], 10**18))
        print("empty cwr no error")
    except MemoryError:
        print("empty cwr MemoryError")
    rs = [10**18]
    box = Box(10**18)
    d = {"r": 10**18}
    print("paths", comb(rs[0]), cwr(box.r), comb(d["r"]))
    print("huge", comb(10**18), cwr(10**18), ctor(10**18), ctor_cwr(10**18))
    n = 0
    try:
        for x in itertools.combinations([1, 2], 10**18):
            n += 1
        print("for comb done", n)
    except MemoryError:
        print("for comb MemoryError")
    n = 0
    try:
        for x in itertools.combinations_with_replacement([1, 2], 10**18):
            n += 1
        print("for cwr done", n)
    except MemoryError:
        print("for cwr MemoryError")
    for r in (-1, -7):
        try:
            list(itertools.combinations([1, 2], r))
            print("neg comb no error")
        except ValueError as e:
            print("neg comb ValueError", str(e))
    for r in (-1, -7):
        try:
            list(itertools.combinations_with_replacement([1, 2], r))
            print("neg cwr no error")
        except ValueError as e:
            print("neg cwr ValueError", str(e))


main()
'''

REFUSED = [
    ('comb_list', 'import itertools\n'
                  'print(len(list(itertools.combinations([1, 2], 10**18))))\n',
     'itertools.combinations: r=1000000000000000000 is too large to allocate'),
    ('cwr_list', 'import itertools\n'
                 'print(len(list(itertools.combinations_with_replacement([1, 2], 10**18))))\n',
     'itertools.combinations_with_replacement: r=1000000000000000000 is too large to allocate'),
    ('comb_for', 'import itertools\n'
                 'for x in itertools.combinations([1, 2], 10**18):\n'
                 '    print(x)\n',
     'itertools.combinations: r=1000000000000000000 is too large to allocate'),
    ('cwr_for', 'import itertools\n'
                'for x in itertools.combinations_with_replacement([1, 2], 10**18):\n'
                '    print(x)\n',
     'combinations_with_replacement: r=1000000000000000000 is too large to allocate'),
]

RUNTIME_R = r'''import itertools


def run(r):
    n = 0
    for x in itertools.combinations([1, 2, 3], r):
        n += 1
    print("for", n)
    m = 0
    for y in itertools.combinations_with_replacement([1, 2], r % 3):
        m += 1
    print("cwr", m)


run(2)
'''


def _cpython(directory, name, text):
    src = Path(directory) / (name + '_cpython.py')
    src.write_text(text, encoding='utf-8')
    done = subprocess.run([sys.executable, '-B', str(src)], capture_output=True, timeout=120,
                          env=dict(os.environ, PYTHONUTF8='1'))
    return done.stdout.replace(b'\r\n', b'\n'), done.returncode, done.stderr


def _build_and_run(directory, name, text, general, no_general=False):
    src = Path(directory) / (name + '.ail')
    src.write_text(text, encoding='utf-8')
    exe = Path(directory) / ('exe_' + name + ('_g' if general else '_d'))
    env = dict(os.environ, AIL_NO_CACHE='1', AIL_QUIET_FALLBACK='1')
    env.pop('AIL_NO_GENERAL', None)
    if no_general:
        env['AIL_NO_GENERAL'] = '1'
    if general:
        env['AIL_UNIFIED_FORCE'] = '1'
    else:
        env.pop('AIL_UNIFIED_FORCE', None)
    built = subprocess.run([sys.executable, '-B', CLI, 'compile', src.name,
                            '--syntax', 'python', '-o', exe.name], cwd=directory,
                           capture_output=True, text=True, timeout=900, env=env)
    if built.returncode != 0:
        return None, (built.stdout + built.stderr)[-3000:]
    got = subprocess.run([str(exe)], capture_output=True, timeout=120, cwd=directory)
    return (got.stdout.replace(b'\r\n', b'\n'), got.returncode), got.stderr.decode('utf-8', 'replace')[-1500:]


class Pre232Tests(unittest.TestCase):
    def check(self, slug, text):
        with tempfile.TemporaryDirectory(prefix='ail-pre232-') as directory:
            want, want_rc, err = _cpython(directory, slug, text)
            self.assertEqual(want_rc, 0, err)
            for general in (True, False):
                got, build_err = _build_and_run(directory, '%s_%s' % (slug, 'g' if general else 'd'),
                                                text, general)
                self.assertIsNotNone(got, '%s (general=%s)\n%s' % (slug, general, build_err))
                self.assertEqual(got, (want, 0), '%s (general=%s)\n%s' % (slug, general, build_err))

    def test_large_r_combinations(self):
        self.check('large_r', PROGRAM)

    def test_typed_path_refuses_constant_huge_r(self):
        for slug, text, needle in REFUSED:
            with tempfile.TemporaryDirectory(prefix='ail-pre232-') as directory:
                got, build_err = _build_and_run(directory, slug + '_typed', text, False,
                                                no_general=True)
                self.assertIsNone(got, 'built and ran instead of refusing:\n%s\n%s'
                                  % (text, build_err))
                self.assertIn(needle, build_err, build_err)

    def test_typed_path_keeps_runtime_r(self):
        with tempfile.TemporaryDirectory(prefix='ail-pre232-') as directory:
            want, want_rc, err = _cpython(directory, 'runtime_r', RUNTIME_R)
            self.assertEqual(want_rc, 0, err)
            got, build_err = _build_and_run(directory, 'runtime_r_typed', RUNTIME_R, False,
                                            no_general=True)
            self.assertIsNotNone(got, 'typed-only build failed:\n%s' % build_err)
            self.assertEqual(got, (want, 0), build_err)


if __name__ == '__main__':
    unittest.main()

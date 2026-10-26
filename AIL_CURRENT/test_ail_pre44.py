"""pre44: an unassigned Callable local raises CPython's UnboundLocalError.

The R570 callable-value test expected a RuntimeError for a direct call of a
callback local that the definite-assignment pass had not assigned.  CPython
raises UnboundLocalError there, and so does this compiler (the R570 expectation
predates the pass).  The same rule holds when the unassigned value is reached
through a list item, a dict value or an argument, and for an annotation with no
assignment, a branch that did not run, a loop that ran zero times and ``del``.
Each program catches the error and prints its message, so both builds are
compared with CPython by stdout and exit status.
"""
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent

DIRECT = r'''from typing import Callable

def target(x: int) -> int:
    return x

def main() -> int:
    if 0:
        cb: Callable[[int], int] = target
    try:
        cb(1)
    except UnboundLocalError as e:
        print("direct", str(e))
        return 0
    return 9

main()
'''

ANNOTATED = r'''from typing import Callable

def main() -> int:
    cb: Callable[[int], int]
    try:
        cb(1)
    except UnboundLocalError as e:
        print("annotated", str(e))
        return 0
    return 9

main()
'''

PATHS = r'''from typing import Callable

def target(x: int) -> int:
    return x

def apply(f: Callable[[int], int], x: int) -> int:
    return f(x)

def main() -> int:
    if 0:
        cb: Callable[[int], int] = target
    try:
        print([cb][0](1))
    except UnboundLocalError as e:
        print("list", str(e))
    try:
        print({0: cb}[0](1))
    except UnboundLocalError as e:
        print("dict", str(e))
    try:
        print(apply(cb, 1))
    except UnboundLocalError as e:
        print("argument", str(e))
    return 0

main()
'''

CONTROL = r'''from typing import Callable

def target(x: int) -> int:
    return x

def main(n: int) -> int:
    if n:
        cb: Callable[[int], int] = target
    try:
        cb(1)
    except UnboundLocalError as e:
        print("if", str(e))
    for i in range(0):
        looped: Callable[[int], int] = target
    try:
        looped(1)
    except UnboundLocalError as e:
        print("loop", str(e))
    deleted: Callable[[int], int] = target
    del deleted
    try:
        deleted(1)
    except UnboundLocalError as e:
        print("del", str(e))
    return 0

main(0)
'''


def _cpython(directory, name, text):
    src = Path(directory) / (name + '_cpython.py')
    src.write_text(text, encoding='utf-8')
    done = subprocess.run([sys.executable, '-B', str(src)], capture_output=True, timeout=120,
                          env=dict(os.environ, PYTHONUTF8='1'))
    return done.stdout.replace(b'\r\n', b'\n'), done.returncode, done.stderr


def _build_and_run(directory, name, text, general):
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
    if built.returncode != 0:
        return None, (built.stdout + built.stderr)[-3000:]
    got = subprocess.run([str(exe)], capture_output=True, timeout=120, cwd=directory)
    return (got.stdout.replace(b'\r\n', b'\n'), got.returncode), got.stderr.decode('utf-8', 'replace')[-1500:]


class Pre44Tests(unittest.TestCase):
    def check(self, slug, text):
        with tempfile.TemporaryDirectory(prefix='ail-pre44-') as directory:
            want, want_rc, err = _cpython(directory, slug, text)
            self.assertEqual(want_rc, 0, err)
            for general in (True, False):
                got, build_err = _build_and_run(directory, '%s_%s' % (slug, 'g' if general else 'd'),
                                                text, general)
                self.assertIsNotNone(got, '%s (general=%s)\n%s' % (text[:2000], general, build_err))
                self.assertEqual(got, (want, 0), '%s (general=%s)\n%s' % (text[:2000], general, build_err))

    def test_uninitialized_callback_direct(self):
        self.check('uninitialized_direct', DIRECT)

    def test_uninitialized_callback_annotation_only(self):
        self.check('uninitialized_annotation', ANNOTATED)

    def test_uninitialized_callback_through_list_dict_argument(self):
        self.check('uninitialized_paths', PATHS)

    def test_uninitialized_callback_control_flow(self):
        self.check('uninitialized_control', CONTROL)


if __name__ == '__main__':
    unittest.main()

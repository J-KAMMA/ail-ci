"""Runtime-raised KeyError keeps its key, including typed tuple-keyed containers, against CPython.

Reported as a pre-existing difference by the review of job fuzz81: a missing key in a
dict[tuple[...], ...] or set[tuple[...]] (r19/r20) printed the repr string as the argument,
`KeyError('(4, 5)')` with `e.args == ('(4, 5)',)`, where CPython keeps the tuple itself,
`KeyError((4, 5))` with `e.args == ((4, 5),)`.  The same runtime path is used for scalar keys on
the general build.
"""
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent

TUPLE_DICT = r'''GRID = {(0, 1): 5, (2, 3): 7}


class Box:
    def __init__(self) -> None:
        self.d = {(8, 9): 1}


def report(label: str, e: KeyError) -> None:
    print(label, str(e), repr(e), e.args, e.args[0], type(e).__name__)


def get(d: dict[tuple[int, int], int], k: tuple[int, int], label: str) -> None:
    try:
        print(label, d[k])
    except KeyError as e:
        report(label, e)


def pop(d: dict[tuple[int, int], int], k: tuple[int, int], label: str) -> None:
    try:
        print(label, d.pop(k))
    except KeyError as e:
        report(label, e)


def main() -> None:
    b = Box()
    keys = [(-6, 7)]
    box = {"k": (10, 11)}
    get(GRID, (4, 5), "module")
    k = (12, 13)
    get(b.d, k, "variable")
    get(b.d, keys[0], "listitem")
    get(b.d, box["k"], "dictvalue")
    get(b.d, (14, 15), "literal")
    pop(GRID, (16, 17), "pop")
    get(GRID, (0, 1), "present")


main()
'''

TUPLE_SET = r'''def report(label: str, e: KeyError) -> None:
    print(label, str(e), repr(e), e.args, e.args[0], type(e).__name__)


def remove(s: set[tuple[int, int]], k: tuple[int, int], label: str) -> None:
    try:
        s.remove(k)
    except KeyError as e:
        report(label, e)


def main() -> None:
    s = {(1, 2)}
    remove(s, (3, 4), "argument")
    remove(s, (5, 6), "literal")
    s.discard((7, 8))
    print("kept", len(s), (1, 2) in s)


main()
'''

SCALAR = r'''def main() -> None:
    d = {"a": 1}
    try:
        print(d["b"])
    except KeyError as e:
        print("get", str(e), repr(e), e.args, e.args[0])
    try:
        print(d.pop("c"))
    except KeyError as e:
        print("pop", str(e), repr(e), e.args, e.args[0])
    del d["a"]
    try:
        del d["d"]
    except KeyError as e:
        print("del", str(e), repr(e), e.args, e.args[0])
    try:
        set().remove("x")
    except KeyError as e:
        print("remove", str(e), repr(e), e.args, e.args[0])
    print("done")


main()
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


class Pre12Tests(unittest.TestCase):
    def check(self, slug, text, rc=0):
        with tempfile.TemporaryDirectory(prefix='ail-pre12-') as directory:
            want, got_rc, err = _cpython(directory, slug, text)
            self.assertEqual(got_rc, rc, err)
            for general in (True, False):
                got, build_err = _build_and_run(directory, '%s_%s' % (slug, 'g' if general else 'd'), text, general)
                self.assertIsNotNone(got, '%s (general=%s)\n%s' % (text[:2000], general, build_err))
                self.assertEqual(got, (want, rc), '%s (general=%s)\n%s' % (text[:2000], general, build_err))

    def test_tuple_keyed_dict(self):
        self.check('tuple_dict', TUPLE_DICT)

    def test_tuple_keyed_set(self):
        self.check('tuple_set', TUPLE_SET)

    def test_scalar_key_errors(self):
        self.check('scalar', SCALAR)


if __name__ == '__main__':
    unittest.main()

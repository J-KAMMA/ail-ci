"""fuzz82: global state across functions -- deleting from a module-level list.

`del xs[i]` in a function that names a module-level numeric list used to reach the typed
path's `ail_list_pop` on the const table `_emit_module_consts` declares. Deleting the last
element wrote `.n` through const storage (the optimiser could drop the write, so the program
printed the old list, exit 0); deleting one before it also memmoved over const data and
faulted. The typed path now refuses the construct by name, like `.append()` and `xs[i] = v`;
the default build falls back to the general path and prints what CPython prints.

The probes cover the last and a middle element, a negative index, an out-of-range index, and
an index that reaches the delete through a parameter, a list item, an attribute and a dict
value. Both builds are compared with CPython; the typed path alone must refuse by name.
"""
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent
CLI = ROOT / 'ail_chatgpt.py'

PROGRAM = r'''a = [1, 2, 3]
b = [4, 5, 6, 7]
c = [8, 9, 10]
d = [11, 12, 13, 14]
e = [15, 16, 17, 18, 19]
idxs = [1]
m = {"k": 3}


class Box:
    def __init__(self, i):
        self.i = i


def drop_a(i):
    del a[i]


def drop_b(i):
    del b[i]


def drop_c(i):
    del c[i]


def drop_d(i):
    del d[i]


def drop_e(i):
    del e[i]


def main():
    box = Box(2)
    drop_a(-1)
    drop_b(1)
    drop_c(idxs[0])
    drop_d(box.i)
    drop_e(m["k"])
    print(a, b, c, d, e)
    print(len(a), a[0], a[-1])
    try:
        drop_a(100)
    except IndexError:
        print("IndexError")
    try:
        drop_e(-100)
    except IndexError:
        print("IndexError")
    print(a, e)


main()
'''


def cpython(directory, name, text):
    src = Path(directory) / (name + '.py')
    src.write_text(text, encoding='utf-8')
    done = subprocess.run([sys.executable, '-B', src.name], cwd=directory, capture_output=True,
                          timeout=120, env=dict(os.environ, PYTHONUTF8='1'))
    return done.stdout.replace(b'\r\n', b'\n'), done.returncode, done.stderr


def build(directory, name, text, *, general, typed_only=False):
    src = Path(directory) / (name + '.ail')
    src.write_text(text, encoding='utf-8')
    exe = Path(directory) / (name + ('_g' if general else '_t' if typed_only else '_d'))
    env = dict(os.environ, AIL_NO_CACHE='1', AIL_QUIET_FALLBACK='1')
    env.pop('AIL_UNIFIED_FORCE', None)
    env.pop('AIL_NO_GENERAL', None)
    if general:
        env['AIL_UNIFIED_FORCE'] = '1'
    if typed_only:
        env['AIL_NO_GENERAL'] = '1'
    done = subprocess.run([sys.executable, '-B', str(CLI), 'compile', src.name, '--syntax', 'python',
                           '-o', exe.name], cwd=directory, capture_output=True, text=True,
                          timeout=900, env=env)
    return done, exe


class Fuzz82Tests(unittest.TestCase):
    def test_module_list_delete_matches_cpython(self):
        with tempfile.TemporaryDirectory(prefix='ail-fuzz82-') as directory:
            want, rc, err = cpython(directory, 'main', PROGRAM)
            self.assertEqual(rc, 0, err.decode('utf-8', 'replace'))
            for general in (True, False):
                done, exe = build(directory, 'main_%s' % ('g' if general else 'd'), PROGRAM, general=general)
                self.assertEqual(done.returncode, 0, done.stdout + done.stderr)
                got = subprocess.run([str(exe)], cwd=directory, capture_output=True, timeout=120)
                self.assertEqual(got.stdout.replace(b'\r\n', b'\n'), want, got.stderr.decode('utf-8', 'replace'))
                self.assertEqual(got.returncode, 0)

    def test_module_list_delete_is_refused_by_name_on_the_typed_path(self):
        with tempfile.TemporaryDirectory(prefix='ail-fuzz82-') as directory:
            done, _ = build(directory, 'typed', PROGRAM, general=False, typed_only=True)
            self.assertIn(done.returncode, (2, 3), done.stdout + done.stderr)
            self.assertIn("'a' is a module-level constant; deleting from it would mutate it",
                          done.stderr)
            self.assertNotIn('Traceback', done.stderr)


if __name__ == '__main__':
    unittest.main()

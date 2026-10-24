"""pre152: reading `__name__` on a class read as a value.

`C.__name__` failed on both builds with `AttributeError: 'type' object has no attribute
'__name__'`: a class is a real CLASS value in the general path, and `ail_inst_getattr`
accepted only INST/EXC receivers. It now answers CPython's `type.__name__` (the class's own
name, whatever the class body or a base holds under `__name__`), and the missing-attribute
message for a class receiver is CPython's `type object 'C' has no attribute 'x'`.

The probes cover a direct read, a repeated read, a class kept in a variable, an argument, a
list item, a dict value and an attribute, a base with a `__name__` class attribute, an
exception class, and the unchanged errors on a class and on an int. Both builds are compared
with CPython.
"""
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent
CLI = ROOT / 'ail_chatgpt.py'

PROGRAM = r'''class C:
    pass


class Named:
    __name__ = 5


class Base:
    __name__ = 9


class Sub(Base):
    pass


class E(Exception):
    pass


class Box:
    def __init__(self, v):
        self.v = v


def name_of(cls):
    return cls.__name__


def main():
    print(C.__name__)
    print(C.__name__)
    cls = C
    print(cls.__name__)
    print(name_of(C))
    print(name_of(E))
    print([C][0].__name__)
    print({"k": C}["k"].__name__)
    print(Box(C).v.__name__)
    print(Named.__name__)
    print(Sub.__name__)
    print("%s!" % C.__name__)
    print(f"{C.__name__}?")
    c = C()
    print(c.__class__.__name__, type(c).__name__)
    try:
        print(C.missing)
    except AttributeError as e:
        print("AttributeError:", e)
    try:
        print((5).missing)
    except AttributeError as e:
        print("AttributeError:", e)


main()
'''


def cpython(directory, name, text):
    src = Path(directory) / (name + '.py')
    src.write_text(text, encoding='utf-8')
    done = subprocess.run([sys.executable, '-B', src.name], cwd=directory, capture_output=True,
                          timeout=120, env=dict(os.environ, PYTHONUTF8='1'))
    return done.stdout.replace(b'\r\n', b'\n'), done.returncode, done.stderr


def build(directory, name, text, *, general):
    src = Path(directory) / (name + '.ail')
    src.write_text(text, encoding='utf-8')
    exe = Path(directory) / (name + ('_g' if general else '_d'))
    env = dict(os.environ, AIL_NO_CACHE='1', AIL_QUIET_FALLBACK='1')
    env.pop('AIL_UNIFIED_FORCE', None)
    env.pop('AIL_NO_GENERAL', None)
    if general:
        env['AIL_UNIFIED_FORCE'] = '1'
    done = subprocess.run([sys.executable, '-B', str(CLI), 'compile', src.name, '--syntax', 'python',
                           '-o', exe.name], cwd=directory, capture_output=True, text=True,
                          timeout=900, env=env)
    return done, exe


class Pre152Tests(unittest.TestCase):
    def test_class_name_matches_cpython(self):
        with tempfile.TemporaryDirectory(prefix='ail-pre152-') as directory:
            want, rc, err = cpython(directory, 'main', PROGRAM)
            self.assertEqual(rc, 0, err.decode('utf-8', 'replace'))
            for general in (True, False):
                done, exe = build(directory, 'main_%s' % ('g' if general else 'd'), PROGRAM, general=general)
                self.assertEqual(done.returncode, 0, done.stdout + done.stderr)
                got = subprocess.run([str(exe)], cwd=directory, capture_output=True, timeout=120)
                self.assertEqual(got.stdout.replace(b'\r\n', b'\n'), want, got.stderr.decode('utf-8', 'replace'))
                self.assertEqual(got.returncode, 0)


if __name__ == '__main__':
    unittest.main()

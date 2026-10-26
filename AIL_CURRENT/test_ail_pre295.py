"""Class attribute stores through every route to the class (job pre295).

The pre283 reviewer recorded that a class attribute store whose class base reached the
assignment through a computed index, a function return, an instance attribute, a parameter, a
conditional alias, a local alias or a `global`-declared name raised
`AttributeError: 'type' object has no attribute 'v'`, while CPython prints the new value.  The
general runtime's attribute store now updates the class's shared attribute slot (or a dynamic
entry for a name the class body did not define), and an instance that does not shadow the name
reads it through its class, so existing instances see the new value too.  Inheritance is kept
per class: `Sub.v = x` hides `Base.v` instead of changing it.  A class body attribute is still
evaluated once and shared by class and instance reads.

The programs below cover the recorded routes, new names, int/float/str/list/dict/None/bool
values, augmented assignment, inherited attributes, instance shadowing, `vars`, `getattr`,
`hasattr` and `setattr`, on both builds.
"""
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent
CLI = str(ROOT / 'ail_chatgpt.py')

ROUTES = r'''class Box:
    v = 1


class Holder:
    def __init__(self, c):
        self.c = c


def get():
    return Box


def set_param(c, x):
    c.v = x


def set_global(x):
    global Box
    Box.v = x


def main():
    holder = Holder(Box)
    boxes = [Box, Box]
    alias = Box
    local = Box
    boxes[0].v = 2
    print(Box.v)
    get().v = 3
    print(Box.v)
    holder.c.v = 4
    print(Box.v)
    set_param(Box, 5)
    print(Box.v)
    alias.v = 6
    print(Box.v)
    local.v = 7
    print(Box.v)
    chosen = Box if get() is Box else holder.c
    chosen.v = 8
    print(Box.v)
    set_global(9)
    print(Box.v)


main()
'''

VALUES = r'''class Box:
    i = 0
    f = 0.0
    s = ""
    xs = []
    d = {}


def set_box(c):
    c.i = -7
    c.f = -1.5
    c.s = "hi"
    c.xs = [1, 2]
    c.d = {"k": 1}
    c.n = None
    c.b = True


def main():
    set_box(Box)
    print(Box.i, Box.f, Box.s, Box.xs, Box.d, Box.n, Box.b)
    box = Box()
    print(box.i, box.f, box.s, box.xs, box.d, box.n, box.b)
    Box.i += 5
    print(Box.i, box.i)
    Box.s += "!"
    print(Box.s, box.s)


main()
'''

INHERITANCE = r'''class Base:
    v = 1
    shared = []


class Sub(Base):
    pass


def main():
    b = Base()
    s = Sub()
    Base.v = 2
    print(Base.v, b.v, Sub.v, s.v)
    Sub.v = 3
    print(Base.v, b.v, Sub.v, s.v)
    b.v = 9
    print(Base.v, b.v, Sub.v, s.v)
    Sub.shared = [1]
    print(Base.shared, b.shared, Sub.shared, s.shared, b.shared is Base.shared)
    print(vars(b), vars(s))
    print(getattr(b, "v"), getattr(b, "missing", "dflt"), hasattr(b, "v"))
    setattr(Base, "v", 4)
    print(Base.v, b.v, s.v)


main()
'''

NEW_NAMES = r'''class Box:
    pass


def main():
    b = Box()
    Box.w = 5
    print(Box.w, b.w)
    Box.w = 6
    print(Box.w, b.w)
    print(getattr(Box, "w"), hasattr(Box, "w"), getattr(b, "w"))
    setattr(Box, "z", 7)
    print(Box.z, b.z, getattr(Box, "z"))


main()
'''


def _cpython(directory, name, text):
    src = Path(directory) / (name + '_cpython.py')
    src.write_text(text, encoding='utf-8')
    done = subprocess.run([sys.executable, '-B', str(src)], capture_output=True, timeout=120,
                          env=dict(os.environ, PYTHONUTF8='1'))
    return done.stdout.replace(b'\r\n', b'\n'), done.returncode


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
    built = subprocess.run([sys.executable, '-B', CLI, 'compile', src.name,
                            '--syntax', 'python', '-o', exe.name], cwd=directory,
                           capture_output=True, text=True, timeout=900, env=env)
    if built.returncode != 0:
        return None, (built.stdout + built.stderr)[-3000:]
    got = subprocess.run([str(exe)], capture_output=True, timeout=120, cwd=directory)
    return (got.stdout.replace(b'\r\n', b'\n'), got.returncode), got.stderr.decode('utf-8', 'replace')[-1500:]


class Pre295Tests(unittest.TestCase):
    def check(self, slug, text):
        with tempfile.TemporaryDirectory(prefix='ail-pre295-') as directory:
            want, want_rc = _cpython(directory, slug, text)
            self.assertEqual(want_rc, 0)
            for general in (True, False):
                got, build_err = _build_and_run(directory, '%s_%s' % (slug, 'g' if general else 'd'),
                                                text, general)
                self.assertIsNotNone(got, '%s (general=%s)\n%s' % (slug, general, build_err))
                self.assertEqual(got, (want, want_rc), '%s (general=%s)\n%s'
                                 % (slug, general, build_err))

    def test_routes(self):
        self.check('routes', ROUTES)

    def test_values(self):
        self.check('values', VALUES)

    def test_inheritance_and_instances(self):
        self.check('inheritance', INHERITANCE)

    def test_new_names(self):
        self.check('new_names', NEW_NAMES)


if __name__ == '__main__':
    unittest.main()

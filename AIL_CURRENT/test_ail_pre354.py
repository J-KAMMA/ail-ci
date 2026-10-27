"""pre354: a local or parameter named ``slice`` must not shadow the slice class.

The pre327 reviewer recorded this as pre-existing: a function whose parameter or local
is named ``slice``, followed by a slice of a user-class instance, raised
``TypeError: 'int' object is not callable`` on both builds, where CPython passes its
builtin ``slice`` object to ``__getitem__``.  The general path built the object with a
call to the user-visible name ``slice``; it now calls the prelude class through the
compiler's class reference, so user code that binds ``slice`` still sees its own binding
while the subscript uses the builtin type.  A user binding of any helper name (the first
fix's ``_ail_slice_type`` alias included) cannot shadow it.
"""
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent

CASES = {
    'shadow_param': '''
class C:
    def __getitem__(self, i):
        return (i.start, i.stop, i.step)


def cut(slice, x):
    return x[1:2]


print(cut(5, C()))
''',
    'shadow_local': '''
class C:
    def __getitem__(self, i):
        return i


def cut(x):
    slice = 3
    return x[1:2]


print(cut(C()))
''',
    'shadow_method': '''
class C:
    def __getitem__(self, i):
        return (i.start, i.stop, i.step)


class D:
    def m(self, slice):
        return C()[1:2]


print(D().m(7))
''',
    'shadow_module': '''
class C:
    def __getitem__(self, i):
        return (i.start, i.stop, i.step)


slice = 5
print(C()[1:2])
''',
    'shadow_global_func': '''
class C:
    def __getitem__(self, i):
        return i


slice = 5


def cut(x):
    return x[1:2]


print(cut(C()))
''',
    'user_slice': '''
class C:
    def __getitem__(self, i):
        return i


print(C()[1:2])
print(slice(1, 2))
print(slice(1, 2, 3).start)
''',
    'shadow_loop': '''
class C:
    def __getitem__(self, i):
        return (i.start, i.stop, i.step)


def cut(x):
    for slice in (1,):
        return x[1:2]


print(cut(C()))
''',
    'alias_local': '''
class C:
    def __getitem__(self, i):
        return (i.start, i.stop, i.step)


def cut(x):
    _ail_slice_type = 9
    return x[1:2]


print(cut(C()))
''',
    'alias_global': '''
class C:
    def __getitem__(self, i):
        return (i.start, i.stop, i.step)


_ail_slice_type = 9
print(C()[1:2])
''',
    'alias_param': '''
class C:
    def __getitem__(self, i):
        return (i.start, i.stop, i.step)


def cut(_ail_slice_type, x):
    return x[1:2]


print(cut(9, C()))
''',
    'routes_and_store': '''
class C:
    def __init__(self):
        self.items = list(range(6))

    def __getitem__(self, i):
        if isinstance(i, slice):
            return (i.start, i.stop, i.step)
        return self.items[i]

    def __setitem__(self, i, v):
        self.items[i] = v

    def __delitem__(self, i):
        del self.items[i]


class H:
    pass


def cut(slice, x):
    return x[1:3]


def setcut(slice, x):
    x[1:4] = [9]


def delcut(slice, x):
    del x[::2]


c = C()
alias = c
holder = H()
holder.c = c
d = {"c": c}
xs = [c]
print(cut(1, c), cut(1, alias), cut(1, holder.c), cut(1, d["c"]), cut(1, xs[0]))
setcut(1, d["c"])
print(c.items)
delcut(1, xs[0])
print(c.items, alias.items)
''',
}

REFUSALS = ('int64 literal out of range', 'int64 constant out of range')


def compile_source(directory, name, source, general):
    path = Path(directory) / (name + '.ail')
    path.write_text(source, encoding='utf-8')
    env = dict(os.environ, AIL_NO_CACHE='1', AIL_QUIET_FALLBACK='1')
    env.pop('AIL_UNIFIED_FORCE', None)
    if general:
        env['AIL_UNIFIED_FORCE'] = '1'
    exe = Path(directory) / (name + ('_g' if general else '_d'))
    built = subprocess.run([sys.executable, '-B', str(ROOT / 'ail_chatgpt.py'), 'compile', path.name,
                            '--syntax', 'python', '-o', exe.name], cwd=directory,
                           capture_output=True, text=True, timeout=900, env=env)
    return built, exe


def run_cpython(directory, name, source):
    path = Path(directory) / (name + '_cpython.py')
    path.write_text(source, encoding='utf-8')
    ran = subprocess.run([sys.executable, '-B', path.name], cwd=directory, capture_output=True,
                         text=True, timeout=120)
    return ran.stdout.replace('\r\n', '\n'), ran.returncode


class Pre354(unittest.TestCase):
    def test_shadowed_slice_name(self):
        for slug, source in CASES.items():
            with tempfile.TemporaryDirectory(prefix='ail-pre354-') as directory:
                expected, status = run_cpython(directory, 'pre354_' + slug, source)
            modes = set()
            for general in (False, True):
                with self.subTest(slug=slug, general=general), \
                        tempfile.TemporaryDirectory(prefix='ail-pre354-') as directory:
                    built, exe = compile_source(directory, 'pre354_' + slug, source, general)
                    output = built.stdout + built.stderr
                    if built.returncode != 0:
                        self.assertFalse(exe.exists(), '%s built an executable' % slug)
                        self.assertTrue(any(marker in output for marker in REFUSALS),
                                        output[-4000:])
                        modes.add('refused')
                    else:
                        self.assertTrue(exe.exists(), '%s did not build' % slug)
                        ran = subprocess.run([str(exe)], cwd=directory, capture_output=True,
                                             text=True, timeout=120)
                        self.assertEqual(ran.returncode, status, ran.stdout + ran.stderr)
                        self.assertEqual(ran.stdout.replace('\r\n', '\n'), expected,
                                         ran.stdout + ran.stderr)
                        modes.add('ran')
            self.assertEqual(len(modes), 1, '%s builds disagree: %s' % (slug, sorted(modes)))


if __name__ == '__main__':
    unittest.main()

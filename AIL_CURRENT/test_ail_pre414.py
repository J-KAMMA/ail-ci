"""pre414: an exception instance names its class in item errors.

The pre396 review recorded as pre-existing that ``del MyErr()[0]`` on a user exception
class printed ``'exception' object doesn't support item deletion`` on both builds, where
CPython names the instance's class (``'MyErr' object doesn't support item deletion``).
The v2 item-error name helper (``ail__tname_c``) handled only ordinary instances, so an
``AIL_T_EXC`` value fell through to the tag name ``exception``.  Exception values now take
the same class-name path, which also covers item reads and stores, subclasses, aliases and
values reaching the operation through an argument, a list item, an attribute and a dict
value.

Programs are built with the general path forced and with the default build; stdout and the
exit status must match CPython.
"""
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent
CHATGPT = str(ROOT / 'ail_chatgpt.py')


def cpython(directory, name, text):
    src = Path(directory) / (name + '_cpython.py')
    src.write_text(text, encoding='utf-8')
    return subprocess.run([sys.executable, '-B', str(src)], capture_output=True, timeout=120,
                          env=dict(os.environ, PYTHONUTF8='1', PYTHONWARNINGS='ignore'))


def build(directory, name, text, general):
    src = Path(directory) / (name + '.py')
    src.write_text(text, encoding='utf-8')
    exe = Path(directory) / ('exe_' + name + ('_g' if general else '_d'))
    env = dict(os.environ, AIL_NO_CACHE='1', AIL_QUIET_FALLBACK='1')
    env.pop('AIL_NO_GENERAL', None)
    if general:
        env['AIL_UNIFIED_FORCE'] = '1'
    return exe, subprocess.run([sys.executable, '-B', CHATGPT, 'compile', src.name, '--syntax', 'python',
                                '-o', exe.name], cwd=directory, capture_output=True, text=True, timeout=900, env=env)


def last_line(data):
    lines = [line for line in data.decode('utf-8', 'replace').splitlines() if line.strip()]
    return lines[-1] if lines else ''


class Pre414Tests(unittest.TestCase):
    def check(self, name, text):
        with tempfile.TemporaryDirectory(prefix='ail-pre414-') as directory:
            want = cpython(directory, name, text)
            for general in (True, False):
                exe, built = build(directory, name, text, general)
                self.assertEqual(built.returncode, 0, (name, general, built.stdout + built.stderr))
                got = subprocess.run([str(exe)], capture_output=True, timeout=120, cwd=directory)
                self.assertEqual(got.stdout, want.stdout, (name, general, got.stderr[-800:]))
                self.assertEqual(got.returncode, want.returncode, (name, general, got.stderr[-800:]))
                self.assertEqual(last_line(got.stderr), last_line(want.stderr),
                                 (name, general, got.stderr[-800:]))

    def test_exception_item_errors_name_the_class(self):
        self.check('item_names', '''
class MyErr(Exception):
    pass


class Sub(MyErr):
    pass


class Box:
    pass


def drop(x):
    del x[0]


def report(label, fn):
    try:
        fn()
    except Exception as e:
        print(label, type(e).__name__, e)


def del_int():
    del MyErr()[0]


def del_bool():
    del MyErr()[True]


def del_sub():
    del Sub()[0]


def get_int():
    print(MyErr()[0])


def get_sub():
    print(Sub()[0])


def set_int():
    MyErr()[0] = 1


def set_sub():
    Sub()[0] = 1


report('del_int', del_int)
report('del_bool', del_bool)
report('del_sub', del_sub)
a = MyErr()
try:
    del a[0]
except Exception as e:
    print('del_alias', type(e).__name__, e)
try:
    drop(MyErr())
except Exception as e:
    print('del_arg', type(e).__name__, e)
xs = [MyErr()]
try:
    del xs[0][0]
except Exception as e:
    print('del_list_item', type(e).__name__, e)
box = Box()
box.e = MyErr()
try:
    del box.e[0]
except Exception as e:
    print('del_attr', type(e).__name__, e)
d = {'e': MyErr()}
try:
    del d['e'][0]
except Exception as e:
    print('del_dict_value', type(e).__name__, e)
report('get_int', get_int)
report('get_sub', get_sub)
report('set_int', set_int)
report('set_sub', set_sub)
''')

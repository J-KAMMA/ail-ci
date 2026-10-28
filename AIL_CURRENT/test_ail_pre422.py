"""pre422: an exception instance names its class in slice errors.

The pre414 review recorded that the item-error wording was too broad for slice deletion: an
exception instance still printed the tag name in a slice operation, e.g.
``del MyErr()[0:1]`` said ``'exception' object does not support item deletion`` on both
builds where CPython names the class (``'MyErr' object does not support item deletion``).
The slice assignment/deletion path in ``safetyrt.SLICE`` built its message from
``ail_type_name(c.tag)``, which returns the tag ``exception``; it now uses the same
``ail__raise_item_tname`` helper as the item path, so a custom exception, its subclass, an
ordinary instance and the builtin names follow CPython.  Slice assignment carries the same
name and is covered too.

Programs are built with the general path forced and with the default build; stdout, the exit
status and the last stderr line must match CPython.
"""
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent
CHATGPT = str(ROOT / 'ail_chatgpt.py')

LONG = 'E' * 210


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


class Pre422Tests(unittest.TestCase):
    def check(self, name, text):
        with tempfile.TemporaryDirectory(prefix='ail-pre422-') as directory:
            want = cpython(directory, name, text)
            for general in (True, False):
                exe, built = build(directory, name, text, general)
                self.assertEqual(built.returncode, 0, (name, general, built.stdout + built.stderr))
                got = subprocess.run([str(exe)], capture_output=True, timeout=120, cwd=directory)
                self.assertEqual(got.stdout, want.stdout, (name, general, got.stderr[-800:]))
                self.assertEqual(got.returncode, want.returncode, (name, general, got.stderr[-800:]))
                self.assertEqual(last_line(got.stderr), last_line(want.stderr),
                                 (name, general, got.stderr[-800:]))

    def test_exception_slice_errors_name_the_class(self):
        self.check('slice_names', '''
class MyErr(Exception):
    pass


class Sub(MyErr):
    pass


class Plain:
    pass


class Box:
    pass


class %s(Exception):
    pass


def show(label, fn):
    try:
        fn()
    except Exception as e:
        print(label, type(e).__name__, e)
    else:
        print(label, 'no error')


def del_one(x):
    del x[1:2]


def set_one(x):
    x[1:2] = []


def del_attr(b):
    del b.e[1:2]


def del_list_item():
    del [MyErr()][0][1:2]


def del_dict_value():
    del {'e': MyErr()}['e'][1:2]


def del_direct():
    del MyErr()[0:1]


def del_default():
    del MyErr()[::1]


def del_step():
    del MyErr()[0:2:2]


def del_negative():
    del MyErr()[-5:-1]


def del_none():
    del MyErr()[None:None]


def del_sub():
    del Sub()[2:1]


def set_direct():
    MyErr()[0:1] = []


def set_sub():
    Sub()[0:1] = ()


def del_plain():
    del Plain()[0:1]


def set_plain():
    Plain()[0:1] = []


def del_long():
    del %s()[0:1]


def set_long():
    %s()[0:1] = []


def del_int():
    del 5[0:1]


def del_float():
    del 5.0[0:1]


def del_none_value():
    del None[0:1]


def del_tuple():
    del (1, 2)[0:1]


def del_str():
    del 'ab'[0:1]


e = MyErr()
box = Box()
box.e = MyErr()
show('del_direct', del_direct)
show('del_default', del_default)
show('del_step', del_step)
show('del_negative', del_negative)
show('del_none', del_none)
show('del_sub', del_sub)
show('set_direct', set_direct)
show('set_sub', set_sub)
show('del_plain', del_plain)
show('set_plain', set_plain)
show('del_long', del_long)
show('set_long', set_long)
show('del_alias', lambda: del_one(e))
show('set_alias', lambda: set_one(e))
show('del_arg', lambda: del_one(MyErr()))
show('set_arg', lambda: set_one(MyErr()))
show('del_list_item', del_list_item)
show('set_list_item', lambda: set_one([MyErr()][0]))
show('del_attr', lambda: del_attr(box))
show('del_dict_value', del_dict_value)
show('set_dict_value', lambda: set_one({'e': MyErr()}['e']))
show('del_int', del_int)
show('del_float', del_float)
show('del_none_value', del_none_value)
show('del_tuple', del_tuple)
show('del_str', del_str)
''' % (LONG, LONG, LONG))

    def test_uncaught_slice_error(self):
        self.check('slice_uncaught', '''
class MyErr(Exception):
    pass


del MyErr()[0:1]
''')

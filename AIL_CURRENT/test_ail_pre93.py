"""Pre93: bare annotations on attribute and subscript targets evaluate their subexpressions.

CPython evaluates the target's own subexpressions for a function-local bare annotation
(`box().x: int` loads `box()`, `xs[i()]: int` loads `xs` and `i()`), but neither reads the
attribute nor performs the final subscript, and never evaluates the annotation. The surface
used to replace an attribute target with `pass`, so the calls disappeared. Module scope now
evaluates the target too; the annotation itself is still only a hint there.

Both builds are compared with CPython.
"""
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent

FUNCTIONS = r'''class Box:
    def __init__(self, v):
        self.x = v


events = []


def touch(label, value):
    events.append(label)
    return value


def ann():
    events.append("ann")
    return 0


holder = Box(1)
items = [Box(2), Box(3)]
table = {"b": Box(4), "i": [Box(5)]}
alias = holder


def attr_argument(box):
    touch("arg", box).x: ann()
    print("arg", events, box.x)


def attr_list_item():
    touch("list", items[1]).x: ann()
    print("list", events, items[1].x)


def attr_dict_value():
    touch("dict", table["b"]).x: ann()
    print("dict", events, table["b"].x)


def attr_chain():
    touch("chain", holder).child.x: ann()
    print("chain", events)


def attr_alias():
    alias.x: ann()
    print("alias", events, alias.x)


def sub_argument(xs, i):
    touch("sbase", xs)[touch("sidx", i)]: ann()
    print("subarg", events)


def sub_list_item(i):
    items[touch("slistidx", i)]: ann()
    print("sublist", events)


def sub_dict_value(key):
    table["i"][touch("sdictidx", key)]: ann()
    print("subdict", events)


def sub_nested(xs, key):
    touch("outer", xs)[touch("innerkey", key)][touch("finalkey", "z")]: ann()
    print("subnested", events)


def sub_slice(lo, hi):
    items[touch("lo", lo):touch("hi", hi)]: ann()
    print("slice", events)


def sub_step(lo, hi, step):
    items[touch("slo2", lo):touch("shi2", hi):touch("sstep2", step)]: ann()
    print("step", events)


def sub_tuple(i, j):
    items[touch("tup0", i), touch("tup1", j)]: ann()
    print("tuple", events)


def sub_negative():
    items[touch("neg", -1)]: ann()
    print("negative", events)


def sub_empty(xs):
    xs[touch("empty", 0)]: ann()
    print("empty", events)


def sub_not_subscriptable():
    5[touch("notsub", 0)]: ann()
    print("notsub", events)


def attr_none():
    None.x: ann()
    print("noneattr", events)


print("module", events)
attr_argument(holder)
attr_list_item()
attr_dict_value()
holder.child = Box(6)
attr_chain()
attr_alias()
sub_argument(items, 0)
sub_list_item(1)
sub_dict_value(0)
sub_nested(table["i"], 0)
sub_slice(0, 2)
sub_step(0, 2, 2)
sub_tuple(0, 1)
sub_negative()
sub_empty([])
sub_not_subscriptable()
attr_none()


def run_d():
    holder.child = Box(8)
    holder.child.x: ann()
    print("localnested", events)


run_d()
'''

FUTURE = r'''from __future__ import annotations

class Box:
    def __init__(self, v):
        self.x = v


events = []


def touch(label, value):
    events.append(label)
    return value


def ann():
    events.append("ann")
    return 0


holder = Box(1)
items = [Box(2), Box(3)]


def attr(box):
    touch("arg", box).x: ann()
    print("attr", events)


def sub(i):
    items[touch("idx", i)]: ann()
    print("sub", events)


def slice_target(lo, hi):
    items[touch("lo", lo):touch("hi", hi)]: ann()
    print("slice", events)


def local():
    holder.x: ann()
    print("local", events)


touch("module", holder).x: ann()
print("module", events)


events.clear()
attr(holder)
sub(-1)
slice_target(0, 2)
local()
'''

MODULE = r'''class Box:
    def __init__(self, v):
        self.x = v


events = []
holder = Box(1)
items = [Box(2), Box(3)]


def touch(label, value):
    events.append(label)
    return value


def ann():
    events.append("ann")
    return 0


touch("mbase", holder).x: int
print("module", events)
items[touch("sidx", 0)]: int
print("module2", events)
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


class Pre93Tests(unittest.TestCase):
    def check(self, slug, text):
        with tempfile.TemporaryDirectory(prefix='ail-pre93-') as directory:
            want, want_rc, err = _cpython(directory, slug, text)
            self.assertEqual(want_rc, 0, err)
            for general in (True, False):
                got, build_err = _build_and_run(directory, '%s_%s' % (slug, 'g' if general else 'd'),
                                                text, general)
                self.assertIsNotNone(got, '%s (general=%s)\n%s' % (slug, general, build_err))
                self.assertEqual(got, (want, 0), '%s (general=%s)\n%s' % (slug, general, build_err))

    def test_target_subexpressions_in_functions(self):
        self.check('functions', FUNCTIONS)

    def test_target_subexpressions_with_future_annotations(self):
        self.check('future', FUTURE)

    def test_target_and_annotation_expressions_at_module_scope(self):
        self.check('module', MODULE)


if __name__ == '__main__':
    unittest.main()

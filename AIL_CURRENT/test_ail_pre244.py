"""Pre-244: a walrus or `del` target is a local for the whole activation.

A function that binds a name with `:=` or `del` anywhere has a local of that name from
CPython's point of view, so a read textually before the binding raises UnboundLocalError.
The general path's scope scanner only recorded ordinary assignment targets, so

    def side(x): return x
    def f():
        print(side(1))
        (side := None)

called the module function and printed 1, and `del side` crashed the compiler with
`KeyError: 'side'`.  Walrus and delete targets are now scanned as bindings too, and a call
to a name that a local/closure binding shadows goes through that binding instead of the
statically known module function.  The cases below cover both constructs, reads before the
binding in expression/assignment/test/return/list/dict/attribute/argument positions,
values arriving as arguments, list items, attributes and dict values, module scope, a
`global` declaration, and a nested def, on both builds.
"""
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent

WALRUS_VARIANTS = r'''def side(x):
    return x


def other(x):
    return x + 100


def inc1(x):
    return x + 1


def inc10(x):
    return x * 10


class Box:
    def __init__(self, fn=None):
        self.fn = fn
        self.v = 0


def case_expr():
    print(side(1))
    (side := None)


def case_assign():
    print(side(1))
    v = (side := None)
    return v


def case_if():
    print(side(1))
    if (side := None):
        pass


def case_while():
    print(side(1))
    while (side := None):
        pass


def case_return():
    print(side(1))
    return (side := None)


def case_list():
    print(side(1))
    return [(side := None)]


def case_dict():
    print(side(1))
    return {"k": (side := None)}


def case_attr():
    b = Box()
    print(side(1))
    b.v = (side := None)


def case_arg():
    print(side(1))
    print((side := None))


def case_walrus_self():
    (side := side)


def case_self_assign():
    side = side


def case_call_bound():
    (side := inc1)
    return side(1)


def case_call_noncallable():
    (side := 5)
    return side(1)


def case_param(g):
    side = g
    return side(1)


def case_walrus_arg(g):
    (side := g)
    return side(1)


def case_list_fn():
    side = [inc10][0]
    return side(1)


def case_dict_fn(d):
    side = d["fn"]
    return side(1)


def case_attr_fn(b):
    side = b.fn
    return side(1)


def case_func_alias():
    side = other
    return side(1)


def case_builtin_alias():
    (side := len)
    return side([1, 2, 3])


def check(name, fn):
    try:
        print(name, fn())
    except Exception as e:
        print(name, type(e).__name__, e)


def check_arg(name, fn, arg):
    try:
        print(name, fn(arg))
    except Exception as e:
        print(name, type(e).__name__, e)


def main():
    check("expr", case_expr)
    check("assign", case_assign)
    check("if", case_if)
    check("while", case_while)
    check("return", case_return)
    check("list", case_list)
    check("dict", case_dict)
    check("attr", case_attr)
    check("arg", case_arg)
    check("walrus_self", case_walrus_self)
    check("self_assign", case_self_assign)
    check("call_bound", case_call_bound)
    check("call_noncallable", case_call_noncallable)
    check_arg("param", case_param, inc10)
    check_arg("walrus_arg", case_walrus_arg, inc10)
    check("list_fn", case_list_fn)
    check_arg("dict_fn", case_dict_fn, {"fn": inc10})
    check_arg("attr_fn", case_attr_fn, Box(inc10))
    check("func_alias", case_func_alias)
    check("builtin_alias", case_builtin_alias)


main()
'''

WALRUS_MODULE = r'''def side(x):
    return x


print("module", side(1))
(side := None)
print("after", side)
'''

WALRUS_GLOBAL = r'''def side(x):
    return x


def f():
    global side
    print(side(1))
    (side := None)
    print(side)


f()
'''

WALRUS_NESTED = r'''def side(x):
    return x


def outer():
    def inner():
        (side := 5)
        return side
    return inner()


print(outer())
print(side(1))
'''

DEL_VARIANTS = r'''def side(x):
    return x


G = 1


def case_unbound():
    del side


def case_assigned_then_del():
    side = 1
    del side
    return side


def case_del_ok():
    side = 1
    del side
    return "ok"


def case_global_assigned():
    del G


def case_param(p):
    del p
    return p


def case_tuple():
    a = 1
    b = 2
    del a, b
    return a


def case_walrus():
    (side := 1)
    del side
    return side


def case_item():
    xs = [1, 2, 3]
    del xs[0]
    return xs


def check(name, fn):
    try:
        print(name, fn())
    except Exception as e:
        print(name, type(e).__name__, e)


def check_arg(name, fn, arg):
    try:
        print(name, fn(arg))
    except Exception as e:
        print(name, type(e).__name__, e)


def main():
    check("unbound", case_unbound)
    check("assigned_then_del", case_assigned_then_del)
    check("del_ok", case_del_ok)
    check("global_assigned", case_global_assigned)
    check_arg("param", case_param, 5)
    check("tuple", case_tuple)
    check("walrus", case_walrus)
    check("item", case_item)


main()
'''

DEL_GLOBAL_DECL = r'''G = 1


def f():
    global G
    del G


try:
    f()
    print(G)
except Exception as e:
    print(type(e).__name__, e)
'''

DEL_MODULE = r'''side = 1
try:
    del side
    print(side)
except Exception as e:
    print(type(e).__name__, e)
'''

DEL_MODULE_FUNC = r'''def side(x):
    return x


print(side(1))
del side
print(side(2))
'''

DEL_GLOBAL_FUNC = r'''def side(x):
    return x


def f():
    global side
    del side
    print(side(1))


try:
    f()
except Exception as e:
    print(type(e).__name__, e)
'''

PROGRAMS = {
    'walrus_variants': WALRUS_VARIANTS,
    'walrus_module': WALRUS_MODULE,
    'walrus_global': WALRUS_GLOBAL,
    'walrus_nested': WALRUS_NESTED,
    'del_variants': DEL_VARIANTS,
    'del_global_decl': DEL_GLOBAL_DECL,
    'del_module': DEL_MODULE,
}

REFUSED = {
    'del_module_func': DEL_MODULE_FUNC,
    'del_global_func': DEL_GLOBAL_FUNC,
}


def _cpython(directory, name, text):
    src = Path(directory) / (name + '_cpython.py')
    src.write_text(text, encoding='utf-8')
    done = subprocess.run([sys.executable, '-B', str(src)], capture_output=True, timeout=120,
                          env=dict(os.environ, PYTHONUTF8='1'))
    return done.stdout.replace(b'\r\n', b'\n'), done.returncode, done.stderr


def _build(directory, name, text, general):
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
    return built, exe


def _run(directory, name, text, general):
    built, exe = _build(directory, name, text, general)
    if built.returncode != 0:
        return None, (built.stdout + built.stderr)[-3000:]
    got = subprocess.run([str(exe)], capture_output=True, timeout=120, cwd=directory)
    return (got.stdout.replace(b'\r\n', b'\n'), got.returncode), got.stderr.decode('utf-8', 'replace')[-1500:]


class Pre244Tests(unittest.TestCase):
    def matches(self, slug, text):
        with tempfile.TemporaryDirectory(prefix='ail-pre244-') as directory:
            want, want_rc, err = _cpython(directory, slug, text)
            self.assertEqual(want_rc, 0, err)
            for general in (True, False):
                got, build_err = _run(directory, '%s_%s' % (slug, 'g' if general else 'd'),
                                      text, general)
                self.assertIsNotNone(got, '%s (general=%s)\n%s' % (slug, general, build_err))
                self.assertEqual(got, (want, want_rc), '%s (general=%s)\n%s' % (slug, general, build_err))

    def test_walrus_and_delete_targets_are_local_bindings(self):
        for slug, text in PROGRAMS.items():
            self.matches(slug, text)

    def test_delete_of_known_function_is_refused_by_name(self):
        for slug, text in REFUSED.items():
            with tempfile.TemporaryDirectory(prefix='ail-pre244-') as directory:
                _cpython(directory, slug, text)
                for general in (True, False):
                    built, _exe = _build(directory, '%s_%s' % (slug, 'g' if general else 'd'),
                                         text, general)
                    self.assertNotEqual(built.returncode, 0,
                                        '%s (general=%s) compiled' % (slug, general))
                    self.assertIn('del on the function name', built.stdout + built.stderr,
                                  '%s (general=%s)' % (slug, general))


if __name__ == '__main__':
    unittest.main()

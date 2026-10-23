"""None (and other non-instances) reaching an attribute read, an attribute write, an augmented attribute write, a method call,
a subscript, `len`, an iteration or a call, against CPython 3.12 (DIFFERENCES C144).

An attribute read or write on a value that was not an instance read the value as an object pointer and crashed (exit 139,
the buffered stdout lost): `def f(x): return x.foo` called as `f(None)`. The general-path runtime (`ail_inst_getattr`, and
`ail_inst_setattr_chk` for the writes the emitter makes) now looks at the tag and raises AttributeError with CPython's text
(`'NoneType' object has no attribute 'foo'`, `'int' ...`, `'list' ...`); a user class instance that lacks the attribute is named
by its class. The subscript, `len`, iteration and call cases already raised CPython's TypeErrors (checked here, both builds).
The typed path is unchanged: a struct field read through `X | None` keeps DIFFERENCES A6 (RuntimeError, "field access on None").

Each program is built with the general path forced and with the default build; stdout, the exit status and the last
stderr line must equal CPython's.
"""
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent
CHATGPT = str(ROOT / 'ail_chatgpt.py')
HAVE_CC = shutil.which('gcc') is not None


def _last_line(err):
    lines = [x for x in err.decode('utf-8', 'replace').splitlines() if x.strip() and 'raised near' not in x]
    return lines[-1] if lines else ''


def _cpython(directory, name, text):
    src = Path(directory) / (name + '_cpython.py')
    src.write_text(text, encoding='utf-8')
    done = subprocess.run([sys.executable, '-B', str(src)], capture_output=True, timeout=120,
                          env=dict(os.environ, PYTHONUTF8='1', PYTHONWARNINGS='ignore'))
    return done.stdout.replace(b'\r\n', b'\n'), done.returncode, _last_line(done.stderr)


def _build_run(directory, name, text, mode):
    """mode: 'general' (forced), 'default', 'debug' (--debug, default path)."""
    src = Path(directory) / (name + '_' + mode + '.ail')
    src.write_text(text, encoding='utf-8')
    exe = Path(directory) / ('exe_' + name + '_' + mode)
    env = dict(os.environ, AIL_NO_CACHE='1', AIL_QUIET_FALLBACK='1')
    env.pop('AIL_NO_GENERAL', None)
    env.pop('AIL_UNIFIED_FORCE', None)
    if mode == 'general':
        env['AIL_UNIFIED_FORCE'] = '1'
    cmd = [sys.executable, '-B', CHATGPT, 'compile', src.name, '--syntax', 'python', '-o', exe.name]
    if mode == 'debug':
        cmd.append('--debug')
    built = subprocess.run(cmd, cwd=directory, capture_output=True, text=True, timeout=900, env=env)
    if built.returncode != 0:
        return None, (built.stdout + built.stderr)[-1500:]
    got = subprocess.run([str(exe)], capture_output=True, timeout=120, cwd=directory)
    return (got.stdout.replace(b'\r\n', b'\n'), got.returncode, _last_line(got.stderr)), ''


PROGRAMS = {
    'read_in_function': 'def f(x):\n    return x.foo\nprint("before")\ntry:\n    f(None)\nexcept AttributeError as e:\n    print("caught", e)\nf(None)\n',
    'write_in_function': 'def f(x):\n    x.foo = 1\nprint("before")\ntry:\n    f(None)\nexcept AttributeError as e:\n    print("caught", e)\nf(None)\n',
    'augassign': 'def f(x):\n    x.foo += 1\nprint("before")\ntry:\n    f(None)\nexcept AttributeError as e:\n    print("caught", e)\nf(None)\n',
    'method_on_instance_class': 'class A:\n    def __init__(self):\n        self.v = 1\n    def bar(self, k):\n        return self.v + k\ndef f(x):\n    return x.bar(1)\nprint(f(A()))\nprint("before")\ntry:\n    f(None)\nexcept AttributeError as e:\n    print("caught", e)\ntry:\n    f(5)\nexcept AttributeError as e:\n    print("caught", e)\ntry:\n    f("s")\nexcept AttributeError as e:\n    print("caught", e)\nf(None)\n',
    'subscript': 'def f(x):\n    return x[0]\nprint("before")\ntry:\n    f(None)\nexcept TypeError as e:\n    print("caught", e)\nf(None)\n',
    'item_assign': 'def f(x):\n    x[0] = 1\nprint("before")\ntry:\n    f(None)\nexcept TypeError as e:\n    print("caught", e)\nf(None)\n',
    'len': 'def f(x):\n    return len(x)\nprint("before")\ntry:\n    f(None)\nexcept TypeError as e:\n    print("caught", e)\nf(None)\n',
    'iteration': 'def f(x):\n    for i in x:\n        print(i)\nprint("before")\ntry:\n    f(None)\nexcept TypeError as e:\n    print("caught", e)\nf(None)\n',
    'call': 'def f(x):\n    return x(1)\nprint("before")\ntry:\n    f(None)\nexcept TypeError as e:\n    print("caught", e)\nf(None)\n',
    'value_kinds': 'class A:\n    def __init__(self):\n        self.v = 1\n\ndef rd(x):\n    return x.foo\n\ndef wr(x):\n    x.foo = 1\n\ndef aug(x):\n    x.foo += 1\n\nvals = [None, 5, 2.5, "s", [1], (1, 2), {"a": 1}, True, {1}]\nfor v in vals:\n    for name, fn in (("rd", rd), ("wr", wr), ("aug", aug)):\n        try:\n            fn(v)\n        except AttributeError as e:\n            print(name, type(e).__name__, e)\na = A()\nfor name, fn in (("rd", rd), ("wr", wr)):\n    try:\n        fn(a)\n        print(name, "ok", a.foo if name == "wr" else "")\n    except AttributeError as e:\n        print(name, "AttributeError")\nprint("before")\nrd(5)\n',
    'sources': 'from typing import Optional\n\nclass Node:\n    def __init__(self, v):\n        self.v = v\n        self.next = None\n        self.cb = None\n        self.items = None\n    def val(self):\n        return self.v\n    def nxt_val(self):\n        return self.next.v\n    def call_next(self):\n        return self.next.val()\n\nclass P:\n    def __init__(self):\n        self._x = 1\n    @property\n    def x(self):\n        return self._x\n    @x.setter\n    def x(self, v):\n        self._x = v\n\ndef none():\n    return None\n\ndef ident(x):\n    return x\n\ndef opt(x: Optional[Node]):\n    return x.v\n\ndef opt_set(x: Optional[Node]):\n    x.v = 9\n\ndef opt_call(x: Optional[Node]):\n    return x.val()\n\nd = {"a": Node(1)}\nlst = [Node(2), None]\nn = Node(3)\n\ndef setattr_(o):\n    o.v = 1\n\ndef forloop(o):\n    for i in o:\n        pass\n\ndef setitem_attr():\n    lst[1].v = 3\n\ndef check(name, t):\n    try:\n        t()\n        print(name, "no error")\n    except AttributeError as e:\n        print(name, "AttributeError", e)\n    except TypeError as e:\n        print(name, "TypeError", e)\n\ncheck("arg", lambda: ident(None).v)\ncheck("ret", lambda: none().v)\ncheck("dict.get", lambda: d.get("zz").v)\ncheck("list item", lambda: lst[1].v)\ncheck("attr", lambda: n.next.v)\ncheck("optional", lambda: opt(None))\ncheck("set arg", lambda: setattr_(None))\ncheck("opt set", lambda: opt_set(None))\ncheck("opt call", lambda: opt_call(None))\ncheck("method on attr", lambda: n.call_next())\ncheck("attr in method", lambda: n.nxt_val())\ncheck("meth list item", lambda: lst[1].val())\ncheck("meth dict get", lambda: d.get("q").val())\ncheck("meth ret", lambda: none().val())\ncheck("sub attr", lambda: n.items[0])\ncheck("len attr", lambda: len(n.items))\ncheck("iter attr", lambda: [i for i in n.items])\ncheck("call arg", lambda: ident(None)(1))\ncheck("call ret", lambda: none()())\ncheck("sub ret", lambda: none()[0])\ncheck("sub dictget", lambda: d.get("q")[0])\ncheck("len ret", lambda: len(none()))\ncheck("iter ret", lambda: list(none()))\ncheck("for ret", lambda: forloop(none()))\ncheck("attr of listitem set", lambda: setitem_attr())\ncheck("prop on None", lambda: ident(None).x)\np = P()\np.x = 5\nprint(p.x)\ntry:\n    none().x = 1\nexcept AttributeError as e:\n    print("prop set None", e)\nprint("before")\nlst[1].v\n',
    'optional_annotation': 'from typing import Optional\n\nclass Node:\n    def __init__(self, v: int):\n        self.v = v\n        self.next: Optional["Node"] = None\n    def val(self) -> int:\n        return self.v\n\ndef find(n: Optional[Node]) -> Optional[Node]:\n    return n.next\n\ndef getv(n: Optional[Node]) -> int:\n    return n.v\n\ndef callv(n: Optional[Node]) -> int:\n    return n.val()\n\ndef setv(n: Optional[Node]) -> None:\n    n.v = 3\n\ndef ret_none() -> Optional[Node]:\n    return None\n\na = Node(1)\nprint(getv(a), callv(a))\nfor fn in (getv, callv, find):\n    try:\n        fn(None)\n    except AttributeError as e:\n        print("caught", e)\ntry:\n    setv(None)\nexcept AttributeError as e:\n    print("caught", e)\ntry:\n    print(a.next.v)\nexcept AttributeError as e:\n    print("caught attr", e)\ntry:\n    ret_none().v\nexcept AttributeError as e:\n    print("caught ret", e)\ntry:\n    a.next.v = 4\nexcept AttributeError as e:\n    print("caught attrset", e)\ntry:\n    a.next.val()\nexcept AttributeError as e:\n    print("caught attrmeth", e)\nprint("before")\ngetv(None)\n',
    'dict_get_and_list_item': 'd = {"a": [1, 2]}\nl = [None, [1]]\ndef f(k):\n    return d.get(k)\ndef g(i):\n    return l[i]\nprint("start")\nfor fn in (lambda: f("zz").append(1), lambda: len(f("zz")), lambda: f("zz")[0], lambda: [x for x in f("zz")],\n           lambda: g(0).foo, lambda: g(0)[0], lambda: len(g(0)), lambda: g(0)(), lambda: f("zz").foo):\n    try:\n        fn()\n    except (AttributeError, TypeError) as e:\n        print(type(e).__name__, e)\nprint(f("a"), g(1))\nprint("before")\nf("zz").foo\n',
    'try_except': 'class N:\n    def __init__(self):\n        self.nxt = None\n        self.v = 1\n\ndef walk(n, k):\n    total = 0\n    for i in range(k):\n        try:\n            total += n.nxt.v\n        except AttributeError as e:\n            total += 100\n            print("caught", i, e)\n        finally:\n            total += 1\n    return total\n\ndef safe(x):\n    try:\n        x.foo = 1\n    except (AttributeError, TypeError) as e:\n        return "E:" + str(e)\n    return "ok"\n\ndef gen(items):\n    for it in items:\n        yield it.v\n\ndef outer(x):\n    def inner():\n        return x.v\n    return inner()\n\nn = N()\nprint(walk(n, 3))\nprint(safe(None), safe(n), safe(4))\ntry:\n    print(list(gen([n, None])))\nexcept AttributeError as e:\n    print("gen", e)\ntry:\n    outer(None)\nexcept Exception as e:\n    print(type(e).__name__, e)\ntry:\n    try:\n        n.nxt.v\n    except TypeError:\n        print("wrong")\nexcept AttributeError as e:\n    print("outer", e)\nn.nxt.v\n',
    'dunder_class': 'class V:\n    def __init__(self, x):\n        self.x = x\n    def __add__(self, o):\n        return V(self.x + o.x)\n    def __eq__(self, o):\n        return self.x == o.x\n\ndef rd(o):\n    return o.x\n\ndef check(name, t):\n    try:\n        t()\n        print(name, "no error")\n    except AttributeError as e:\n        print(name, "AttributeError", e)\n\ncheck("none", lambda: rd(None))\ncheck("int", lambda: rd(3))\ncheck("list", lambda: rd([1]))\ncheck("V", lambda: rd(V(1)))\ncheck("add none", lambda: V(1) + None)\nprint((V(1) + V(2)).x)\nprint("before")\nrd(None)\n',
    'instance_message': 'def ident(x):\n    return x\n\ndef check(name, t):\n    try:\n        t()\n        print(name, "no error")\n    except Exception as e:\n        print(name, type(e).__name__, e)\n\nclass K:\n    pass\n\ncheck("kattr", lambda: ident(K()).zz)\nprint("before")\nident(None).foo\n',
    'module_level': 'print("before")\nx = None\nx.foo\n',
    'flush_large': 'def f(x):\n    return x.foo\nfor i in range(3000):\n    print("line", i)\nprint("tail-no-newline", end="")\nf(None)\n',
    'flush_write': 'import sys\nclass A:\n    pass\ndef f(x):\n    x.foo = 3\nsys.stdout.write("partial")\nf(None)\n',
}


@unittest.skipUnless(HAVE_CC, 'gcc is required')
class NoneCrash(unittest.TestCase):
    def check(self, name, modes=('general', 'default')):
        text = PROGRAMS[name]
        with tempfile.TemporaryDirectory(prefix='ail-nonecrash-') as directory:
            want = _cpython(directory, name, text)
            self.assertEqual(want[1], 1, name)
            for mode in modes:
                got, err = _build_run(directory, name, text, mode)
                self.assertIsNotNone(got, '%s (%s)\n%s' % (name, mode, err))
                self.assertEqual(got, want, '%s (%s)' % (name, mode))


def _add(name):
    modes = ('general', 'default', 'debug') if name in ('read_in_function', 'write_in_function', 'flush_large') else ('general', 'default')
    setattr(NoneCrash, 'test_' + name, lambda self, name=name, modes=modes: self.check(name, modes))


for _name in PROGRAMS:
    _add(_name)


if __name__ == '__main__':
    unittest.main()

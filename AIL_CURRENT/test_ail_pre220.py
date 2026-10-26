"""Pre-220: `%` with a computed format string formats at run time.

The review of job rbrbmemsafe2 recorded a pre-existing difference: `fmt % value` where `fmt`
was not a literal (a name, an argument, a list item, an attribute or a dict value) raised
`TypeError: unsupported operand type(s) for %` on both builds, because only a literal str or
a tuple/dict right operand was routed to the run-time formatter.  A str left operand now
takes the formatter whatever the right operand is; a non-str left operand still takes the
ordinary `%` operator (`ail_op_mod`), so int/float/bool modulo, zero division and a user
class's `__mod__`/`__rmod__` are unchanged.

The cases below cover scalar and tuple right operands, every common directive, values that
reach the expression through an argument, a list item, an attribute, a dict value and an
alias, the int/float/bool/None boundaries and a user `__mod__`, on both builds.
"""
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent
CLI = str(ROOT / "ail_chatgpt.py")

PROGRAM = r'''def show(label, fn):
    try:
        print(label, repr(fn()))
    except Exception as e:
        print(label, type(e).__name__, str(e))


class Box:
    def __init__(self, v):
        self.v = v


class M:
    def __init__(self, v):
        self.v = v

    def __mod__(self, o):
        if isinstance(o, M):
            return "Mmod:M"
        return "Mmod:" + str(o)

    def __rmod__(self, o):
        return "Mrmod:" + str(o)


def apply(fmt, args):
    return fmt % args


def mod(a, b):
    return a % b


def main():
    fmts = ["%d", "%s", "%r", "%x", "%o", "%f", "%.2f", "%05d", "%s %d", "%c"]
    print("literal", "%d %s" % (3, "a"))
    for f in fmts:
        show("var-" + f, lambda f=f: f % 3)
    show("arg-scalar", lambda: apply("%d", 7))
    show("arg-tuple", lambda: apply("%s-%d", ("q", 2)))
    show("list-scalar", lambda: ["%s"][0] % "q")
    show("list-tuple", lambda: ["%s-%d"][0] % ("q", 2))
    box = Box("%05.2f")
    show("attr-scalar", lambda: box.v % 3.14159)
    box2 = Box("%s-%d")
    show("attr-tuple", lambda: box2.v % ("q", 2))
    d = {"f": "%d", "t": "%s/%r"}
    show("dict-scalar", lambda: d["f"] % 12)
    show("dict-tuple", lambda: d["t"] % ("a", None))
    alias = "%r"
    show("alias", lambda: alias % "q")
    show("tuple", lambda: "%d/%s/%r" % (1, "x", None))
    show("star", lambda: "%*d|%-*d|%.*f" % (5, 1, 4, 2, 2, 3.14159))
    show("mapping", lambda: "%(a)s" % {"a": 1})
    show("mapping05", lambda: "%(a)05d" % {"a": 7})
    show("percent", lambda: "100%%" % ())
    show("percent-arg", lambda: "100%%" % 3)
    show("literal-none", lambda: "%d" % None)
    for i, (fmt, args) in enumerate([
            ("%d", (3,)), ("%d", 3), ("%s", ("x",)), ("%s", "x"),
            ("%r", (None,)), ("%a", ("x",)), ("%i", (3,)), ("%u", (3,)),
            ("%x", (255,)), ("%X", (255,)), ("%o", (8,)), ("%e", (12.5,)),
            ("%E", (12.5,)), ("%g", (0.0001,)), ("%G", (1e20,)), ("%f", (1.5,)),
            ("%c", (65,)), ("%c", ("z",)), ("%5d", (3,)), ("%-5d|", (3,)),
            ("%05d", (3,)), ("%+d", (3,)), ("% d", (3,)), ("%.3d", (3,)),
            ("%#x", (255,)), ("%#o", (8,)), ("%5.2f", (3.14159,)),
            ("%*d", (5, 3)), ("%-*d", (5, 3)), ("%.*f", (2, 3.14159)),
            ("%*.*f", (8, 2, 3.14159)), ("%s %r %x", (1, "a", 255)),
            ("%", ()), ("%q", (1,)), ("%d", (1, 2)), ("%d %d", (1,)),
            ("%s", ([1, 2],)), ("%s", ({"a": 1},)), ("%s", (None,)),
            ("%r", ({1, 2},)), ("%d", ("x",)), ("%d", (1.9,)),
            ("%s", (b"q",))]):
        show("case%d-%r" % (i, fmt), lambda fmt=fmt, args=args: fmt % args)
    show("nested", lambda: ("%" + "s") % 5)
    for a in (-7, -1, 0, 1, 7, -(2 ** 62), 2 ** 62, True, False):
        for b in (-3, -1, 1, 3, 7, 2 ** 63 - 1):
            show("int-%r-%r" % (a, b), lambda a=a, b=b: a % b)
    show("int-zero", lambda: 7 % 0)
    show("int-arg", lambda: mod(-7, 3))
    show("int-list", lambda: [-7, 3][0] % [5][0])
    ibox = Box(9)
    show("int-attr", lambda: ibox.v % 4)
    idict = {"a": -9, "b": 4}
    show("int-dict", lambda: idict["a"] % idict["b"])
    show("floats", lambda: (7.5 % 2, -7.5 % 2, 7.5 % -2, 7.5 % 2.5,
                            -0.0 % 2.0))
    show("mix", lambda: (7 % 2.5, 7.5 % 2, True % 2.5, 2.5 % True))
    show("float-zero", lambda: 7.5 % 0.0)
    show("bool", lambda: (True % 2, 5 % True, False % 2, 2 % False))
    try:
        None % 2
    except TypeError:
        print("none", "TypeError")
    try:
        2 % None
    except TypeError:
        print("none-r", "TypeError")
    m = M(1)
    show("user", lambda: m % 3)
    show("user-r", lambda: 3 % m)
    show("user-user", lambda: m % M(2))
    malias = m
    show("user-alias", lambda: malias % 4)
    print("done")


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


class Pre220Tests(unittest.TestCase):
    def check(self, slug, text):
        with tempfile.TemporaryDirectory(prefix='ail-pre220-') as directory:
            want = _cpython(directory, slug, text)
            for general in (True, False):
                got, err = _build_and_run(directory, '%s_%s' % (slug, 'g' if general else 'd'),
                                          text, general)
                self.assertIsNotNone(got, '%s (general=%s)\n%s' % (slug, general, err))
                self.assertEqual(got, want, '%s (general=%s)\n%s' % (slug, general, err))

    def test_computed_percent_format(self):
        self.check('computed_percent', PROGRAM)


if __name__ == '__main__':
    unittest.main()

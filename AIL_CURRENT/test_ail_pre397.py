"""An ``__index__`` result that is an IntEnum / IntFlag member (job pre397).

The pre379 review recorded ``p6_enumret`` as pre-existing: CPython accepts an ``__index__``
method that returns an IntEnum member (an IntEnum subclasses int), while both AIL builds raised
``TypeError: list indices must be integers or slices, not instance``.  The general-path
``__index__`` result is now unwrapped through the member's integer ``value`` wherever an index
is converted: list/tuple/str subscription, range(), round()'s ndigits, str and bytes search
bounds and list.index bounds.  CPython never calls an IntEnum member's own (possibly overridden)
``__index__`` for such a result, so neither does AIL: an override that returns a different value
or raises is ignored.  Direct IntEnum/IntFlag subscriptions already worked and keep working; a
plain object whose ``__index__`` returns a non-int (a str, None, another object with
``__index__``, a StrEnum or a plain Enum) stays a TypeError.  Values reach the conversion
through a variable, an argument, a list item, an attribute and a dict value.

The other pre379 items (``E.A *= [1,2]``, ``list *= IntEnum`` aliasing and
``d.keys() * 2`` / genexpr ``* 2``) are not changed here.
"""
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent

GETITEM = r'''import enum


class E(enum.IntEnum):
    ZERO = 0
    A = 3
    NEG = -1
    BIG = 1000


class F(enum.IntFlag):
    X = 1
    Y = 2


class S(enum.StrEnum):
    A = "a"


class G(enum.Enum):
    A = 1


class C:
    def __init__(self, v):
        self.v = v

    def __index__(self):
        return self.v


class Other:
    def __index__(self):
        return 5


class RetOther:
    def __index__(self):
        return Other()


class Box:
    pass


def show(tag, f):
    try:
        print(tag, repr(f()))
    except Exception as e:
        print(tag, type(e).__name__, str(e))


def show_type(tag, f):
    try:
        print(tag, repr(f()))
    except Exception as e:
        print(tag, type(e).__name__)


def via(tag, x):
    show(tag + "-list", lambda: [10, 20, 30, 40][x])
    show(tag + "-tuple", lambda: (10, 20, 30, 40)[x])
    show(tag + "-str", lambda: "abcd"[x])


def main():
    for v in (E.ZERO, E.A, E.NEG, F.X, F.Y):
        via("direct-" + repr(v), v)
    for v in (E.ZERO, E.A, E.NEG, E.BIG, F.X):
        via("ret-" + repr(v), C(v))
    show("empty-direct", lambda: [][E.ZERO])
    show("empty-ret", lambda: [][C(E.ZERO)])
    show("neg-direct", lambda: [10, 20, 30, 40][E.NEG])
    show("neg-ret", lambda: [10, 20, 30, 40][C(E.NEG)])
    show("big-direct", lambda: [10, 20, 30, 40][E.BIG])
    show("big-ret", lambda: [10, 20, 30, 40][C(E.BIG)])

    def take(x):
        print("arg", [10, 20, 30, 40][x])

    take(C(E.A))
    print("listitem", [10, 20, 30, 40][[C(E.A)][0]])
    box = Box()
    box.i = C(E.A)
    print("attr", [10, 20, 30, 40][box.i])
    print("dict", [10, 20, 30, 40][{"i": C(E.A)}["i"]])

    show_type("bad-str", lambda: [10, 20, 30, 40][C("x")])
    show_type("bad-none", lambda: [10, 20, 30, 40][C(None)])
    show_type("bad-other", lambda: [10, 20, 30, 40][RetOther()])
    show_type("strenum-ret", lambda: [10, 20, 30, 40][C(S.A)])
    show_type("enum-ret", lambda: [10, 20, 30, 40][C(G.A)])
    show_type("strenum-direct", lambda: [10, 20, 30, 40][S.A])
    show_type("enum-direct", lambda: [10, 20, 30, 40][G.A])
    print("done")


main()
'''

INDEX_CONTEXTS = r'''import enum


class E(enum.IntEnum):
    ZERO = 0
    ONE = 1
    TWO = 2
    NEG = -1


class C:
    def __init__(self, v):
        self.v = v

    def __index__(self):
        return self.v


class Box:
    pass


def show(tag, f):
    try:
        print(tag, repr(f()))
    except Exception as e:
        print(tag, type(e).__name__, str(e))


def main():
    for v in (E.ZERO, E.ONE, E.TWO, E.NEG):
        c = C(v)
        show("range1-" + repr(v), lambda c=c: list(range(c)))
        show("range2-" + repr(v), lambda c=c: list(range(0, c)))
        show("range3-" + repr(v), lambda c=c: list(range(10, c, 2)))
        show("round-" + repr(v), lambda c=c: round(2.34567, c))
        show("find-" + repr(v), lambda c=c: "abcabcabc".find("a", c))
        show("findhi-" + repr(v), lambda c=c: "abcabcabc".find("a", 0, c))
        show("bfind-" + repr(v), lambda c=c: b"abcabcabc".find(b"a", c))
        show("bfindhi-" + repr(v), lambda c=c: b"abcabcabc".find(b"a", 0, c))
        show("lindex-" + repr(v), lambda c=c: [1, 2, 3, 4].index(3, c))
        show("lindexhi-" + repr(v), lambda c=c: [1, 2, 3, 4].index(3, 0, c))
    for v in (E.ZERO, E.ONE, E.TWO):
        box = Box()
        box.i = C(v)
        print("attr-range", list(range(box.i)))
        print("dict-round", round(2.34567, {"n": C(v)}["n"]))
        print("listitem-find", "abcabcabc".find("a", [C(v)][0]))

        def take(x):
            print("arg-round", round(2.34567, x))

        take(C(v))
    print("done")


main()
'''


OVERRIDDEN_INDEX = r'''import enum


class E(enum.IntEnum):
    ZERO = 0
    ONE = 1
    TWO = 2
    NEG = -1

    def __index__(self):
        return 999


class F(enum.IntFlag):
    A = 1
    B = 2

    def __index__(self):
        return 7


class R(enum.IntEnum):
    A = 5

    def __index__(self):
        raise ValueError("boom")


class C:
    def __init__(self, v):
        self.v = v

    def __index__(self):
        return self.v


class Box:
    pass


def show(tag, f):
    try:
        print(tag, repr(f()))
    except Exception as e:
        print(tag, type(e).__name__, str(e))


def take(x):
    print("arg", [10, 20, 30, 40][x])


def main():
    for v in (E.ZERO, E.ONE, E.NEG, F.B):
        c = C(v)
        show("list-" + repr(v), lambda c=c: [10, 20, 30, 40][c])
        show("tuple-" + repr(v), lambda c=c: (10, 20, 30, 40)[c])
        show("str-" + repr(v), lambda c=c: "abcd"[c])
        show("item-" + repr(v), lambda c=c: [10, 20, 30, 40][[c][0]])
        box = Box()
        box.i = c
        show("attr-" + repr(v), lambda box=box: [10, 20, 30, 40][box.i])
        show("dict-" + repr(v), lambda c=c: [10, 20, 30, 40][{"i": c}["i"]])
        take(c)
    show("empty", lambda: [][C(E.ZERO)])
    for v in (E.ZERO, E.ONE, E.TWO, E.NEG):
        c = C(v)
        show("range1-" + repr(v), lambda c=c: list(range(c)))
        show("range2-" + repr(v), lambda c=c: list(range(0, c)))
        show("find-" + repr(v), lambda c=c: "abcabcabc".find("a", c))
        show("bfind-" + repr(v), lambda c=c: b"abcabcabc".find(b"a", c))
        show("lindex-" + repr(v), lambda c=c: [1, 2, 3, 4].index(3, c))
        show("round-" + repr(v), lambda c=c: round(2.34567, c))
    show("raise-list", lambda: [10, 20, 30][C(R.A)])
    show("raise-range", lambda: list(range(C(R.A))))
    show("raise-round", lambda: round(2.34567, C(R.A)))
    print("done")


main()
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
    exe = Path(directory) / ('exe_' + name)
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


class Pre397Tests(unittest.TestCase):
    def check(self, slug, text):
        with tempfile.TemporaryDirectory(prefix='ail-pre397-') as directory:
            want, want_rc, err = _cpython(directory, slug, text)
            self.assertEqual(want_rc, 0, err)
            for general in (True, False):
                got, build_err = _build_and_run(directory, '%s_%s' % (slug, 'g' if general else 'd'), text, general)
                self.assertIsNotNone(got, '%s (general=%s)\n%s' % (text[:2000], general, build_err))
                self.assertEqual(got, (want, want_rc), '%s (general=%s)\n%s' % (text[:2000], general, build_err))

    def test_intenum_returned_from_index_is_an_index(self):
        self.check('getitem', GETITEM)

    def test_intenum_returned_from_index_in_other_index_contexts(self):
        self.check('contexts', INDEX_CONTEXTS)

    def test_overridden_index_on_returned_member_is_not_called(self):
        self.check('override', OVERRIDDEN_INDEX)


if __name__ == '__main__':
    unittest.main()

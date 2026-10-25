"""pre234: list.index/count propagate an exception raised by a user __eq__.

The review of job pre216 recorded this pre-existing difference (the ``r7_raise_eq`` probe):
``[Boom()].index(x)`` and ``[Boom()].count(x)`` swallowed the ``RuntimeError`` raised by
``Boom.__eq__`` and reported ``ValueError: <Boom object> is not in list`` / ``0``, where CPython
lets the exception through.  Sequence search now uses ``PyObject_RichCompareBool``'s rule:
identity first, then ``==`` (dispatching the user method and keeping its error).  This also covers
``tuple.index``/``count``, which share the same search.

The cases below cover an error on the first and a later element, a bounded and a negative window,
identity short-circuiting the call, equality/reflection returning True or False, empty lists,
strings/ints/None, and a value reaching the search through an argument, a list item, an attribute
and a dict value, on both builds.  A program without classes still compiles, as before.
"""
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent
CLI = str(ROOT / "ail_chatgpt.py")

PROGRAM = r'''class Boom:
    def __init__(self, tag):
        self.tag = tag

    def __eq__(self, other):
        raise RuntimeError("boom-" + self.tag)


class Eq:
    def __init__(self, n):
        self.n = n

    def __eq__(self, other):
        return bool(other == self.n)


class Ref:
    def __init__(self, n):
        self.n = n


class Left:
    def __init__(self, n):
        self.n = n

    def __eq__(self, other):
        if isinstance(other, Ref):
            return bool(other.n == self.n)
        return False


class Box:
    def __init__(self, xs, q):
        self.xs = xs
        self.q = q


def show(label, fn):
    try:
        print(label, "ok", fn())
    except Exception as e:
        print(label, type(e).__name__, str(e))


def look(xs, q):
    return (xs.index(q), xs.count(q))


def main():
    show("empty-i", lambda: [].index(1))
    show("empty-c", lambda: [].count(1))
    show("ints-i", lambda: [1, 2, 3].index(2))
    show("ints-c", lambda: [1, 2, 3].count(2))
    show("strs-i", lambda: ["a", "b"].index("c"))
    show("strs-c", lambda: ["a", "b"].count("c"))
    show("none-i", lambda: [None, None].index(None))
    show("none-c", lambda: [None, None].count(None))

    show("boom-i", lambda: [Boom("a")].index(Eq(1)))
    show("boom-c", lambda: [Boom("a")].count(Eq(1)))
    show("boom-late-i", lambda: [Eq(1), Boom("b")].index(Eq(1)))
    show("boom-late-c", lambda: [Eq(1), Boom("b")].count(Eq(1)))
    show("boom-window-i", lambda: [Boom("a"), Eq(2)].index(Eq(2), 1))
    show("boom-window-c", lambda: [Boom("a"), Eq(2), Eq(2)].count(Eq(2), 1, 3))
    show("neg-window-i", lambda: [Eq(1), Boom("a"), Eq(3)].index(Eq(3), -1))
    show("neg-window-c", lambda: [Eq(1), Boom("a"), Eq(3)].count(Eq(3), -1))

    b = Boom("self")
    same = [b]
    show("same-i", lambda: same.index(b))
    show("same-c", lambda: same.count(b))

    e = Eq(4)
    xs = [1, e, 3]
    show("eq-i", lambda: xs.index(Eq(4)))
    show("eq-c", lambda: xs.count(Eq(4)))
    show("arg", lambda: look(xs, Eq(4)))
    box = Box(xs, Eq(4))
    show("attr", lambda: look(box.xs, box.q))
    d = {"xs": xs, "q": Eq(4)}
    show("dict", lambda: look(d["xs"], d["q"]))
    show("list", lambda: look([xs][0], [Eq(4)][0]))

    show("reflect-i", lambda: [Left(5)].index(Ref(5)))
    show("reflect-c", lambda: [Left(5)].count(Ref(5)))

    tb = (Eq(1), Boom("t"))
    show("tuple-i", lambda: tb.index(Eq(1)))
    show("tuple-c", lambda: tb.count(Eq(1)))
    show("tuple-boom-i", lambda: (Boom("t"),).index(Eq(1)))
    show("tuple-boom-c", lambda: (Boom("t"),).count(Eq(1)))


main()
'''

NO_CLASS = r'''def main():
    xs = [1, 2, 3, 2]
    print(xs.index(2), xs.count(2))
    try:
        print(xs.index(9))
    except ValueError as e:
        print(type(e).__name__, str(e))
    print("a b a".count("a"), "abc".index("b"))


main()
'''


def _run(directory, name, text, general):
    src = Path(directory) / (name + '.py')
    src.write_text(text, encoding='utf-8')
    exe = Path(directory) / ('exe_' + name + ('_g' if general else '_d'))
    env = dict(os.environ, AIL_NO_CACHE='1', AIL_QUIET_FALLBACK='1')
    env.pop('AIL_UNIFIED_FORCE', None)
    if general:
        env['AIL_UNIFIED_FORCE'] = '1'
    built = subprocess.run([sys.executable, '-B', CLI, 'compile', src.name,
                            '--syntax', 'python', '-o', exe.name], cwd=directory,
                           capture_output=True, text=True, timeout=900, env=env)
    if built.returncode != 0:
        return None, built.stdout + built.stderr
    done = subprocess.run([str(exe)], cwd=directory, capture_output=True, text=True, timeout=120)
    return done, ''


def _cpython(directory, name, text):
    src = Path(directory) / (name + '_cpython.py')
    src.write_text(text, encoding='utf-8')
    return subprocess.run([sys.executable, '-B', str(src)], capture_output=True, text=True,
                          timeout=120, cwd=directory)


class Pre234Tests(unittest.TestCase):
    def check(self, slug, text):
        with tempfile.TemporaryDirectory(prefix='ail-pre234-') as directory:
            py = _cpython(directory, slug, text)
            self.assertEqual(py.returncode, 0, py.stderr)
            for general in (True, False):
                got, err = _run(directory, '%s_%s' % (slug, 'g' if general else 'd'), text, general)
                self.assertIsNotNone(got, '%s (general=%s)\n%s' % (slug, general, err))
                self.assertEqual(got.stdout.replace('\r\n', '\n'), py.stdout.replace('\r\n', '\n'),
                                 '%s (general=%s)\n%s' % (slug, general, err))
                self.assertEqual(got.returncode, py.returncode, '%s (general=%s)' % (slug, general))

    def test_list_index_count_propagate_eq_errors(self):
        self.check('eq_errors', PROGRAM)

    def test_program_without_classes_still_builds(self):
        self.check('no_class', NO_CLASS)

    def test_program_without_index_count_keeps_its_c(self):
        text = 'def main():\n    xs = [1, 2, 3]\n    print(len(xs), xs[1], sum(xs))\n\nmain()\n'
        with tempfile.TemporaryDirectory(prefix='ail-pre234-c-') as directory:
            src = Path(directory) / 'nofeature.py'
            src.write_text(text, encoding='utf-8')
            for general in (True, False):
                debug = Path(directory) / ('debug_' + ('g' if general else 'd'))
                env = dict(os.environ, AIL_NO_CACHE='1', AIL_QUIET_FALLBACK='1')
                env.pop('AIL_UNIFIED_FORCE', None)
                if general:
                    env['AIL_UNIFIED_FORCE'] = '1'
                built = subprocess.run(
                    [sys.executable, '-B', CLI, 'compile', src.name, '--syntax', 'python',
                     '-o', 'exe', '--debug-dir', str(debug)],
                    cwd=directory, capture_output=True, text=True, timeout=900, env=env)
                self.assertEqual(built.returncode, 0, built.stdout + built.stderr)
                program_c = (debug / 'program.c').read_text(encoding='utf-8')
                self.assertNotIn('ail__member_eq_st', program_c, 'general=%s' % general)
                self.assertNotIn('ail_meth_list_index_st', program_c, 'general=%s' % general)



if __name__ == '__main__':
    unittest.main()

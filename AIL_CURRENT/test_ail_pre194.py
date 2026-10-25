"""pre194: the itertools choosers convert r the way CPython 3.12 does.

`permutations` materializes its pool first and then requires r to be an int or a
bool (None means "all of them"); a float, str, list or instance is
`TypeError: Expected int as r`.  `combinations` and
`combinations_with_replacement` convert r with `__index__` before the pool is
materialized and name the value's type when it is not an index; a negative r is
only rejected after the pool.  The general path used to read the raw int field
of r, so a float or str produced an empty result (and an explicit None produced
`[()]`), and the typed path accepted a statically known non-int r too.

The programs cover every type, the boundaries around 0 and the pool size,
keyword arguments, values reaching the call through an argument, a list item,
an attribute and a dict value, `__index__` that returns an int, a bool, a
non-int or raises, evaluation order against a generator pool, and for loops.
Each program is built on both builds and compared with CPython.
"""
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent


TYPES = r'''import itertools


def show(label, fn):
    try:
        print(label, fn())
    except Exception as e:
        print(label, type(e).__name__, str(e))


def call(which, xs, r):
    if which == 0:
        return list(itertools.permutations(xs, r))
    if which == 1:
        return list(itertools.combinations(xs, r))
    return list(itertools.combinations_with_replacement(xs, r))


def run():
    xs = [1, 2, 3]
    for which in (0, 1, 2):
        show("w%d-float" % which, lambda which=which: call(which, xs, 2.0))
        show("w%d-float25" % which, lambda which=which: call(which, xs, 2.5))
        show("w%d-str" % which, lambda which=which: call(which, xs, "2"))
        show("w%d-list" % which, lambda which=which: call(which, xs, [2]))
        show("w%d-none" % which, lambda which=which: call(which, xs, None))
        show("w%d-true" % which, lambda which=which: call(which, xs, True))
        show("w%d-false" % which, lambda which=which: call(which, xs, False))
        show("w%d-zero" % which, lambda which=which: call(which, xs, 0))
        show("w%d-one" % which, lambda which=which: call(which, xs, 1))
        show("w%d-two" % which, lambda which=which: call(which, xs, 2))
        show("w%d-n" % which, lambda which=which: call(which, xs, 3))
        show("w%d-gt" % which, lambda which=which: call(which, xs, 4))
        show("w%d-neg" % which, lambda which=which: call(which, xs, -1))
        show("w%d-min" % which, lambda which=which: call(which, xs, -9223372036854775807))


run()
'''

INDEX = r'''import itertools


class Idx:
    def __init__(self, v):
        self.v = v

    def __index__(self):
        return self.v


class Bad:
    def __index__(self):
        return 2.0


class BadNone:
    def __index__(self):
        return None


class Boom:
    def __index__(self):
        raise KeyError("boom")


class IdxBool:
    def __index__(self):
        return True


class Box:
    def __init__(self, r):
        self.r = r


def show(label, fn):
    try:
        print(label, fn())
    except Exception as e:
        print(label, type(e).__name__, str(e))


def pick(which, xs, r):
    if which == 0:
        return list(itertools.permutations(xs, r))
    if which == 1:
        return list(itertools.combinations(xs, r))
    return list(itertools.combinations_with_replacement(xs, r))


def run():
    xs = [1, 2, 3]
    d = {"r": Idx(2), "bad": Bad(), "f": 1.5}
    items = [Idx(1), Bad(), IdxBool()]
    b = Box(Idx(2))
    for which in (0, 1, 2):
        show("w%d-idx" % which, lambda which=which: pick(which, xs, Idx(2)))
        show("w%d-bad" % which, lambda which=which: pick(which, xs, Bad()))
        show("w%d-badnone" % which, lambda which=which: pick(which, xs, BadNone()))
        show("w%d-boom" % which, lambda which=which: pick(which, xs, Boom()))
        show("w%d-idxtrue" % which, lambda which=which: pick(which, xs, IdxBool()))
        show("w%d-arg" % which, lambda which=which: pick(which, xs, Idx(3)))
        show("w%d-list" % which, lambda which=which: pick(which, xs, items[1]))
        show("w%d-dict" % which, lambda which=which: pick(which, xs, d["r"]))
        show("w%d-attr" % which, lambda which=which: pick(which, xs, b.r))


run()
'''

ORDER = r'''import itertools


def show(label, fn):
    try:
        print(label, fn())
    except Exception as e:
        print(label, type(e).__name__, str(e))


def gen(log):
    log.append("iter")
    yield 1
    yield 2


def run():
    show("p-bad-noniter", lambda: list(itertools.permutations(5, 2.0)))
    show("p-neg-noniter", lambda: list(itertools.permutations(5, -1)))
    show("c-bad-noniter", lambda: list(itertools.combinations(5, 2.0)))
    show("c-neg-noniter", lambda: list(itertools.combinations(5, -1)))
    show("w-bad-noniter", lambda: list(itertools.combinations_with_replacement(5, 2.0)))
    show("w-neg-noniter", lambda: list(itertools.combinations_with_replacement(5, -1)))
    log = []
    show("p-gen-bad", lambda: list(itertools.permutations(gen(log), 1.5)))
    print("p-log", log)
    log = []
    show("p-gen-neg", lambda: list(itertools.permutations(gen(log), -1)))
    print("p-neglog", log)
    log = []
    show("c-gen-bad", lambda: list(itertools.combinations(gen(log), 1.5)))
    print("c-log", log)
    log = []
    show("c-gen-neg", lambda: list(itertools.combinations(gen(log), -1)))
    print("c-neglog", log)
    log = []
    show("w-gen-bad", lambda: list(itertools.combinations_with_replacement(gen(log), 1.5)))
    print("w-log", log)
    log = []
    show("w-gen-neg", lambda: list(itertools.combinations_with_replacement(gen(log), -1)))
    print("w-neglog", log)


run()
'''

LOOPS = r'''import itertools


class Idx:
    def __init__(self, v):
        self.v = v

    def __index__(self):
        return self.v


def show(label, fn):
    try:
        print(label, fn())
    except Exception as e:
        print(label, type(e).__name__, str(e))


def loop(which, xs, r):
    out = []
    if which == 0:
        for p in itertools.permutations(xs, r):
            out.append(p)
    elif which == 1:
        for p in itertools.combinations(xs, r):
            out.append(p)
    else:
        for p in itertools.combinations_with_replacement(xs, r):
            out.append(p)
    return out


def run():
    xs = [1, 2, 3]
    for which in (0, 1, 2):
        show("w%d-int" % which, lambda which=which: loop(which, xs, 2))
        show("w%d-zero" % which, lambda which=which: loop(which, xs, 0))
        show("w%d-float" % which, lambda which=which: loop(which, xs, 1.5))
        show("w%d-str" % which, lambda which=which: loop(which, xs, "2"))
        show("w%d-none" % which, lambda which=which: loop(which, xs, None))
        show("w%d-idx" % which, lambda which=which: loop(which, xs, Idx(2)))
        show("w%d-neg" % which, lambda which=which: loop(which, xs, -1))


run()
'''

LITERAL_NONE = r'''import itertools


def show(label, fn):
    try:
        print(label, fn())
    except Exception as e:
        print(label, type(e).__name__, str(e))


def p_loop(xs):
    for a in itertools.permutations(xs, None):
        pass


def c_loop(xs):
    for a in itertools.combinations(xs, None):
        pass


def w_loop(xs):
    for a in itertools.combinations_with_replacement(xs, None):
        pass


def c_unpack(xs):
    for a, b in itertools.combinations(xs, None):
        pass


def w_unpack(xs):
    for a, b in itertools.combinations_with_replacement(xs, None):
        pass


def run():
    xs = [1, 2, 3]
    show("p-pos", lambda: list(itertools.permutations(xs, None)))
    show("c-pos", lambda: list(itertools.combinations(xs, None)))
    show("w-pos", lambda: list(itertools.combinations_with_replacement(xs, None)))
    show("p-kw", lambda: list(itertools.permutations(xs, r=None)))
    show("c-kw", lambda: list(itertools.combinations(xs, r=None)))
    show("w-kw", lambda: list(itertools.combinations_with_replacement(xs, r=None)))
    show("p-loop", lambda: p_loop(xs))
    show("c-loop", lambda: c_loop(xs))
    show("w-loop", lambda: w_loop(xs))
    show("c-unpack", lambda: c_unpack(xs))
    show("w-unpack", lambda: w_unpack(xs))
    show("c-empty", lambda: list(itertools.combinations([], None)))
    show("w-empty", lambda: list(itertools.combinations_with_replacement([], None)))


run()
'''

LONGNAME = r'''import itertools


class Cxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx:
    pass


class Box:
    def __init__(self, r):
        self.r = r


class Bad:
    def __index__(self):
        return Cxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx()


def show(label, fn):
    try:
        print(label, fn())
    except Exception as e:
        print(label, type(e).__name__, str(e))


def run():
    xs = [1, 2, 3]
    inst = Cxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx()
    box = Box(inst)
    show("c-direct", lambda: list(itertools.combinations(xs, inst)))
    show("w-direct", lambda: list(itertools.combinations_with_replacement(xs, inst)))
    show("c-arg", lambda: (lambda r: list(itertools.combinations(xs, r)))(inst))
    show("c-list", lambda: list(itertools.combinations(xs, [inst][0])))
    show("c-attr", lambda: list(itertools.combinations(xs, box.r)))
    show("c-dict", lambda: list(itertools.combinations(xs, {"r": inst}["r"])))
    show("c-badindex", lambda: list(itertools.combinations(xs, Bad())))
    show("w-badindex", lambda: list(itertools.combinations_with_replacement(xs, Bad())))


run()
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


class Pre194Tests(unittest.TestCase):
    def check(self, slug, text):
        with tempfile.TemporaryDirectory(prefix='ail-pre194-') as directory:
            want, rc, err = _cpython(directory, slug, text)
            self.assertEqual(rc, 0, err)
            for general in (True, False):
                got, build_err = _build_and_run(directory, '%s_%s' % (slug, 'g' if general else 'd'),
                                                text, general)
                self.assertIsNotNone(got, '%s (general=%s)\n%s' % (text[:2000], general, build_err))
                self.assertEqual(got[0], want, '%s (general=%s)\n%s' % (text[:2000], general, build_err))
                self.assertEqual(got[1], rc, '%s (general=%s)\n%s' % (text[:2000], general, build_err))

    def test_types_and_bounds(self):
        self.check('types', TYPES)

    def test_index_and_routes(self):
        self.check('index', INDEX)

    def test_order(self):
        self.check('order', ORDER)

    def test_for_loops(self):
        self.check('loops', LOOPS)

    def test_literal_none(self):
        self.check('literal_none', LITERAL_NONE)

    def test_long_type_name(self):
        self.check('longname', LONGNAME)


if __name__ == '__main__':
    unittest.main()

"""Differential round 25: a non-int slice bound is CPython's TypeError, not index 0.

Found with small programs compared against CPython on both builds:

`"abcdef"[v:]` for a `v` that is not an int, bool, or None read the bound's
payload as the integer 0 (the general path took `(v).i` without looking at the
tag), so `v = 1.0`, `"1"`, `[1]` or `(1,)` silently printed a slice instead of
raising.  CPython evaluates the bound and raises

    TypeError: slice indices must be integers or None or have an __index__ method

The general emitter now checks each supplied bound's tag, keeps None as the
omitted bound (has_lo / has_hi / has_step = 0), and raises CPython's TypeError
for every other non-int value.  The same check covers str, list and tuple
slices, a step of a wrong type, and a bound that reaches the slice through a
variable, a function argument, a list item, a dict value or an attribute.
"""
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent

WRONG_BOUNDS = r'''class C:
    pass


def cut(xs, lo, hi):
    return xs[lo:hi]


def stepped(xs, lo, hi, st):
    return xs[lo:hi:st]


def main() -> None:
    c = C()
    c.lo = 1.0
    c.hi = 2
    d = {"lo": [1], "hi": 2, "st": "1"}
    xs = ["0", "1", "2", "3", "4"]
    ys = (0, 1, 2, 3, 4)
    for xs_ in (xs, ys):
        for v in [1.0, "1", [1], (1,), {"a": 1}]:
            try:
                print("get", repr(xs_[v:]))
            except TypeError:
                print("get TypeError", type(v).__name__)
            try:
                print("get2", repr(xs_[:v]))
            except TypeError:
                print("get2 TypeError", type(v).__name__)
            try:
                print("cut", repr(cut(xs_, 0, v)))
            except TypeError:
                print("cut TypeError", type(v).__name__)
            try:
                print("step", repr(stepped(xs_, 0, 2, v)))
            except TypeError:
                print("step TypeError", type(v).__name__)
    try:
        print("attr", repr(xs[c.lo:c.hi]))
    except TypeError:
        print("attr TypeError")
    try:
        print("dict", repr(xs[d["lo"]:d["hi"]]))
    except TypeError:
        print("dict TypeError")
    try:
        print("dictstep", repr(xs[0:2:d["st"]]))
    except TypeError:
        print("dictstep TypeError")
    for v in [None, True, False, -100, 100]:
        print("ok", repr(v), repr(xs[v:]), repr(ys[:v]), repr(xs[v:v]))
    print("done")


main()
'''

BOUND_SOURCES = r'''class C:
    pass


def show(s: str, lo, hi, st) -> None:
    print(repr(s[lo:hi]), repr(s[lo:hi:st]))


def main() -> None:
    s: str = "abcdef"
    c = C()
    c.lo = None
    c.hi = -1
    xs = [None, 0, 2, 5, -1]
    d = {"lo": None, "hi": None, "st": -1}
    show(s, None, None, 1)
    show(s, -100, 100, -2)
    show(s, 100, -100, 1)
    show(s, c.lo, c.hi, -1)
    show(s, xs[0], xs[4], xs[2])
    show(s, d["lo"], d["hi"], d["st"])
    show("", None, None, -1)
    show("aé", None, None, -1)
    print(repr(s[::-1]), repr(s[::0 if False else 1]))
    print("done")


main()
'''


STALE_BOUND_KIND = r"""def main() -> None:
    s = "abcdef"
    x = 2
    if False:
        x = None
    print(repr(s[x:]), repr(s[:x]))
    y = 3
    while False:
        y = None
    print(repr(s[y:]), repr(s[:y]))
    z = 1
    for _ in range(0):
        z = None
    print(repr(s[z:]), repr(s[:z]))
    t = 2
    if False:
        t = 1.5
    print(repr(s[t:]), repr(s[:t]))
    u = 2
    if False:
        u = "x"
    print(repr(s[u:]), repr(s[:u]))
    for flag in (False, True):
        v = 2
        if flag:
            v = None
        print("none", repr(s[v:]))
        w = 2
        if flag:
            w = 1.5
        try:
            print("float", repr(s[:w]))
        except TypeError:
            print("float TypeError")
    print(repr(["a", "b", "c", "d"][x:]), repr(("a", "b", "c", "d")[:x]))


main()
"""


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


class Fuzz25Tests(unittest.TestCase):
    def check(self, slug, text, rc=0):
        with tempfile.TemporaryDirectory(prefix='ail-fuzz25-') as directory:
            want, got_rc, err = _cpython(directory, slug, text)
            self.assertEqual(got_rc, rc, err)
            for general in (True, False):
                got, build_err = _build_and_run(directory, '%s_%s' % (slug, 'g' if general else 'd'), text, general)
                self.assertIsNotNone(got, '%s (general=%s)\n%s' % (text[:2000], general, build_err))
                self.assertEqual(got, (want, rc), '%s (general=%s)\n%s' % (text[:2000], general, build_err))

    def test_wrong_typed_slice_bounds(self):
        self.check('wrong_bounds', WRONG_BOUNDS)

    def test_slice_bounds_from_sources(self):
        self.check('bound_sources', BOUND_SOURCES)

    def test_stale_bound_kind_from_unreachable_branch(self):
        self.check('stale_bound_kind', STALE_BOUND_KIND)


if __name__ == '__main__':
    unittest.main()

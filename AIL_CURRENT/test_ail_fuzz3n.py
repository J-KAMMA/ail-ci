"""Differential round 3n: a None start/end of a str search is CPython's default bound.

Found with small random programs compared against CPython on both builds:

`None` passed as the start or end of `str.find`, `rfind`, `count`, `startswith`,
`endswith`, `index` or `rindex` was read as an empty window on the general path
(the argument was present, so the bound flags said `has_lo = has_hi = 1` and the
None's zero payload was used as the index). CPython reads `None` as "from the
start" / "to the end". `"hello".find("l", None, None)` printed -1 where CPython
prints 2; the same held when the None reached the method through a variable, a
function argument, a list item, a dict value or an attribute, and for
startswith/endswith and for index/rindex (which printed a spurious ValueError).

The general emitter now tests each supplied bound's tag and passes `has_lo = 0`
/ `has_hi = 0` for a None, matching the typed path, which already special-cased a
literal None. The programs below keep the shape compared with CPython on both
builds, including the non-None bounds they must not disturb.
"""
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent

NONE_LITERAL = r'''def main() -> None:
    s: str = "hello"
    print(s.find("l", None, None), s.rfind("l", None, None), s.count("l", None, None))
    print(s.startswith("he", None, None), s.endswith("lo", None, None))
    print(s.index("l", None, None), s.rindex("l", None, None))
    print(s.find("l", None), s.find("l", 0, None), s.find("l", None, 5))
    print(s.rfind("l", None), s.count("l", 0, None), s.startswith("lo", None, 3))
    print(s.endswith("he", None, 3))
    print("done")


main()
'''

NONE_SOURCES = r'''class C:
    pass


def show(s: str, sub: str, a, b) -> None:
    print(s.find(sub, a, b), s.rfind(sub, a, b), s.count(sub, a, b))
    print(s.startswith(sub, a, b), s.endswith(sub, a, b))
    try:
        print(s.index(sub, a, b), s.rindex(sub, a, b))
    except ValueError:
        print("miss")


def main() -> None:
    s: str = "hello world hello"
    a = None
    c = C()
    c.lo = None
    c.hi = 5
    xs = [None, 0, 2, 5, -1]
    d = {"lo": None, "hi": None}
    show(s, "hello", a, a)
    show(s, "hello", 0, a)
    show(s, "hello", a, 10)
    show(s, "hello", -1, a)
    show(s, "hello", a, -1)
    show(s, "hello", c.lo, c.hi)
    show(s, "hello", xs[0], xs[1])
    show(s, "hello", d["lo"], d["hi"])
    show(s, "hello", xs[3], d["lo"])
    show(s, "hello", 2, 2)
    show("", "", a, a)
    show("éXé", "é", a, a)
    show("abc", "b", 100, a)
    show("abc", "b", a, 100)
    show("abc", "b", -100, 100)
    print("done")


main()
'''

NONE_WINDOWS = r'''def probe(s: str, sub: str, lo, hi) -> None:
    print(s.find(sub, lo, hi), s.rfind(sub, lo, hi), s.count(sub, lo, hi))
    print(s.startswith(sub, lo, hi), s.endswith(sub, lo, hi))
    try:
        print(s.index(sub, lo, hi), s.rindex(sub, lo, hi))
    except ValueError:
        print("miss")


def main() -> None:
    strings = ["", "aXbXc", "abcabc", "éXé", "aaa"]
    subs = ["", "X", "a", "é", "abc"]
    bounds = [None, -100, -6, -5, -1, 0, 1, 3, 5, 6, 100]
    for s in strings:
        for sub in subs:
            for lo in bounds:
                for hi in bounds:
                    probe(s, sub, lo, hi)
    print("done")


main()
'''

NONE_TUPLE = r'''def start(prefix, lo, hi) -> None:
    try:
        print("s", "hello".startswith(prefix, lo, hi))
    except TypeError:
        print("s TypeError")


def end(suffix, lo, hi) -> None:
    try:
        print("e", "hello".endswith(suffix, lo, hi))
    except TypeError:
        print("e TypeError")


def main() -> None:
    a = None
    start(("x", "he"), a, a)
    end(("x", "lo"), a, a)
    start(("x", "he"), 0, a)
    end(("x", "lo"), a, 5)
    start((), a, a)
    end((), a, a)
    start("he", a, a)
    end("lo", a, a)
    start(("a", 1), a, a)
    end(("a", 1), a, a)
    print("done")


main()
'''

NONE_TYPES = r'''def main() -> None:
    s: str = "hello"
    for v in [True, False, 0, 1, 2, -1]:
        print(v, s.find("l", v, None), s.count("l", None, v),
              s.startswith("he", v, None), s.endswith("lo", None, v))
    for v in [1.5, "x", [1]]:
        try:
            print("f", s.find("l", v, None))
        except TypeError as e:
            print("f TypeError", e)
        try:
            print("s", s.startswith("he", v, None))
        except TypeError as e:
            print("s TypeError", e)
        try:
            print("c", s.count("l", None, v))
        except TypeError as e:
            print("c TypeError", e)
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


class Fuzz3nTests(unittest.TestCase):
    def check(self, slug, text, rc=0):
        with tempfile.TemporaryDirectory(prefix='ail-fuzz3n-') as directory:
            want, got_rc, err = _cpython(directory, slug, text)
            self.assertEqual(got_rc, rc, err)
            for general in (True, False):
                got, build_err = _build_and_run(directory, '%s_%s' % (slug, 'g' if general else 'd'), text, general)
                self.assertIsNotNone(got, '%s (general=%s)\n%s' % (text[:2000], general, build_err))
                self.assertEqual(got, (want, rc), '%s (general=%s)\n%s' % (text[:2000], general, build_err))

    def test_none_literal_bounds(self):
        self.check('none_literal', NONE_LITERAL)

    def test_none_bounds_from_sources(self):
        self.check('none_sources', NONE_SOURCES)

    def test_none_and_int_windows(self):
        self.check('none_windows', NONE_WINDOWS)

    def test_none_bounds_with_tuple_prefixes(self):
        self.check('none_tuple', NONE_TUPLE)

    def test_none_bounds_type_checks(self):
        self.check('none_types', NONE_TYPES)


if __name__ == '__main__':
    unittest.main()

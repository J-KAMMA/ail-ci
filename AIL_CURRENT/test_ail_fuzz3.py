"""Differential fuzz round 3: str methods and slices, including the windows they take.

Found with small random programs compared against CPython on both builds:

1. The general path's shared start/end clamp (`ail__win`, cruntime.py) collapsed an inverted
   window to an empty one at the clamped start. CPython treats `s.find("", 10, 0)` as an invalid
   window (-1), not the empty window at 5, and the same holds for rfind/index/rindex/count/
   startswith/endswith: `"aXbXc".find("", 10, 0)` printed 5 on the general path where CPython
   prints -1. It also clamped a start past the end down to `len`, so `"abc".find("", 4)` was 3
   instead of -1. The helper now returns whether the window is valid, does not clamp start above
   the length, and every str method (and list/tuple index, whose invalid window is simply not
   searched) uses that answer.

The other method/slice shapes below (split/rsplit maxsplit, strip chars, replace count,
center/ljust/rjust, expandtabs, splitlines, casefold, and negative/huge/zero-step slices) were
fuzzed too; these programs keep them compared with CPython on both builds.
"""
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent

STR_WINDOW = r'''def probe(s: str, sub: str, lo: int, hi: int) -> None:
    print(s.find(sub, lo, hi), s.rfind(sub, lo, hi), s.count(sub, lo, hi),
          s.startswith(sub, lo, hi), s.endswith(sub, lo, hi))
    try:
        print(s.index(sub, lo, hi))
    except ValueError:
        print("index-miss")
    try:
        print(s.rindex(sub, lo, hi))
    except ValueError:
        print("rindex-miss")


def main() -> None:
    strings: list[str] = ["", "aXbXc", "abcabc", "éXé", "aaa"]
    subs: list[str] = ["", "X", "a", "é", "abc"]
    bounds: list[int] = [-100, -6, -5, -1, 0, 1, 3, 5, 6, 100]
    for s in strings:
        for sub in subs:
            for lo in bounds:
                for hi in bounds:
                    probe(s, sub, lo, hi)
    # the same values reach the method through a list item and a dict value
    bs: list[int] = [10, 0, 5, -2]
    d: dict[str, int] = {"lo": 10, "hi": 0, "end": 5}
    for i in range(len(bs)):
        probe("aXbXc", "", bs[i], bs[(i + 1) % len(bs)])
    probe("aXbXc", "", d["lo"], d["hi"])
    probe("aXbXc", "", d["end"], d["hi"])
    print("done")


main()
'''

STR_TUPLE_WINDOW = r'''def start(prefix: tuple[str, int], lo: int, hi: int) -> None:
    try:
        print("s", "abc".startswith(prefix, lo, hi))
    except TypeError:
        print("s TypeError")


def end(suffix: tuple[str, int], lo: int, hi: int) -> None:
    try:
        print("e", "abc".endswith(suffix, lo, hi))
    except TypeError:
        print("e TypeError")


def scalar(prefix: int) -> None:
    try:
        print("one", "abc".startswith(prefix))
    except TypeError:
        print("one TypeError")
    try:
        print("two", "abc".endswith(prefix, 10, 0))
    except TypeError:
        print("two TypeError")


def main() -> None:
    # An invalid window still validates every tuple member: CPython raises TypeError before
    # it decides that the window matches nothing.
    start(("a", 1), 10, 0)
    start(("a", 1), 3, 2)
    start(("a", 1), 100, 99)
    start(("a", 1), -100, -99)
    end(("a", 1), 10, 0)
    end(("a", 1), 3, 2)
    end(("a", 1), 100, 99)
    end(("a", 1), -100, -99)
    # the same window values arrive through a list item and a dict value
    a: list[int] = [10, 3, 0]
    b: list[int] = [0, 2, 3]
    d: dict[str, int] = {"lo": 10, "hi": 0}
    for i in range(len(a)):
        start(("a", 1), a[i], b[i])
        end(("a", 1), a[i], b[i])
    start(("a", 1), d["lo"], d["hi"])
    end(("a", 1), d["lo"], d["hi"])
    # on a valid window a matching early element still short-circuits before the bad one
    start(("a", 1), 0, 3)
    start(("a", 1), 0, 1)
    end(("c", 1), 0, 3)
    end(("c", 1), 2, 3)
    # a valid window with no match does reach the bad element
    start(("x", 1), 0, 3)
    end(("x", 1), 0, 3)
    # all-str tuples under invalid and valid windows
    start(("a", "b"), 10, 0)
    end(("a", "b"), 10, 0)
    start(("a", "b"), 0, 3)
    end(("a", "b"), 0, 3)
    start(("a", 1), -1000000000000000000, 1000000000000000000)
    end(("a", 1), -1000000000000000000, 1000000000000000000)
    # a non-str scalar goes through the same validation, including for an invalid window
    scalar(1)
    ns: list[int] = [1, 7]
    for i in range(len(ns)):
        scalar(ns[i])
    # an empty tuple matches nothing and raises nothing
    et: tuple[str, ...] = ()
    try:
        print("empty", "abc".startswith(et, 10, 0), "abc".endswith(et, 10, 0))
    except TypeError:
        print("empty TypeError")
    print("done")


main()
'''

STR_METHOD_SLICES = r'''def main() -> None:
    s: str = "  a,b,,c  "
    print(len(s.split(",")), "|".join(s.split(",")))
    print(len(s.rsplit(",", 2)), "|".join(s.rsplit(",", 2)))
    print(len(s.split(None, 2)), "|".join(s.split(None, 2)))
    print(len("  a  b  ".split(None, 0)), "|".join("  a  b  ".split(None, 0)))
    print(len("  a  b  ".rsplit(None, 0)), "|".join("  a  b  ".rsplit(None, 0)))
    print(s.strip(), s.lstrip(), s.rstrip())
    print(s.strip(" ,a"), s.lstrip(" "), s.rstrip(" c"))
    print(s.replace("a", "X"), s.replace(",", ";", 2), s.replace("", "-", 3))
    print(s.find("a"), s.rfind("a"), s.find("a", 3), s.rfind("a", 0, 5))
    print(s.count("a"), s.count(",", 2, 8), s.startswith("  a"), s.endswith("  ", 0, 7))
    print("abc".center(9, "*"), "abc".ljust(6, "."), "abc".rjust(6), "abc".center(8))
    print("abc".zfill(7), "-12".zfill(7), "+12".zfill(7))
    print("A\tB\tC".expandtabs(4), "A\tB".expandtabs(0))
    t: str = "a\nb\r\nc\rd"
    print(len(t.splitlines()), "|".join(t.splitlines()))
    print("abcABC".casefold(), "ABC".lower(), "abc".upper())
    print(s[1:10], s[-4:], s[::-1], s[::2], s[1:5:-1], s[::100], s[-100:100:3])
    print("abcdef"[::-2], "abcdef"[5:0:-2], "abcdef"[-100:100:-2], "abcdef"[100:-100:-1])
    print("éaé"[::-1], "aébcé"[::2], "aébcé"[-100:100:-2])
    bounds: list[int] = [-1000000000000000000, -100, -7, -1, 0, 1, 3, 7, 100, 1000000000000000000]
    steps: list[int] = [-1000000000000000000, -7, -3, -2, -1, 1, 2, 3, 7, 1000000000000000000]
    for lo in bounds:
        for hi in bounds:
            print("aébcé"[lo:hi])
    for lo in bounds:
        for st in steps:
            print("aébcé"[lo:10:st], "aébcé"[-10:lo:st])
    print("done")


main()
'''

ZERO_STEP = r'''def main() -> None:
    s: str = "abcdef"
    print(s[:])
    st: int = 0
    print(s[::st])
    print("unreachable")


main()
'''

LIST_INDEX_WINDOW = r'''def main() -> None:
    xs: list[int] = [4, 5, 4]
    ys: list[str] = ["a", "b", "a"]
    t: tuple[int, int, int] = (4, 5, 4)
    bounds: list[int] = [-100, -5, -1, 0, 1, 3, 4, 5, 100]
    for lo in bounds:
        for hi in bounds:
            try:
                print(xs.index(4, lo, hi))
            except ValueError:
                print("list-miss")
            try:
                print(ys.index("a", lo, hi))
            except ValueError:
                print("sl-miss")
            try:
                print(t.index(4, lo, hi))
            except ValueError:
                print("tuple-miss")
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


class Fuzz3Tests(unittest.TestCase):
    def check(self, slug, text, rc=0):
        with tempfile.TemporaryDirectory(prefix='ail-fuzz3-') as directory:
            want, got_rc, err = _cpython(directory, slug, text)
            self.assertEqual(got_rc, rc, err)
            for general in (True, False):
                got, build_err = _build_and_run(directory, '%s_%s' % (slug, 'g' if general else 'd'), text, general)
                self.assertIsNotNone(got, '%s (general=%s)\n%s' % (text[:2000], general, build_err))
                self.assertEqual(got, (want, rc), '%s (general=%s)\n%s' % (text[:2000], general, build_err))

    def test_str_windows(self):
        self.check('str_windows', STR_WINDOW)

    def test_str_tuple_window_type_checks(self):
        self.check('str_tuple_window', STR_TUPLE_WINDOW)

    def test_str_methods_and_slices(self):
        self.check('str_methods_slices', STR_METHOD_SLICES)

    def test_zero_step_is_cpython_error(self):
        self.check('zero_step', ZERO_STEP, rc=1)

    def test_list_and_tuple_index_windows(self):
        self.check('list_index_windows', LIST_INDEX_WINDOW)


if __name__ == '__main__':
    unittest.main()

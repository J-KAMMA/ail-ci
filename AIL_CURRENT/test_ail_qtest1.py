"""Differential qtest1: str search start/end bounds go through __index__.

CPython converts the optional start and end of str.startswith/endswith (and the
other str searches) with PyNumber_AsSsize_t, so an instance with __index__ is a
valid bound. The general path read the argument's pointer payload as an integer
after its tag check rejected AIL_T_INST, printing a caught TypeError where
CPython returns a result (``"abc".startswith(("a",), Idx(0))``). Bounds are now
converted through __index__ with CPython's messages, and the same program keeps
None, negative, huge, wrong-type, nested-tuple and empty-prefix cases compared
on both builds.
"""
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent

INDEX_BOUNDS = r'''class Idx:
    def __init__(self, v: int) -> None:
        self.v = v
    def __index__(self) -> int:
        return self.v


class NoIdx:
    def __init__(self, v: int) -> None:
        self.v = v


class Bad:
    def __index__(self) -> float:
        return 1.5


def probe(tag: str, f) -> None:
    try:
        print(tag, f())
    except TypeError as e:
        print(tag, "TypeError", str(e))


def show(s: str, lo, hi) -> None:
    probe("start", lambda: s.startswith(("bc", "x"), lo, hi))
    probe("end", lambda: s.endswith(("ab", "x"), lo, hi))
    probe("find", lambda: s.find("bc", lo, hi))
    probe("count", lambda: s.count("b", lo, hi))


def main() -> None:
    s: str = "abcabc"
    i = Idx(1)
    j = Idx(5)
    k = Idx(-1)
    n = Idx(100)
    big = Idx(9223372036854775807)
    neg = Idx(-9223372036854775807)
    probe("plain-lo", lambda: s.startswith("bc", i))
    probe("plain-both", lambda: s.startswith("bc", i, j))
    probe("tuple-lo", lambda: s.startswith(("bc",), i))
    probe("tuple-both", lambda: s.endswith(("bc",), i, j))
    show(s, i, j)
    show(s, k, n)
    show(s, Idx(-100), Idx(100))
    show(s, n, n)
    show(s, big, big)
    show(s, neg, big)
    show(s, big, neg)
    xs = [i, j, k, n]
    d = {"lo": i, "hi": j}
    for a in xs:
        probe("item", lambda a=a: s.startswith(("bc",), a))
    probe("dict", lambda: s.endswith(("bc",), d["lo"], d["hi"]))
    probe("none", lambda: s.startswith(("bc",), None, None))
    probe("empty-tuple", lambda: s.startswith((), i, j))
    probe("empty-prefix", lambda: s.endswith(("",), i, j))
    probe("nested", lambda: s.startswith(("a", ("b",))))
    probe("noindex", lambda: s.startswith(("bc",), NoIdx(1)))
    probe("badindex", lambda: s.startswith(("bc",), Bad()))
    probe("float", lambda: s.startswith(("bc",), 1.5))
    probe("str", lambda: s.startswith(("bc",), "x"))
    probe("list", lambda: s.startswith(("bc",), [1]))
    probe("list-index", lambda: [0, 1, 2, 3].index(2, Idx(1)))
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


class QTest1Tests(unittest.TestCase):
    def check(self, slug, text, rc=0):
        with tempfile.TemporaryDirectory(prefix='ail-qtest1-') as directory:
            want, got_rc, err = _cpython(directory, slug, text)
            self.assertEqual(got_rc, rc, err)
            for general in (True, False):
                got, build_err = _build_and_run(directory, '%s_%s' % (slug, 'g' if general else 'd'), text, general)
                self.assertIsNotNone(got, '%s (general=%s)\n%s' % (text[:2000], general, build_err))
                self.assertEqual(got, (want, rc), '%s (general=%s)\n%s' % (text[:2000], general, build_err))

    def test_str_search_bounds_use_index(self):
        self.check('index_bounds', INDEX_BOUNDS)


if __name__ == '__main__':
    unittest.main()

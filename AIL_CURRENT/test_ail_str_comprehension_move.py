"""`names = [f(x) for x in xs]` of strings moves the comprehension's own list into the local (pkg-v12/pyfunc.py).

The comprehension is built into a private temp that nothing else names, and the assignment then copied that spine of views
into one temp and again into a second one before moving it: two extra 24-byte spines per str column (a tree parser sorts a
3,000,000-element name column per `sort`: 144 MB of spines and 6 million pushes). The temp itself now moves into the local.
What this module pins, against CPython in the legacy build and both IR modes and under ASan+UBSan+LSan:

* a comprehension of strings assigned to a name, in a loop, from itself (`xs = [x + "!" for x in xs]`), with a filter, over a
  struct field's list, over `range`, empty, and one that raises half way (the name keeps its old list);
* the C shape: no copy of the comprehension's spine between its temp and the local.
"""
import os
import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path[:0] = [str(ROOT / 'python' / 'pkg-v12'), str(ROOT)]

from test_ail_ir_s3 import Built, cpython_run, run, HAVE_CC     # noqa: E402

PROGRAM = '''import sys


class T:
    def __init__(self, nm: list[str], w: list[int]):
        self.nm = nm
        self.w = w


def shout(words: list[str]) -> list[str]:
    names = [w.upper() + "!" for w in words]
    return names


def pick(t: T, idx: list[int]) -> str:
    col = [t.nm[i] for i in idx]
    return ",".join(col)


def main() -> int:
    n = int(sys.argv[1])
    words: list[str] = []
    for i in range(n):
        words.append("w" + str(i * 7 % 11))
    xs = [w + "." for w in words]
    for r in range(3):
        xs = [x + str(r) for x in xs]
    ys = [x for x in xs if len(x) > 4]
    zs = [str(i) + "z" for i in range(n)]
    es = [w for w in words if w == "none"]
    print(len(xs), len(ys), len(zs), len(es), xs[0] if len(xs) > 0 else "-", ys[len(ys) - 1] if len(ys) > 0 else "-", ",".join(ys))
    t = T(words, list(range(n)))
    idx = [i for i in range(n) if i % 2 == 0]
    print(pick(t, idx))
    cols = shout(words)
    print(len(cols), ",".join(cols))
    keep = ["a", "b"]
    try:
        keep = [words[i] for i in range(n + 3)]
    except IndexError:
        print("raised", len(keep), keep[0], keep[1])
    for k in range(3):
        keep = [x + str(k) for x in keep]
    print(",".join(keep))
    return 0


sys.exit(main())
'''

SAN_ENV = dict(os.environ, ASAN_OPTIONS='detect_leaks=1:abort_on_error=0', UBSAN_OPTIONS='print_stacktrace=1:halt_on_error=1')


def body_of(c, name):
    m = re.search(r'\n[\w *]+ %s\([^)]*\) \{\n' % name, c)
    assert m, name
    return c[m.end():c.index('\n}\n', m.end())]


@unittest.skipUnless(HAVE_CC, 'no C compiler')
class ComprehensionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.dir = tempfile.TemporaryDirectory(prefix='ail-scm-')
        cls.built = Built(cls.dir.name, 'scm', PROGRAM, debug=True)

    @classmethod
    def tearDownClass(cls):
        cls.dir.cleanup()

    def test_matches_cpython_in_every_mode(self):
        for n in (0, 1, 2, 3, 9, 40, 500):
            expected = cpython_run(self.dir.name, 'scm_cpython', PROGRAM, (n,))
            self.assertEqual(expected[0], 0, expected[2])
            for tag, exe in self.built.exe.items():
                self.assertEqual(run(exe, (n,))[:2], expected[:2], (tag, n))

    def test_the_comprehension_list_moves_without_a_copy(self):
        c = Path(self.dir.name, 'scm.legacy.d', 'program.c').read_text()
        body = body_of(c, 'shout')
        self.assertRegex(body, r'ail_slist_free\(&v_names\); v_names = v__t\d+; v__t\d+ = \(ail_slist\)\{0\};')
        self.assertNotIn('ail_slist _source', body)
        main = body_of(c, 'py_main')
        for line in main.splitlines():
            if '_comp_element' in line:
                self.assertNotIn('ail_slist _source', line)

    def test_sanitizers_report_nothing(self):
        for tag in ('legacy', 'ir'):
            san = Path(self.dir.name, 'scm.%s.san' % tag)
            cc = subprocess.run(['gcc', '-O1', '-g', '-fsanitize=address,undefined', '-fno-sanitize-recover=undefined',
                                 '-fno-omit-frame-pointer', '-pthread', '-w',
                                 str(Path(self.dir.name, 'scm.%s.d' % tag, 'program.c')), '-lm', '-o', str(san)],
                                capture_output=True, text=True)
            self.assertEqual(cc.returncode, 0, cc.stderr[-2000:])
            for n in (0, 7, 300):
                r = subprocess.run([str(san), str(n)], capture_output=True, timeout=600, env=SAN_ENV)
                err = r.stderr.decode(errors='replace')
                self.assertEqual(r.returncode, 0, err[-1200:])
                self.assertNotIn('Sanitizer', err)
                self.assertNotIn('runtime error', err)
                expected = cpython_run(self.dir.name, 'scm_cpython', PROGRAM, (n,))
                self.assertEqual(r.stdout.decode(), expected[1])


if __name__ == '__main__':
    unittest.main()

"""Silent wrong answers in chained comparisons and identity, against CPython 3.12.

`is` on str/bytes was a silent False where CPython interns equal constants and answers True
(`same("a", "a")`, `b"a" is b"a"`).  A direct pair of string constants is now refused by name
at compile time; a value that reaches the comparison through an argument, a list item, an
attribute or a dict value stops by name on both builds with the same DIFFERENCES id.

Chained comparisons with a side effect in the middle, membership over lists of lists and
`None == ...` were already CPython-identical; the programs below keep those shapes covered.
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
IDENT = 'C?-job-fuzz90-10231630-1'


def _cpython(directory, name, text):
    src = Path(directory) / (name + '_cpython.py')
    src.write_text(text, encoding='utf-8')
    done = subprocess.run([sys.executable, '-B', str(src)], capture_output=True, timeout=120,
                          env=dict(os.environ, PYTHONUTF8='1', PYTHONWARNINGS='ignore'))
    return done.stdout.replace(b'\r\n', b'\n'), done.returncode, _last_line(done.stderr)


def _last_line(err):
    lines = [x for x in err.decode('utf-8', 'replace').splitlines() if x.strip()]
    return lines[-1] if lines else ''


def _build(directory, name, text, general):
    src = Path(directory) / (name + '.ail')
    src.write_text(text, encoding='utf-8')
    exe = Path(directory) / ('exe_' + name + ('_g' if general else '_d'))
    env = dict(os.environ, AIL_NO_CACHE='1', AIL_QUIET_FALLBACK='1')
    env.pop('AIL_NO_GENERAL', None)
    if general:
        env['AIL_UNIFIED_FORCE'] = '1'
    cmd = [sys.executable, '-B', CHATGPT, 'compile', src.name, '--syntax', 'python', '-o', exe.name]
    built = subprocess.run(cmd, cwd=directory, capture_output=True, text=True, timeout=900, env=env)
    return exe, built


def _build_run(directory, name, text, general):
    exe, built = _build(directory, name, text, general)
    if built.returncode != 0:
        return None, (built.stdout + built.stderr)[-1500:]
    got = subprocess.run([str(exe)], capture_output=True, timeout=120, cwd=directory)
    return (got.stdout.replace(b'\r\n', b'\n'), got.returncode, _last_line(got.stderr)), got.stderr.decode('utf-8', 'replace')[-800:]


def check_program(test, name, text, modes=(True, False), rc=0):
    with tempfile.TemporaryDirectory(prefix='ail-fuzz90-') as directory:
        want = _cpython(directory, name, text)
        test.assertEqual(want[1], rc, text)
        for general in modes:
            got, err = _build_run(directory, name, text, general)
            test.assertIsNotNone(got, '%s (general=%s)\n%s' % (text[:3000], general, err))
            test.assertEqual(got, want, '%s (general=%s)\n%s' % (text[:3000], general, err))


def check_refused(test, name, text, words, modes=(True, False)):
    with tempfile.TemporaryDirectory(prefix='ail-fuzz90-') as directory:
        for general in modes:
            _, built = _build(directory, '%s%d' % (name, general), text, general)
            test.assertNotEqual(built.returncode, 0, '%s built (general=%s)' % (name, general))
            for word in words:
                test.assertIn(word, built.stdout + built.stderr, '%s (general=%s)' % (name, general))


def check_stopped(test, name, text, stdout, modes=(True, False)):
    with tempfile.TemporaryDirectory(prefix='ail-fuzz90-') as directory:
        want = _cpython(directory, name, text)
        test.assertEqual(want[1], 0, text)
        for general in modes:
            got, err = _build_run(directory, name, text, general)
            test.assertIsNotNone(got, '%s (general=%s)\n%s' % (text[:3000], general, err))
            test.assertEqual(got[0], stdout, '%s (general=%s)\n%s' % (name, general, err))
            test.assertNotEqual(got[1], 0, '%s (general=%s)' % (name, general))
            test.assertIn(IDENT, got[2], '%s (general=%s)' % (name, general))


CHAINS = r'''def mid(n: int) -> int:
    print("mid", n)
    return n


def mid_s() -> str:
    print("mid s")
    return "b"


def mid_f() -> float:
    print("mid f")
    return 1.5


def mid_l() -> list[int]:
    print("mid l")
    return [1, 2, 3]


def main() -> None:
    print(1 < mid(2) < 3)
    print(3 < mid(2) < 5)
    print(mid(2) > 1 < mid(2))
    print("a" < mid_s() < "c")
    print("c" < mid_s() < "d")
    print(0.0 < mid_f() < 2.0)
    print(0 < len(mid_l()) < 4)
    print(2**62 < mid(2**62) < 2**62 + 1)
    print(-2**62 < mid(-2**62) < 0)
    print(0 is mid(0) is 0)
    print(None is None is None)


main()
'''

NESTED = r'''def main() -> None:
    rows = [[1, 2], [3], []]
    print([1, 2] in rows, [3, 4] in rows, [] in rows, [1] in rows)
    print([1, 2] not in rows, [2, 1] in rows)
    print(None == 0, None == False, None == "", None == [])
    print([None] == [None], [None] == [0], None is not None)
    inner = [1, 2]
    print(inner in rows, inner is rows[0])
    print([] == [], [0] == [False], [1] != [1.0])


main()
'''

ALLOWED = r'''def same(a, b):
    return a is b, a is not b


def main() -> None:
    x = []
    print(same(x, x), same(x, []))
    print(same(None, None), same(True, True), same(1, True))
    print(same("a", "b"), same("a", 1), same("a", None), same("a", []))
    s = "a"
    t = s
    print(s is t, s is not t, s is s)


main()
'''

REFUSED = {
    'str': 'print("a" is "a")\n',
    'str_not': 'print("a" is not "a")\n',
    'bytes': 'print(b"a" is b"a")\n',
}

STOPPED = {
    'argument': ('def same(a, b):\n    return a is b, a is not b\n\n\n'
                 'def main() -> None:\n    print("start")\n    print(same("a", "a"))\n\n\nmain()\n',
                 b'start\n'),
    'list_item': ('def main() -> None:\n    xs = ["a", "a"]\n    print(xs[0] is xs[1])\n\n\nmain()\n', b''),
    'attribute': ('class C:\n    def __init__(self, s: str) -> None:\n        self.s = s\n\n\n'
                  'def main() -> None:\n    a = C("a")\n    b = C("a")\n    print(a.s is b.s)\n\n\nmain()\n', b''),
    'dict_value': ('def main() -> None:\n    a = {"k": "a"}\n    b = {"k": "a"}\n    print(a["k"] is b["k"])\n\n\nmain()\n', b''),
    'bytes_argument': ('def same(a, b):\n    return a is b\n\n\n'
                       'def main() -> None:\n    print(same(b"a", b"a"))\n\n\nmain()\n', b''),
}


@unittest.skipUnless(HAVE_CC, 'needs gcc')
class Fuzz90(unittest.TestCase):
    def test_chained_comparisons_evaluate_the_middle_once(self):
        check_program(self, 'chains', CHAINS)

    def test_in_none_and_nested_lists(self):
        check_program(self, 'nested', NESTED)

    def test_text_constant_identity_is_refused_by_name(self):
        for name, text in sorted(REFUSED.items()):
            check_refused(self, 'text_' + name, text, [IDENT, 'is'])

    def test_text_identity_through_values_stops_by_name(self):
        for name, (text, stdout) in sorted(STOPPED.items()):
            check_stopped(self, 'stop_' + name, text, stdout)

    def test_non_text_identity_and_different_types_still_match(self):
        check_program(self, 'allowed', ALLOWED)


if __name__ == '__main__':
    unittest.main()

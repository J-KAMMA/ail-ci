"""Differential fuzz round 65: heapq/bisect with a value the annotation does not describe.

CPython appends to a heap before its comparison, so `heappush(h, "x")` on a `list[int]`
leaves the string in `h` when it raises TypeError. When the same file also compares tuples
(the bisect below), the list repr helper is generated from the annotation and spelled each
int element `str(x)`; after that failed push it printed `x`, not CPython's `'x'`. The helper
now uses `repr(x)` for scalar elements, so the value's own repr is used. The same shape with
`list[str]` and an int used to raise a spurious TypeError while printing.

Both builds are compared with CPython.
"""
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent

WRONG_TYPE_HEAP = r'''import heapq
import bisect


class Box:
    def __init__(self, v: str) -> None:
        self.v: str = v


def push_bad(h: list[int], item: str) -> None:
    try:
        heapq.heappush(h, item)
    except TypeError as e:
        print("arg", type(e).__name__)


def main() -> None:
    h: list[int] = [3, 1, 2]
    heapq.heapify(h)
    try:
        heapq.heappush(h, "x")
    except TypeError as e:
        print("push", type(e).__name__)
    print(h)
    s: list[str] = ["b", "a"]
    heapq.heapify(s)
    try:
        heapq.heappush(s, 1)
    except TypeError as e:
        print("strpush", type(e).__name__)
    print(s)
    xs: list[tuple[int, int]] = [(1, 2), (3, 4)]
    print(bisect.bisect_left(xs, (2, 0)))
    bad: list[str] = ["z"]
    d: dict[str, str] = {"v": "q"}
    h2: list[int] = [5, 4]
    heapq.heapify(h2)
    for item in [bad[0], d["v"]]:
        try:
            heapq.heappush(h2, item)
        except TypeError as e:
            print("more", type(e).__name__)
    print(h2)
    b = Box("w")
    h3: list[int] = [9, 8]
    heapq.heapify(h3)
    try:
        heapq.heappush(h3, b.v)
    except TypeError as e:
        print("attr", type(e).__name__)
    print(h3)
    push_bad(h3, d["v"])
    print(h3)


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


class Fuzz65Tests(unittest.TestCase):
    def check(self, slug, text, rc=0):
        with tempfile.TemporaryDirectory(prefix='ail-fuzz65-') as directory:
            want, got_rc, err = _cpython(directory, slug, text)
            self.assertEqual(got_rc, rc, err)
            for general in (True, False):
                got, build_err = _build_and_run(directory, '%s_%s' % (slug, 'g' if general else 'd'),
                                                text, general)
                self.assertIsNotNone(got, '%s (general=%s)\n%s' % (text[:2000], general, build_err))
                self.assertEqual(got, (want, rc), '%s (general=%s)\n%s' % (text[:2000], general, build_err))

    def test_wrong_type_heap_push_then_list_repr(self):
        self.check('wrong_type_heap', WRONG_TYPE_HEAP)


if __name__ == '__main__':
    unittest.main()

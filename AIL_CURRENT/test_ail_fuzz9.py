"""fuzz9: silent differences in the collections / data-structure area (job fuzz9).

DEVLOG 2026-10-21 (job fuzz9): 72 generated programs over Counter arithmetic and most_common ties,
defaultdict factories, OrderedDict move_to_end, deque rotate / item access, namedtuple _replace / _asdict,
heapq and bisect were run against CPython 3.12 on both builds (the default build and AIL_UNIFIED_FORCE=1).
Three causes were fixed; the DIFFERENCES rows are C?-job-fuzz9-10220555-1..3 (this export carries no
DIFFERENCES.md / DEVLOG.md, so the entries live here; see DEVLOG.md at the root for the same note).

1. `print(f, f["y"])` of a defaultdict / OrderedDict / deque (C?-job-fuzz9-10220555-1). CPython evaluates
   every argument of a call before it turns any of them into text, so `print(f, f["y"])` shows the key
   `f["y"]` inserted and `print(len(f), f, f["w"])` shows the len from before the insert. The collections
   rewrite built the repr text of the collection while evaluating that argument, i.e. before the later
   arguments ran: `defaultdict(<class 'int'>, {'x': 1}) 0` where CPython prints `..., 'y': 0}) 0`. Every
   argument that is not itself converted is now bound to a local first, in order, so the conversion runs
   after all of them; a converted collection keeps its own name, because a second name for a container
   would be a copy, not an alias (the compiler refuses those).
2. A deque's item access on the general path (C?-job-fuzz9-10220555-2). A deque is a two-element list
   wrapper at run time (`[data, maxlen]`), and `q[0] = x` / `del q[0]` wrote through the wrapper instead of
   the data list: after `q += [3]`, `q[0] = 9` overwrote the wrapper's data pointer, so `len(q)` printed 122
   (or the program segfaulted), while `q[1:]` printed `[None]` where CPython raises TypeError. setitem /
   delitem index the data list now (IndexError "deque index out of range"), and a slice of a deque raises
   CPython's TypeError "sequence index must be integer, not 'slice'" (also for a non-int index, and for
   `q[9]` / `del q[9]` on an empty deque).
3. `del c[k]` with a missing key on a Counter (C?-job-fuzz9-10220555-3). CPython's Counter.__delitem__
   ignores a missing key; the general path raised KeyError and lost the rest of the output. A Counter (a
   dict whose header flag is set) now deletes only when the key is there, while `del d[k]` on a
   defaultdict of the same shape still raises KeyError.

Still differing after these fixes, not fixed here (one area each for the next job): `list(od)` of an
OrderedDict whose keys are ints raises TypeError "argument of type 'int' is not iterable" on the general
path (str keys are fine); `move_to_end(k, last=False)` and `print(d, d.popitem())` are refused by name, and
the general path cannot build them either, so those stay compile errors rather than silent answers.

Each program is built twice (default build, AIL_UNIFIED_FORCE=1 general path) and must print what CPython
prints with the same exit status; the tests that cover a fix also assert which path built them, so a
program that silently falls back does not make the test vacuous.
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
GENERAL_NOTE = 'built on the general path'


def _cpython(directory, name, text):
    src = Path(directory) / (name + '_cpython.py')
    src.write_text(text, encoding='utf-8')
    done = subprocess.run([sys.executable, '-B', str(src)], capture_output=True, timeout=120,
                          env=dict(os.environ, PYTHONUTF8='1'))
    return done.stdout.replace(b'\r\n', b'\n'), done.returncode


def _build_run(directory, name, text, general):
    src = Path(directory) / (name + '.ail')
    src.write_text(text, encoding='utf-8')
    exe = Path(directory) / ('exe_' + name + ('_g' if general else '_d'))
    env = dict(os.environ, AIL_NO_CACHE='1', AIL_QUIET_FALLBACK='1')
    env.pop('AIL_NO_GENERAL', None)
    if general:
        env['AIL_UNIFIED_FORCE'] = '1'
    cmd = [sys.executable, '-B', CHATGPT, 'compile', src.name, '--syntax', 'python', '-o', exe.name]
    built = subprocess.run(cmd, cwd=directory, capture_output=True, text=True, timeout=900, env=env)
    log = built.stdout + built.stderr
    if built.returncode != 0:
        return None, log[-1500:]
    got = subprocess.run([str(exe)], capture_output=True, timeout=120, cwd=directory)
    return (got.stdout.replace(b'\r\n', b'\n'), got.returncode), log[-1500:]


def _note_log(directory, name, text):
    """The default build's own notes: AIL_QUIET_FALLBACK is off, so a fallback to the general path shows."""
    src = Path(directory) / (name + '.ail')
    src.write_text(text, encoding='utf-8')
    env = dict(os.environ, AIL_NO_CACHE='1')
    env.pop('AIL_UNIFIED_FORCE', None)
    env.pop('AIL_NO_GENERAL', None)
    env.pop('AIL_QUIET_FALLBACK', None)
    cmd = [sys.executable, '-B', CHATGPT, 'compile', src.name, '--syntax', 'python', '-o',
           (name + '_note.exe')]
    done = subprocess.run(cmd, cwd=directory, capture_output=True, text=True, timeout=900, env=env)
    return done.stdout + done.stderr


def check_program(test, name, text, modes=(True, False), path=None):
    """`path`: 'typed' / 'general' asserts which path the default build took (a forced build prints no note)."""
    with tempfile.TemporaryDirectory(prefix='ail-fuzz9-') as directory:
        want = _cpython(directory, name, text)
        test.assertEqual(want[1], 0, 'the CPython side of %s must succeed\n%s' % (name, text))
        for general in modes:
            got, log = _build_run(directory, name, text, general)
            test.assertIsNotNone(got, '%s (general=%s)\n%s' % (name, general, log))
            test.assertEqual(got, want, '%s (general=%s)\n%s' % (name, general, log))
        if path is not None:
            notes = _note_log(directory, name, text)
            if path == 'typed':
                test.assertNotIn(GENERAL_NOTE, notes, '%s fell back to the general path\n%s' % (name, notes))
            else:
                test.assertIn(GENERAL_NOTE, notes, '%s is not on the general path any more\n%s' % (name, notes))

P_DDS_INT = r'''from collections import defaultdict, OrderedDict


def main():
    f = defaultdict(int)
    f["x"] += 1
    print(f, f["y"])
    print(f, f["z"], f["y"])


main()
'''

P_DDS_FLOAT_STR = r'''from collections import defaultdict


def main():
    f = defaultdict(float)
    f["a"] += 0.1
    f["a"] += 0.2
    print(f, f["b"])
    i = defaultdict(int)
    i[1] += 1
    print(i, i[2], i)
    s = defaultdict(str)
    s["k"] += "x"
    print(s, s["j"])


main()
'''

P_DDL = r'''from collections import defaultdict


def main():
    g = defaultdict(list)
    g["a"].append(1)
    print(g, g["b"])
    print(g, g["a"].pop())
    print(g)


main()
'''

P_OD = r'''from collections import OrderedDict


def main():
    d = OrderedDict()
    d["x"] = 1
    print(d, d.setdefault("y", 2))
    print(d, len(d))
    d2 = OrderedDict()
    d2["p"] = 5
    print(d2, d2.pop("p"))


main()
'''

P_DEQUE_REPR = r'''from collections import deque


def main():
    q = deque([1, 2, 3])
    print(q, q.popleft())
    print(len(q), q)


main()
'''

P_DEQUE_ITEMS = r'''from collections import deque


def main():
    q = deque([1, 2])
    q += [3]
    print(len(q), list(q))
    q[0] = 9
    print(len(q), list(q))
    del q[1]
    print(len(q), list(q))
    q[-1] = 7
    print(list(q))
    try:
        q[9] = 1
    except IndexError as e:
        print("IndexError", e)
    try:
        del q[9]
    except IndexError as e:
        print("IndexError", e)
    try:
        q["x"] = 1
    except TypeError as e:
        print("TypeError", e)
    try:
        print(q[1:])
    except TypeError as e:
        print("TypeError", e)
    m = deque(["a", "b"])
    m += deque(["c"])
    m[0] = "z"
    print(list(m), len(m))
    print(q, len(q))


main()
'''

P_DEQUE_ITEMS_ERR = r'''from collections import deque


def main():
    e2 = deque()
    try:
        e2[0] = 1
    except IndexError as e:
        print("IndexError", e)
    try:
        del e2[0]
    except IndexError as e:
        print("IndexError", e)
    try:
        print(e2[0])
    except IndexError as e:
        print("IndexError", e)
    n = deque([1, 2])
    try:
        print(n[1:])
    except TypeError as e:
        print("TypeError", e)
    try:
        print(n["k"])
    except TypeError as e:
        print("TypeError", e)
    try:
        print(n[1.5])
    except TypeError as e:
        print("TypeError", e)


main()
'''

P_COUNTER_DEL = r'''from collections import Counter, defaultdict


def main():
    c = Counter("aab")
    del c["z"]
    print(c)
    del c["a"]
    print(c, len(c), c.total())
    c["b"] += 3
    del c["b"]
    print(c, c.most_common())
    d = defaultdict(int)
    d["k"] += 1
    try:
        del d["nope"]
    except KeyError as e:
        print("KeyError", e)
    print(d)
    p = Counter()
    p["only"] = 1
    del p["only"]
    print(p, p.total())
    del p["only"]
    print(p, len(p))


main()
'''

P_HEAP_BISECT = r'''import heapq
import bisect


def main():
    h: list[int] = []
    for v in [5, 1, 4, 1, 3]:
        heapq.heappush(h, v)
    print(h)
    print(heapq.heappushpop(h, 0), heapq.heapreplace(h, -1), h)
    out: list[int] = []
    while h:
        out.append(heapq.heappop(h))
    print(out)
    try:
        heapq.heappop(h)
    except IndexError as e:
        print("IndexError", e)
    xs = [1, 3, 3, 5, 9]
    print(bisect.bisect_left(xs, 3), bisect.bisect_right(xs, 3), bisect.bisect(xs, 3))
    print(bisect.bisect_left(xs, 3, 2), bisect.bisect_right(xs, 3, 1, 4))
    bisect.insort_left(xs, 3)
    bisect.insort_right(xs, 4)
    print(xs)
    e: list[int] = []
    print(bisect.bisect_left(e, 1), bisect.bisect_right(e, 1))


main()
'''

P_NAMEDTUPLE = r'''from collections import namedtuple

P = namedtuple("P", "x y", defaults=[5])


def main():
    p = P(1, 2)
    print(p, p.x, p[1], p._replace(y=8), p._asdict())
    print(P._fields, p == (1, 2), p.index(2), p.count(1), len(p))
    print(P(1), P(1, 3), P(1)._asdict())
    print(p._replace(x=0).y)


main()
'''

@unittest.skipUnless(HAVE_CC, 'gcc is needed for the AIL build')
class Fuzz9Collections(unittest.TestCase):
    """1: the repr of a collection is built after every argument of the print ran (typed path)."""

    def test_defaultdict_int_repr_after_read(self):
        check_program(self, 'dds_int', P_DDS_INT, path='typed')

    def test_defaultdict_float_str_repr_after_read(self):
        check_program(self, 'dds_float_str', P_DDS_FLOAT_STR, path='typed')

    def test_defaultdict_list_repr_after_read(self):
        check_program(self, 'ddl', P_DDL, path='typed')

    def test_ordereddict_repr_after_setdefault(self):
        check_program(self, 'od', P_OD, path='typed')

    def test_deque_repr_after_popleft(self):
        check_program(self, 'dq_repr', P_DEQUE_REPR, path='typed')

    """2: a deque's item access goes through its data list (general path)."""

    def test_deque_setitem_delitem(self):
        check_program(self, 'dq_items', P_DEQUE_ITEMS, path='general')

    def test_deque_index_errors(self):
        check_program(self, 'dq_items_err', P_DEQUE_ITEMS_ERR, path='general')

    """3: del c[k] of a missing key on a Counter is silent (general path)."""

    def test_counter_del_missing(self):
        check_program(self, 'counter_del', P_COUNTER_DEL, path='general')

    """the rest of the area, unchanged by this job."""

    def test_heap_and_bisect(self):
        check_program(self, 'heap_bisect', P_HEAP_BISECT)

    def test_namedtuple(self):
        check_program(self, 'namedtuple', P_NAMEDTUPLE, path='general')


if __name__ == '__main__':
    unittest.main()

"""A constructor takes over a list or dict local that is never read again, and copies it otherwise.

`T(a0, ..., a12)` with thirteen 3M-element list locals held every list three times: the caller
snapshotted each argument, the constructor snapshotted it again, and the locals stayed alive
(tree_fold: 943 MB peak against C's 215 MB). A numeric list or dict parameter whose only use in
`__init__` is `self.f = p` is now taken by pointer and moved into the field, and the call site
hands over either the local itself -- when liveness on the AST shows nothing can read it again --
or one private copy.

The cases below pin the observable value semantics (a copy wherever the local is used later, in a
loop that comes back to it, in a branch, from a parameter) against output recorded from the
compiler before this change, and the C shape: which arguments are moved and which copied.
"""
import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent

SOURCE = 'import sys\n\nclass P:\n\n    def __init__(self, xs: list[int], ys: list[float], k: int):\n        self.xs = xs\n        self.ys = ys\n        self.k = k\n\nclass Q:\n\n    def __init__(self, n: int, xs: list[int]):\n        self.n = n\n        self.xs = xs\n\nclass Two:\n\n    def __init__(self, a: list[int], b: list[int]):\n        self.a = a\n        self.b = b\n\nclass S:\n\n    def __init__(self, d: dict[str, int], f: dict[str, float], n: int):\n        self.d = d\n        self.f = f\n        self.n = n\n\ndef total(xs: list[int]) -> int:\n    s = 0\n    for v in xs:\n        s += v\n    return s\n\ndef qt(q: Q) -> int:\n    return total(q.xs)\n\ndef from_param(xs: list[int]) -> Q:\n    return Q(len(xs), xs)\n\ndef fresh(n: int) -> list[int]:\n    r = [n] * n\n    return r\n\ndef made_here(n: int) -> Q:\n    local = [n, n + 1]\n    local.append(n * 100)\n    return Q(n, local)\n\ndef dict_here(n: int) -> S:\n    m: dict[str, int] = {}\n    for i in range(n):\n        m[\'k\' + str(i)] = i\n    fm: dict[str, float] = {}\n    fm[\'h\'] = 0.5\n    return S(m, fm, n)\n\ndef guarded(n: int) -> int:\n    gx = [n, n]\n    try:\n        q = Q(1, gx)\n        if n > 5:\n            raise ValueError(\'big\')\n        return qt(q)\n    except ValueError:\n        return -1\n\ndef main() -> int:\n    moved = [1, 2, 3]\n    mf = [0.5, 1.5]\n    p = P(moved, mf, 7)\n    p.xs[0] = 100\n    print(\'moved\', total(p.xs), len(p.ys), p.k)\n    kept = [4, 5, 6]\n    q = Q(1, kept)\n    kept[0] = 40\n    q.xs.append(9)\n    print(\'kept\', total(kept), len(kept), total(q.xs), len(q.xs))\n    popped = [7, 8, 9]\n    q2 = Q(popped.pop(), popped)\n    print(\'earlier\', q2.n, total(q2.xs), len(q2.xs))\n    twice = [1, 1]\n    tw = Two(twice, twice)\n    tw.a[0] = 5\n    print(\'twice\', total(tw.a), total(tw.b))\n    outer = [10, 20]\n    qs: list[Q] = []\n    for i in range(3):\n        qs.append(Q(i, outer))\n        qs[i].xs[0] = i\n    print(\'outer\', total(outer), qt(qs[0]), qt(qs[2]))\n    built: list[Q] = []\n    for i in range(3):\n        row = [i, i + 1]\n        row.append(i * 10)\n        built.append(Q(i, row))\n    print(\'per-iteration\', qt(built[0]), qt(built[1]), qt(built[2]))\n    nested: list[Q] = []\n    for i in range(2):\n        shared = [i]\n        for j in range(2):\n            inner = [i, j]\n            nested.append(Q(j, inner))\n            nested.append(Q(j, shared))\n    print(\'nested\', len(nested), qt(nested[2]), qt(nested[3]), qt(nested[7]))\n    carry = [1]\n    chain: list[Q] = []\n    j = 0\n    while j < 3:\n        chain.append(Q(j, carry))\n        carry = [j, j]\n        j += 1\n    print(\'carry\', qt(chain[0]), qt(chain[1]), qt(chain[2]), total(carry))\n    branch = [3, 3]\n    bq = Q(0, [0])\n    if len(branch) > 5:\n        bq = Q(1, branch)\n    else:\n        branch.append(1)\n    print(\'branch\', total(branch), total(bq.xs))\n    base = [5, 5, 5]\n    fq = from_param(base)\n    fq.xs[0] = 0\n    print(\'param\', total(base), total(fq.xs))\n    lit = Q(2, [1, 2] + fresh(2))\n    print(\'expr\', total(lit.xs))\n    last = [9]\n    after = Q(len(last), last)\n    print(\'len-before\', after.n, total(after.xs))\n    mh = made_here(3)\n    print(\'returned\', mh.n, total(mh.xs), guarded(2), guarded(9))\n    a: dict[str, int] = {}\n    a[\'x\'] = 1\n    fa: dict[str, float] = {}\n    fa[\'y\'] = 2.5\n    s = S(a, fa, 1)\n    s.d[\'z\'] = 3\n    kd: dict[str, int] = {\'k\': 4}\n    t = S(kd, fa, 2)\n    kd[\'k\'] = 40\n    t.d[\'q\'] = 5\n    dh = dict_here(50)\n    print(\'dict\', len(s.d), s.d[\'x\'], s.f[\'y\'], len(t.d), t.d[\'k\'], kd[\'k\'], len(kd), len(dh.d), dh.d[\'k49\'], dh.f[\'h\'])\n    return 0\n\nif __name__ == "__main__":\n    sys.exit(main())\n'

# Recorded from the compiler before constructors took arguments over (utf8-str 20cbb51).
EXPECTED = """moved 105 2 7
kept 51 3 24 4
earlier 9 15 2
twice 6 2
outer 30 20 22
per-iteration 1 13 25
nested 8 1 0 1
carry 1 0 2 4
branch 7 0
param 15 10
expr 7
len-before 1 9
returned 3 307 4 -1
dict 2 1 2.5 2 4 40 1 50 49 0.5
"""


def build(directory, text):
    source, exe, debug = Path(directory, "p.ail"), Path(directory, "p"), Path(directory, "debug")
    source.write_text(text, encoding="utf-8")
    built = subprocess.run([sys.executable, str(ROOT / "ail_chatgpt.py"), "compile", str(source),
                            "-o", str(exe), "--debug-dir", str(debug)],
                           capture_output=True, text=True, timeout=300)
    assert built.returncode == 0, built.stdout + built.stderr
    return exe, (debug / "program.c").read_text(encoding="utf-8")


class ConstructorMoveTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.exe, cls.program = build(cls.tmp.name, SOURCE)

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def test_value_semantics_unchanged(self):
        result = subprocess.run([str(self.exe)], capture_output=True, timeout=60)
        self.assertEqual((result.returncode, result.stdout.decode()), (0, EXPECTED),
                         result.stderr.decode(errors="replace"))

    def handed_over(self):
        """C names passed to a constructor by address of a source local (`&v_name`)."""
        names = set()
        for call in re.findall(r"ail_new_\w+\(([^;]*?)\)\)", self.program):
            names.update(re.findall(r"&\(?\*?v_([a-z]\w*)", call))
        return names

    def test_dead_locals_are_moved(self):
        moved = self.handed_over()
        for name in ("moved", "mf", "popped", "twice", "row", "inner", "last", "local", "gx", "a", "m", "fm"):
            self.assertIn(name, moved)

    def test_live_locals_are_copied(self):
        # used after the call, in a loop that comes back to it, read before reassignment in the
        # next iteration, mentioned in a later branch: each keeps its value and the object a copy.
        # (`fa` is copied into `s` and moved into `t`, its last use.)
        moved = self.handed_over()
        for name in ("kept", "outer", "shared", "carry", "branch", "base", "kd"):
            self.assertNotIn(name, moved)

    def test_constructor_does_not_copy_again(self):
        body = re.search(r"\nstatic ail_obj_Q \*ail_new_Q\(int64_t v_n, ail_list \*v_xs\) \{\n(.*?)\n\}\n",
                         self.program, re.S)
        self.assertIsNotNone(body)
        self.assertNotIn("snapshot", body.group(1))
        self.assertIn("ail_obj_field_list_move(&v_self->f_xs, v_xs);", body.group(1))
        self.assertIn("ail_sdict_replace(&v_self->f_d, ail_sdict_take(v_d));", self.program)


if __name__ == "__main__":
    unittest.main()

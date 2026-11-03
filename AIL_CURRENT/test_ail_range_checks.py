"""Overflow and index checks elided by the value-range analysis (python/pkg-v12/rangecheck.py).

The analysis may remove a `ck_add/ck_sub/ck_mul` or a list/bytes index check only where it can
never fire. These tests hold it to that: the edge programs below run against CPython (with every
int `+ - *` checked against int64, which is this language's rule), at values next to 2**63, over
negative ranges, with loop bounds changed inside the loop, with lists resized inside the loop and
through struct fields, under ASan+UBSan (a wrongly elided add is signed overflow, which UBSan
traps), and the generated C is checked for the checks that should be gone and the ones that must
stay.
"""
import ast
import io
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
# The C-text assertions below describe the legacy emitter; with AIL_IR set, functions in the IR's
# subset are emitted by the IR (same behaviour, different text), so only the behaviour is checked.
LEGACY_C = os.environ.get('AIL_IR', '0').strip().lower() in ('', '0', 'off', 'no')
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

EDGES = 'import sys\nMAXV = 9223372036854775807\nMINV = -9223372036854775808\n\ndef add1(a: int) -> int:\n    return a + 1\n\ndef top_loop() -> int:\n    last = 0\n    for i in range(MAXV - 3, MAXV):\n        last = i + 1\n    return last\n\ndef bottom_loop(lo: int) -> int:\n    last = 0\n    for i in range(lo, lo + 3):\n        last = i - 1\n    return last\n\ndef while_lt(n: int) -> int:\n    i = n - 3\n    while i < n:\n        i += 1\n    return i\n\ndef while_le(n: int) -> int:\n    i = n - 3\n    while i <= n:\n        i += 1\n    return i\n\ndef count_down(n: int) -> int:\n    i = n\n    steps = 0\n    while i > 0:\n        i -= 1\n        steps += 1\n    return steps\n\ndef neg_index(xs: list[int]) -> int:\n    s = 0\n    for i in range(-3, 3):\n        s = s + xs[i] * (i + 10)\n    return s\n\ndef local_neg(k: int) -> int:\n    xs = [10, 20, 30, 40]\n    s = 0\n    for i in range(k, 4):\n        s = s + xs[i] + i\n    return s\n\ndef square_guard(w: int) -> int:\n    if w < 0 or w > 3037000499:\n        return -1\n    return w * w\n\ndef square_loose(w: int) -> int:\n    if w > 3037000500:\n        return -1\n    return w * w\n\ndef modified_bound(n0: int) -> int:\n    n = n0\n    xs = [0] * n\n    s = 0\n    for i in range(n):\n        n = n - 1\n        xs[i] = i + n\n        s = s + xs[i]\n    return s + n\n\ndef bound_grows(n0: int) -> int:\n    n = n0\n    xs = [1] * n0\n    s = 0\n    i = 0\n    while i < n:\n        s = s + xs[i]\n        i += 1\n        if i == 3:\n            n = n + 2\n    return s\n\ndef shrinking(k: int) -> int:\n    xs = [1] * 10\n    s = 0\n    for i in range(10):\n        if i == k:\n            xs.pop()\n            xs.pop()\n            xs.pop()\n            xs.pop()\n            xs.pop()\n            xs.pop()\n        s = s + xs[i]\n    return s\n\ndef growing() -> int:\n    xs = [3] * 4\n    s = 0\n    i = 0\n    while i < len(xs):\n        if len(xs) < 12:\n            xs.append(i)\n        s = s + xs[i]\n        i += 1\n    return s\n\ndef rebuilt(n: int) -> int:\n    xs = [1] * 8\n    s = 0\n    for i in range(8):\n        if i == n:\n            xs = [2] * 3\n        s = s + xs[i]\n    return s\n\ndef elem_max(k: int) -> int:\n    xs = [1] * 6\n    xs[k] = MAXV\n    return xs[0] + xs[3]\n\ndef elem_grow(n: int) -> int:\n    xs = [1] * 4\n    for r in range(n):\n        for i in range(4):\n            xs[i] = xs[i] * 3\n    return xs[0] + xs[1]\n\ndef elem_small(n: int) -> int:\n    if n < 1 or n > 100000:\n        return 0\n    xs = [0] * n\n    for i in range(n):\n        xs[i] = (i * 7 + 3) % 256\n    s = 0\n    for i in range(n - 1):\n        s = s + (xs[i] + xs[i + 1])\n    return s\n\ndef ring(n: int) -> int:\n    if n < 1:\n        return 0\n    h = [0.0] * n\n    for i in range(n):\n        h[i] = float(i % 5)\n    acc = 0.0\n    for k in range(n):\n        i = n - 1 - k\n        li = i - 1\n        if li < 0:\n            li = n - 1\n        ri = i + 1\n        if ri == n:\n            ri = 0\n        acc = acc + h[li] * 2.0 + h[ri]\n    return int(acc)\n\ndef bytes_sum(d: bytes) -> int:\n    n = len(d)\n    s = 0\n    i = 0\n    while i + 1 < n:\n        s = s + (d[i] + d[i + 1]) * 3\n        i += 2\n    return s\n\ndef caught(a: int) -> int:\n    x = 7\n    try:\n        x = a + 1\n    except OverflowError:\n        x = x - 1\n    return x + 1\n\ndef mods(a: int, m: int) -> int:\n    if m < 1:\n        return 0\n    r = a % m\n    return r + MAXV - m\n\ndef appended(n: int, at: int) -> int:\n    xs: list[int] = []\n    for i in range(n):\n        xs.append(i * 2)\n    return xs[at] + len(xs)\n\ndef half_appended(n: int, at: int) -> int:\n    xs: list[int] = []\n    for i in range(n):\n        if i % 2 == 0:\n            xs.append(i)\n    return xs[at]\n\ndef broken_append(at: int) -> int:\n    xs: list[int] = []\n    for i in range(10):\n        if i == 5:\n            break\n        xs.append(i)\n    return xs[at]\n\ndef popped(at: int) -> int:\n    ys = [7] * 10\n    for i in range(5):\n        ys.pop()\n    s = 0\n    for i in range(len(ys)):\n        s = s + ys[i]\n    return s + ys[at]\n\ndef nested_append(at: int) -> int:\n    xs: list[int] = []\n    for i in range(3):\n        for j in range(4):\n            xs.append(i * 4 + j)\n    return xs[at]\n\ndef counted(n: int) -> int:\n    c = 0\n    xs = [1] * 5\n    for i in range(n):\n        if i % 3 == 0:\n            c += 1\n    return xs[c]\n\ndef run(k: int, a: int) -> str:\n    try:\n        if k == 0:\n            return str(add1(a))\n        if k == 1:\n            return str(top_loop())\n        if k == 2:\n            return str(bottom_loop(a))\n        if k == 4:\n            return str(while_lt(a))\n        if k == 5:\n            return str(while_le(a))\n        if k == 6:\n            return str(count_down(a))\n        if k == 7:\n            return str(square_guard(a))\n        if k == 8:\n            return str(square_loose(a))\n        if k == 9:\n            return str(modified_bound(a))\n        if k == 10:\n            return str(shrinking(a))\n        if k == 11:\n            return str(growing())\n        if k == 12:\n            return str(elem_max(a))\n        if k == 13:\n            return str(elem_small(a))\n        if k == 14:\n            return str(ring(a))\n        if k == 15:\n            return str(caught(a))\n        if k == 16:\n            return str(mods(a, 1000))\n        if k == 17:\n            return str(local_neg(a))\n        if k == 18:\n            return str(bound_grows(a))\n        if k == 19:\n            return str(rebuilt(a))\n        if k == 21:\n            return str(appended(6, a))\n        if k == 22:\n            return str(half_appended(6, a))\n        if k == 23:\n            return str(broken_append(a))\n        if k == 24:\n            return str(popped(a))\n        if k == 25:\n            return str(nested_append(a))\n        if k == 26:\n            return str(counted(a))\n        return str(elem_grow(a))\n    except OverflowError:\n        return \'overflow\'\n    except IndexError:\n        return \'index\'\n\ndef main() -> int:\n    print(run(0, MAXV), run(0, MAXV - 1), run(0, MINV))\n    print(run(1, 0), run(2, MINV), run(2, MINV + 1), run(2, MAXV - 2), run(2, MAXV - 3))\n    print(run(4, MAXV), run(4, MINV + 3), run(5, MAXV), run(5, MAXV - 1))\n    print(run(6, 5), run(6, -5), run(6, 0))\n    print(run(7, 3037000499), run(7, 3037000500), run(7, -1), run(8, 3037000500), run(8, -3037000500), run(8, -3037000499))\n    print(run(9, 6), run(9, 0), run(9, -4))\n    print(run(10, 2), run(10, 4), run(10, 9), run(10, 11))\n    print(run(11, 0), run(12, 3), run(12, 4), run(12, 9), run(13, 1000), run(13, 1))\n    print(run(14, 7), run(14, 1), run(15, 5), run(15, MAXV))\n    print(run(16, MINV), run(16, MAXV), run(16, -1), run(16, 999))\n    print(run(17, -4), run(17, -5), run(17, 2), run(18, 3), run(18, 6), run(18, 1))\n    print(run(19, 2), run(19, 3), run(19, 8), run(20, 3), run(20, 39), run(20, 40))\n    print(run(21, 5), run(21, 6), run(21, -6), run(21, -7), run(22, 2), run(22, 3), run(22, 5))\n    print(run(23, 4), run(23, 5), run(24, 4), run(24, 5), run(24, -5), run(25, 11), run(25, 12))\n    print(run(26, 12), run(26, 13), run(26, 15), run(26, 0))\n    print(neg_index([5, 6, 7, 8, 9, 10]))\n    print(bytes_sum(b\'\\xff\\xfe\\x01\\x02\\x80\'), bytes_sum(b\'\'), bytes_sum(b\'\\x10\'))\n    return 0\n\nif __name__ == "__main__":\n    sys.exit(main())\n'

# A struct field read is a copy in this language (CPython would alias), so these two are checked
# against the compiler's own answer from before the analysis existed, not against CPython.
FIELDS = 'import sys\n\nclass Box:\n\n    def __init__(self, v: list[int], n: int):\n        self.v = v\n        self.n = n\n\ndef through_field() -> int:\n    b = Box([0, 1, 2, 3, 4], 5)\n    xs = b.v\n    b.v.pop()\n    b.v.pop()\n    return xs[4] + len(b.v)\n\ndef field_loop(b: Box) -> int:\n    s = 0\n    for i in range(b.n):\n        s = s + b.v[i]\n        b.v.pop()\n    return s\n\ndef main() -> int:\n    print(through_field())\n    b = Box([1, 2, 3, 4, 5, 6], 6)\n    try:\n        print(field_loop(b))\n    except IndexError:\n        print(\'index\', len(b.v))\n    return 0\n\nif __name__ == "__main__":\n    sys.exit(main())\n'
FIELDS_EXPECTED = "7\nindex 3\n"

# Codegen: which checks are gone (proven) and which stay (not provable).
CODEGEN = 'import sys\n\ndef proven(n: int) -> int:\n    if n < 0 or n > 1000000:\n        return 0\n    xs = [0] * n\n    for i in range(n):\n        xs[i] = i % 100 + 1\n    s = 0\n    for i in range(1, n):\n        s = s + (xs[i] - xs[i - 1])\n    return s\n\ndef kept(xs: list[int], n: int) -> int:\n    t = 0\n    for i in range(n):\n        t = t + i\n    return t + xs[n] + n * n\n\ndef main() -> int:\n    print(proven(10), kept([1, 2, 3], 2))\n    return 0\n\nif __name__ == "__main__":\n    sys.exit(main())\n'


def _ck(op):
    def f(a, b):
        r = op(a, b)
        if type(r) is int and not -(1 << 63) <= r < (1 << 63):
            raise OverflowError('integer overflow')
        return r
    return f


class _Checked(ast.NodeTransformer):
    """Every `a + b`, `a - b`, `a * b` and `-a` raises OverflowError outside int64, like AIL."""
    OPS = {ast.Add: '_ck_add', ast.Sub: '_ck_sub', ast.Mult: '_ck_mul'}

    def visit_BinOp(self, node):
        self.generic_visit(node)
        name = self.OPS.get(type(node.op))
        if name is None:
            return node
        return ast.copy_location(ast.Call(func=ast.Name(id=name, ctx=ast.Load()), args=[node.left, node.right],
                                          keywords=[]), node)

    def visit_UnaryOp(self, node):
        self.generic_visit(node)
        if isinstance(node.op, ast.USub) and not isinstance(node.operand, ast.Constant):
            return ast.copy_location(ast.Call(func=ast.Name(id='_ck_sub', ctx=ast.Load()),
                                              args=[ast.Constant(0), node.operand], keywords=[]), node)
        return node

    def visit_AugAssign(self, node):
        self.generic_visit(node)
        name = self.OPS.get(type(node.op))
        if name is None or not isinstance(node.target, ast.Name):
            return node
        load = ast.Name(id=node.target.id, ctx=ast.Load())
        call = ast.Call(func=ast.Name(id=name, ctx=ast.Load()), args=[load, node.value], keywords=[])
        return ast.copy_location(ast.Assign(targets=[node.target], value=call), node)


def cpython_reference(source):
    import ail_syntax
    tree = _Checked().visit(ast.parse(source))
    tree.body = [st for st in tree.body if not (isinstance(st, ast.Expr) and isinstance(st.value, ast.Call)
                                                and ast.unparse(st.value).startswith('sys.exit'))]
    ast.fix_missing_locations(tree)
    env = {'_ck_add': _ck(lambda a, b: a + b), '_ck_sub': _ck(lambda a, b: a - b),
           '_ck_mul': _ck(lambda a, b: a * b), '__name__': 'ail_ref'}
    for checked in ('__ail_checked_int__', '__ail_checked_str__', '__ail_checked_bool__', '__ail_checked_void__'):
        env[checked] = object
    out = io.StringIO()
    with redirect_stdout(out):
        exec(compile(tree, 'ail_ref', 'exec'), env)
        env['main']()
    return out.getvalue()


def build(directory, name, source):
    path, exe, debug = Path(directory, name + '.ail'), Path(directory, name), Path(directory, name + '.d')
    path.write_text(source)
    built = subprocess.run([sys.executable, str(ROOT / 'ail_chatgpt.py'), 'compile', str(path), '-o', str(exe),
                            '--debug-dir', str(debug)], capture_output=True, text=True, timeout=600)
    return built, exe, debug / 'program.c'


def function_text(c_source, name):
    m = re.search(r'^int64_t %s\([^;\n]*\) \{\n.*?^}\n' % re.escape(name), c_source, re.M | re.S)
    return m.group(0) if m else ''


class RangeCheckTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.edges = build(cls.tmp.name, 'edges', EDGES)

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def test_edges_match_cpython_with_int64_checks(self):
        built, exe, _ = self.edges
        self.assertEqual(built.returncode, 0, built.stdout + built.stderr)
        ran = subprocess.run([str(exe)], capture_output=True, text=True, timeout=120)
        self.assertEqual(ran.returncode, 0, ran.stderr)
        self.assertEqual(ran.stdout, cpython_reference(EDGES))

    def test_edges_elide_checks(self):
        built, _, program = self.edges
        self.assertEqual(built.returncode, 0, built.stdout + built.stderr)
        c = program.read_text()
        self.assertNotIn('ck_add', function_text(c, 'top_loop'))          # i + 1 with i < MAXV
        self.assertIn('ck_sub', function_text(c, 'bottom_loop'))          # i - 1 with i >= lo unknown
        self.assertNotIn('ck_add', function_text(c, 'while_lt'))          # i += 1 under i < n
        self.assertIn('ck_add', function_text(c, 'while_le'))             # i <= n: i + 1 may overflow
        self.assertNotIn('ck_mul', function_text(c, 'square_guard'))
        self.assertIn('ck_mul', function_text(c, 'square_loose'))
        self.assertNotIn('ail_flist_get', function_text(c, 'ring'))       # h[li], h[ri] wrap-around
        self.assertNotIn('ail_bytes_get', function_text(c, 'bytes_sum'))
        if LEGACY_C:        # (the IR owns these lists and emits its own checked read)
            self.assertIn('ail_list_get', function_text(c, 'shrinking'))  # resized in the loop
            self.assertIn('ail_list_get', function_text(c, 'rebuilt'))    # rebound in the loop
        self.assertIn('ck_add', function_text(c, 'elem_max'))             # an element may be MAXV

    @unittest.skipUnless(shutil.which('gcc'), 'gcc is not available')
    def test_edges_under_sanitizers(self):
        built, _, program = self.edges
        self.assertEqual(built.returncode, 0, built.stdout + built.stderr)
        exe = Path(self.tmp.name, 'edges_san')
        cc = subprocess.run(['gcc', '-O1', '-g', '-fsanitize=address,undefined', '-fno-sanitize-recover=all',
                             '-o', str(exe), str(program), '-lm'], capture_output=True, text=True, timeout=600)
        self.assertEqual(cc.returncode, 0, cc.stderr[-2000:])
        env = dict(os.environ, ASAN_OPTIONS='detect_leaks=0')
        ran = subprocess.run([str(exe)], capture_output=True, text=True, timeout=300, env=env)
        self.assertEqual(ran.returncode, 0, ran.stderr[-2000:])
        self.assertEqual(ran.stdout, cpython_reference(EDGES))

    def test_fields_keep_their_checks(self):
        built, exe, _ = build(self.tmp.name, 'fields', FIELDS)
        self.assertEqual(built.returncode, 0, built.stdout + built.stderr)
        ran = subprocess.run([str(exe)], capture_output=True, text=True, timeout=120)
        self.assertEqual(ran.returncode, 0, ran.stderr)
        self.assertEqual(ran.stdout, FIELDS_EXPECTED)

    def test_codegen_proven_and_kept(self):
        built, exe, program = build(self.tmp.name, 'codegen', CODEGEN)
        self.assertEqual(built.returncode, 0, built.stdout + built.stderr)
        ran = subprocess.run([str(exe)], capture_output=True, text=True, timeout=120)
        self.assertEqual(ran.stdout, cpython_reference(CODEGEN))
        c = program.read_text()
        proven, kept = function_text(c, 'proven'), function_text(c, 'kept')
        self.assertTrue(proven and kept)
        for check in ('ail_list_get', 'ail_list_set', 'ck_sub'):
            self.assertNotIn(check, proven)
        sums = [line for line in proven.splitlines() if 'ck_add(' in line]
        if LEGACY_C:
            self.assertTrue(sums and all(line.strip().startswith('v_s = ') for line in sums), sums)  # only s
        self.assertIn('ck_add(', kept)                                    # t = t + i is unbounded
        self.assertIn('ck_mul(', kept)                                    # n * n, n unknown
        self.assertTrue('ail_list_get' in kept or 'ail_list_view_get' in kept)  # xs[n], len(xs) unknown

    def test_analysis_rules_directly(self):
        sys.path.insert(0, str(ROOT / 'python' / 'pkg-v12'))
        import rangecheck
        src = ('def f(n, d):\n'
               '    if n < 1 or n > 10:\n        return 0\n'
               '    xs = [0] * n\n'
               '    s = 0\n'
               '    for i in range(n):\n'
               '        xs[i] = d[i] + d[i]\n'
               '        s = s + xs[i]\n'
               '    j = n - 1\n'
               '    t = xs[j] + xs[0]\n'
               '    xs.append(5)\n'
               '    t = t + xs[j + 1]\n'
               '    xs.pop()\n'
               '    return xs[j + 1] - t\n')
        fn = ast.parse(src).body[0]
        kinds = {'n': 'int', 'i': 'int', 's': 'int', 'j': 'int', 't': 'int', 'xs': 'list', 'd': 'bytes'}
        proofs = rangecheck.analyze(fn, rangecheck.Info(kinds.get))
        marks = {ast.unparse(node): (proofs.ok_arith(node), proofs.ok_index(node)) for node in ast.walk(fn)
                 if isinstance(node, (ast.BinOp, ast.Subscript))}
        self.assertEqual(marks['xs[i]'], (False, True))
        self.assertEqual(marks['d[i] + d[i]'], (True, False))            # 0..510
        self.assertEqual(marks['d[i]'], (False, False))                  # len(d) unknown
        self.assertEqual(marks['s + xs[i]'], (False, False))             # s grows with the loop
        self.assertEqual(marks['xs[j] + xs[0]'], (True, False))          # elements are 0..510
        self.assertEqual(marks['xs[j]'], (False, True))                  # j == n - 1 == len - 1
        reads = [proofs.ok_index(node) for node in ast.walk(fn)
                 if isinstance(node, ast.Subscript) and ast.unparse(node) == 'xs[j + 1]']
        self.assertEqual(reads, [True, False])           # after the append len is n + 1; after the pop n
        self.assertEqual(marks['t + xs[j + 1]'], (True, False))
        self.assertEqual(marks['xs[j + 1] - t'], (True, False))
        # a lambda may shrink a list whenever it is called: such a list is never tracked
        lam = ast.parse('def g(n):\n    xs = [0] * 4\n    f = lambda: xs.pop()\n    f()\n'
                        '    return xs[3] + xs[n % 2]\n').body[0]
        proofs = rangecheck.analyze(lam, rangecheck.Info({'n': 'int', 'xs': 'list'}.get))
        self.assertFalse(any(proofs.ok_index(node) for node in ast.walk(lam) if isinstance(node, ast.Subscript)))


# These tests pin the C text of the legacy emitter, the AIL_IR=0 opt-out (the IR is the default since
# 2026-10-19 and has its own text, pinned in test_ail_ir_*): the whole module builds with AIL_IR=0
# unless the caller set AIL_IR.
_SAVED_AIL_IR = []


def setUpModule():
    import os as _os
    _SAVED_AIL_IR.append(_os.environ.get('AIL_IR'))
    if _SAVED_AIL_IR[-1] is None:
        _os.environ['AIL_IR'] = '0'


def tearDownModule():
    import os as _os
    if _SAVED_AIL_IR.pop() is None:
        _os.environ.pop('AIL_IR', None)


if __name__ == '__main__':
    unittest.main()

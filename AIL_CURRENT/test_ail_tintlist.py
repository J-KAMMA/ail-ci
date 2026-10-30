"""Lists of exact ints on the typed path (docs/design/BIGINT.md section 13), against CPython 3.12.

An int that comes from text (`int(tok)`) or from an accumulator is not provably int64, so a list of them cannot be an int64 list.
The IR has a list kind whose element is a tagged slot (`ail_tint`: a small int inline, a big one a pointer to its magnitude), so the
commonest idiom, `values = [int(t) for t in sys.stdin.read().split()]` followed by sum/min/max/sort/loops, stays on the typed path
and exact.

T1  the corpus programs t001, t010, t012, t314, t459 take the typed path (no "built on the general path" note) and print what
    CPython prints, in stdout and exit code, on ordinary inputs, empty input, the int64 edges and values beyond int64
T2  the probe programs (aliasing, mixed small and big elements in sort/min/max/sum, negative zero, `del`, slice assignment, a
    list passed to a function that appends a big value, the empty list, printing mixed lists) equal CPython; the ones the IR
    lowers stay typed
T3  the same programs under AIL_UNIFIED_FORCE=1 (the forced general build) equal CPython
T4  a big literal in the source keeps the program on the exact general path, with the same answers
"""
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent
HAVE_CC = shutil.which('gcc') is not None or shutil.which('cc') is not None

CORPUS = {
    't001': 'import sys\n\n\ndef main() -> None:\n    data = sys.stdin.read().split()\n    if not data:\n        print("none")\n        return\n    n = int(data[0])\n    values = [int(x) for x in data[1:1 + n]]\n    distinct = sorted(set(values), reverse=True)\n    if len(distinct) >= 2:\n        print(distinct[1])\n    else:\n        print("none")\n\n\nif __name__ == "__main__":\n    main()\n',
    't010': 'import sys\n\n\ndef main() -> None:\n    data = sys.stdin.read().split()\n    if not data:\n        return\n    n = int(data[0])\n    nums = [int(x) for x in data[1:1 + n]]\n    changed = 0\n    result = []\n    for value in nums:\n        if value < 0:\n            changed += 1\n            result.append(-value)\n        else:\n            result.append(value)\n    print(" ".join(str(x) for x in result))\n    print(changed)\n\n\nif __name__ == "__main__":\n    main()\n',
    't012': 'import sys\n\nMOD = 1000003\n\n\ndef main() -> None:\n    data = sys.stdin.read().split()\n    if not data:\n        return\n    n = int(data[0])\n    nums = [int(x) for x in data[1:1 + n]]\n\n    product_all = 1\n    product_nonzero = 1\n    for x in nums:\n        product_all = product_all * x % MOD\n        if x != 0:\n            product_nonzero = product_nonzero * x % MOD\n\n    print(product_all)\n    print(product_nonzero)\n\n\nif __name__ == "__main__":\n    main()\n',
    't314': 'import sys\nfrom bisect import bisect_right\n\n\ndef longest_non_decreasing(nums: list[int]) -> int:\n    tails: list[int] = []\n    for x in nums:\n        pos = bisect_right(tails, x)\n        if pos == len(tails):\n            tails.append(x)\n        else:\n            tails[pos] = x\n    return len(tails)\n\n\ndef longest_bitonic(nums: list[int]) -> int:\n    n = len(nums)\n    if n == 0:\n        return 0\n\n    inc = [1] * n\n    for i in range(n):\n        for j in range(i):\n            if nums[j] < nums[i] and inc[j] + 1 > inc[i]:\n                inc[i] = inc[j] + 1\n\n    dec = [1] * n\n    for i in range(n - 1, -1, -1):\n        for j in range(i + 1, n):\n            if nums[j] < nums[i] and dec[j] + 1 > dec[i]:\n                dec[i] = dec[j] + 1\n\n    return max(inc[i] + dec[i] - 1 for i in range(n))\n\n\ndef main() -> None:\n    nums = [int(tok) for tok in sys.stdin.read().split()]\n    print(longest_non_decreasing(nums), longest_bitonic(nums))\n\n\nif __name__ == "__main__":\n    main()\n',
    't459': 'import sys\n\n\ndef main() -> None:\n    data = sys.stdin.read().split()\n    if not data:\n        return\n\n    n = int(data[0])\n    numbers = [int(token) for token in data[1 : 1 + n]]\n\n    print(*numbers, sep=", ", end="\\n")\n\n    for value in numbers:\n        sys.stdout.write(f"{value}\\n")\n\n    print(*numbers, sep="|")\n\n\nif __name__ == "__main__":\n    main()\n',
}

PROGRAMS = {
    'alias': 'import sys\n\n\ndef main() -> None:\n    xs = [int(t) for t in sys.stdin.read().split()]\n    ys = xs\n    if xs:\n        ys.append(xs[0] * xs[0] * xs[0])\n        xs[0] = xs[0] + 1\n    print(xs, ys)\n    zs = xs[:]\n    zs.append(5)\n    if ys:\n        ys[0] = 7\n    print(xs, zs, len(ys))\n    ws = list(xs)\n    ws.sort()\n    print(ws)\n\n\nif __name__ == "__main__":\n    main()\n',
    'callapp': 'import sys\n\n\ndef push_big(xs: list[int]) -> None:\n    c = xs[0] * xs[0] * xs[0]\n    xs.append(c)\n    xs.append(xs[0] * 2)\n\n\ndef total(xs: list[int]) -> int:\n    t = 0\n    for x in xs:\n        t += x\n    return t\n\n\ndef evens(xs: list[int]) -> list[int]:\n    out = []\n    for x in xs:\n        if x % 2 == 0:\n            out.append(x)\n    return out\n\n\ndef main() -> None:\n    xs = [int(t) for t in sys.stdin.read().split()]\n    if not xs:\n        return\n    print(total(xs))\n    e = evens(xs)\n    print(e, total(e))\n    push_big(xs)\n    print(xs, total(xs))\n\n\nif __name__ == "__main__":\n    main()\n',
    'callarg': 'import math\nimport sys\n\n\ndef is_square(value: int) -> bool:\n    if value < 0:\n        return False\n    root = math.isqrt(value)\n    return root * root == value\n\n\ndef main() -> None:\n    xs = [int(t) for t in sys.stdin.read().split()]\n    sq = [x for x in xs if is_square(x)]\n    print(len(sq), max(sq) if sq else -1)\n    for x in xs:\n        m = abs(x)\n        print(m & (m - 1), m.bit_length())\n\n\nif __name__ == "__main__":\n    main()\n',
    'delslice': 'import sys\n\n\ndef main() -> None:\n    xs = [int(t) for t in sys.stdin.read().split()]\n    if not xs:\n        return\n    c = xs[0] * xs[0] * xs[0]\n    del xs[0]\n    print(xs)\n    xs[0:1] = [c, 5, 6]\n    print(xs)\n    xs[:] = [1, c * c]\n    print(xs)\n    xs.insert(0, 3)\n    xs.reverse()\n    print(xs, xs.index(3), xs.count(3))\n    xs.extend([9, 8])\n    print(xs)\n    print(xs.pop(), xs.pop(0))\n\n\nif __name__ == "__main__":\n    main()\n',
    'empty': 'import sys\n\n\ndef main() -> None:\n    xs = [int(t) for t in sys.stdin.read().split()]\n    print(xs, len(xs), sum(xs))\n    print(sorted(xs), xs[:], xs[1:])\n    print(*xs)\n    print(*xs, sep="-")\n    print(xs == [], not xs, 3 in xs)\n    for x in xs:\n        print(x)\n    try:\n        print(min(xs))\n    except ValueError as e:\n        print("ValueError", e)\n    try:\n        print(max(xs))\n    except ValueError as e:\n        print("ValueError", e)\n    try:\n        print(xs[0])\n    except IndexError as e:\n        print("IndexError", e)\n\n\nif __name__ == "__main__":\n    main()\n',
    'idiom': 'import sys\n\n\ndef main() -> None:\n    values = [int(t) for t in sys.stdin.read().split()]\n    print(len(values))\n    print(sum(values))\n    if values:\n        print(min(values), max(values))\n    print(sorted(values))\n    print(*values, sep=",")\n    print(values)\n    print(" ".join(str(v) for v in values))\n    total = 0\n    for v in values:\n        total += v\n    print(total)\n    if values:\n        print(values[0], values[-1])\n    else:\n        print("none")\n    print(7 in values, 0 in values)\n    if values:\n        print(values[0] * values[0] * values[0] in values)\n\n\nif __name__ == "__main__":\n    main()\n',
    'idx': 'import sys\n\n\ndef main() -> None:\n    xs = [int(t) for t in sys.stdin.read().split()]\n    n = len(xs)\n    for i in range(n):\n        for j in range(i + 1, n):\n            if xs[i] > xs[j]:\n                xs[i], xs[j] = xs[j], xs[i]\n    print(xs)\n    ys = [0] * n\n    for i in range(n):\n        ys[i] = xs[i] * xs[i]\n    print(ys)\n    if ys:\n        ys[0] += ys[-1] * ys[-1]\n    print(ys, xs[-1] if n else 0, xs[n - 1] if n else 0)\n    print(xs.pop() if xs else 0, xs)\n\n\nif __name__ == "__main__":\n    main()\n',
    'mixed': 'import sys\n\n\ndef main() -> None:\n    data = sys.stdin.read().split()\n    n = int(data[0]) if data else 0\n    xs = [int(t) for t in data[1:1 + n]]\n    ys = []\n    for x in xs:\n        ys.append(x * 3 - 1)\n    xs.sort()\n    print(xs)\n    if ys:\n        print(min(ys), max(ys))\n    else:\n        print("empty")\n    s = 0\n    for y in ys:\n        s += y\n        print(s)\n    zs = sorted(set(xs), reverse=True)\n    print(zs)\n    ws = xs[1:3]\n    print(ws, len(ws))\n    if xs:\n        xs[0] = xs[-1] + 1\n        c = xs[0] * xs[0] * xs[0]\n        xs.append(c)\n        xs.append(c * c)\n        xs.append(-c * 2 - 1)\n    print(xs, sum(xs))\n    if xs:\n        print(max(xs), min(xs))\n    xs.sort()\n    print(xs)\n\n\nif __name__ == "__main__":\n    main()\n',
    'ret': 'import sys\n\n\ndef parse(text: str) -> list[int]:\n    return [int(t) for t in text.split()]\n\n\ndef doubled(xs: list[int]) -> list[int]:\n    return [x * 2 for x in xs]\n\n\ndef prefix(xs: list[int]) -> list[int]:\n    out = []\n    acc = 0\n    for x in xs:\n        acc += x\n        out.append(acc)\n    return out\n\n\ndef main() -> None:\n    xs = parse(sys.stdin.read())\n    ps = prefix(xs)\n    ds = doubled(ps)\n    print(xs, ps, ds)\n    print(max(ds) if ds else 0)\n\n\nif __name__ == "__main__":\n    main()\n',
    'zero': 'import sys\n\n\ndef main() -> None:\n    values = [int(t) for t in sys.stdin.read().split()]\n    print(values)\n    print(sum(values), len(values))\n    print(sorted(values))\n    print(max(values) if values else 0)\n\n\nif __name__ == "__main__":\n    main()\n',
}

LITERAL = {
    'big_literal': 'import sys\n\n\ndef main() -> None:\n    xs = [int(t) for t in sys.stdin.read().split()]\n    xs.append(10 ** 20)\n    xs.append(2 ** 63)\n    xs.append(-2 ** 63 - 1)\n    ys = xs\n    ys[0] = 7 if ys else 0\n    print(xs, sum(xs), max(xs), min(xs), sorted(ys))\n    print(10 ** 20 in xs, 2 ** 63 in xs)\n    del xs[1]\n    xs[1:2] = [10 ** 20, 5]\n    print(xs, len(xs))\n\n\nif __name__ == "__main__":\n    main()\n',
}

TYPED = ['alias', 'idx', 'mixed', 'ret', 'zero']
INPUTS = [
    '',
    '\n',
    '5',
    '1 2 3',
    '3 1 2',
    '-0 +0 -00 0',
    '5 3 99999999999999999999 9 -99999999999999999999 2',
    '3 9223372036854775807 9223372036854775808 -9223372036854775809',
    '4 -9223372036854775808 -9223372036854775807 9223372036854775806 9223372036854775807',
    '4 100000000000000000000 100000000000000000000 -5 7',
    '6 9223372036854775807 9223372036854775807 9223372036854775807 5 -9223372036854775808 1',
    '7 1 7 7 0 -3 1000000000000 2',
    '2 4611686018427387904 -4611686018427387905',
    '3 4294967296 4294967297 -4294967295',
]
# t314 reads one line of numbers (no count)
LINE_INPUTS = ['', '\n', '5', '3 1 2 2 5 4 9 1 7 3', '3 99999999999999999999 2 -99999999999999999999 5 4 100000000000000000000',
               '9223372036854775807 9223372036854775808 -9223372036854775809 5', '-5 -5 -5', '1 3 2 4 3 5 1']


def compile_default(directory, text, name, force=False):
    source, exe = Path(directory, name + '.py'), Path(directory, name + ('_f' if force else '_x'))
    source.write_text(text, encoding='utf-8')
    env = dict(os.environ, AIL_NO_CACHE='1')
    for key in ('AIL_NO_GENERAL', 'AIL_UNIFIED_FORCE', 'AIL_QUIET_FALLBACK'):
        env.pop(key, None)
    if force:
        env['AIL_UNIFIED_FORCE'] = '1'
    res = subprocess.run([sys.executable, '-B', str(ROOT / 'ail_chatgpt.py'), 'compile', source.name, '-o', exe.name],
                         cwd=directory, capture_output=True, text=True, timeout=900, env=env)
    return res, exe, source


def typed(res):
    return 'built on the general path' not in res.stderr


@unittest.skipUnless(HAVE_CC, 'needs a C compiler')
class TintList(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.mkdtemp(prefix='tintlist_')

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp, ignore_errors=True)

    def check(self, text, name, inputs, expect_typed=None, force=False):
        res, exe, source = compile_default(self.tmp, text, name, force)
        self.assertEqual(res.returncode, 0, res.stderr[-1500:])
        if expect_typed is not None and not force:
            self.assertEqual(typed(res), expect_typed, res.stderr[-600:])
        for stdin in inputs:
            want = subprocess.run([sys.executable, str(source)], input=stdin.encode('utf-8'), capture_output=True, timeout=300)
            got = subprocess.run([str(exe)], input=stdin.encode('utf-8'), capture_output=True, timeout=300)
            self.assertEqual(got.stdout, want.stdout, (name, stdin))
            self.assertEqual(got.returncode, want.returncode, (name, stdin, got.stderr[-200:]))

    # T1
    def test_corpus_programs_typed_and_equal(self):
        for name in ('t001', 't010', 't012', 't459'):
            self.check(CORPUS[name], name, INPUTS, expect_typed=True)

    def test_corpus_t314_across_functions_typed_and_equal(self):
        self.check(CORPUS['t314'], 't314', LINE_INPUTS, expect_typed=True)

    # T2
    def test_probe_programs_equal_and_typed_where_lowered(self):
        for name, text in sorted(PROGRAMS.items()):
            self.check(text, 'p_' + name, INPUTS, expect_typed=True if name in TYPED else None)

    # T3
    def test_probe_programs_equal_under_forced_general_build(self):
        for name in ('mixed', 'ret', 'idx', 'alias'):
            self.check(PROGRAMS[name], 'f_' + name, INPUTS, force=True)
        self.check(CORPUS['t314'], 'f_t314', LINE_INPUTS, force=True)

    # T4
    def test_big_literal_keeps_the_exact_general_path(self):
        for name, text in sorted(LITERAL.items()):
            self.check(text, 'l_' + name, INPUTS, expect_typed=False)


if __name__ == '__main__':
    unittest.main()

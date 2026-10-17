"""Library batch 3: random, itertools, functools and json, each compared with CPython.

Every program below is ordinary Python. CPython runs it as the oracle, the compiled program (the Python
syntax, AIL_NO_GENERAL=1 so the typed path must take it) prints the same bytes, or the spelling is
refused by name at compile time -- there is no third outcome where the numbers differ.

* random: MT19937 in the C runtime, bit for bit CPython 3.12 after random.seed(<int>): random, randint,
  randrange (1 to 3 arguments), uniform, gauss, choice, shuffle, sample. Generated: 12000 operations on
  random seeds / ranges / list sizes, errors included. Unseeded use is refused.
* itertools: count, repeat, chain, chain.from_iterable, islice, accumulate, groupby, pairwise,
  zip_longest, product, permutations, combinations, combinations_with_replacement, in for statements,
  comprehensions and the list / sum / any / all consumers. Generated: 6000 random inputs times about 30
  constructs, every item folded into an order-sensitive checksum.
* functools: reduce, lru_cache / cache (shared across calls, threaded through callers), cmp_to_key.
* json: json.loads into a declared type with CPython's error messages (generated: valid and mutated
  documents), json.dumps of typed values and literals with indent / sort_keys / separators /
  ensure_ascii (generated round trips).
"""
import json
import os
import random
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def compile_python(directory, text, name):
    source, exe = Path(directory, name + ".ail"), Path(directory, name)
    source.write_text(text, encoding="utf-8")
    built = subprocess.run([sys.executable, "-B", str(ROOT / "ail_chatgpt.py"), "compile", source.name,
                            "--syntax", "python", "-o", exe.name], cwd=directory, capture_output=True,
                           text=True, timeout=900, env=dict(os.environ, AIL_NO_GENERAL="1"))
    return built, source, exe


RANDOM_PROGRAM = r'''import random
import sys


def main() -> int:
    random.seed(0)
    for line in sys.stdin:
        f = line.split()
        op = int(f[0])
        a = int(f[1])
        b = int(f[2])
        c = int(f[3])
        n = a % 21
        xs = list(range(n))
        if op == 0:
            random.seed(a)
        elif op == 1:
            print(random.random())
        elif op == 2:
            try:
                print(random.randint(a, b))
            except ValueError:
                print("VE")
        elif op == 3:
            try:
                print(random.randrange(a))
            except ValueError:
                print("VE")
        elif op == 4:
            try:
                print(random.randrange(a, b))
            except ValueError:
                print("VE")
        elif op == 5:
            try:
                print(random.randrange(a, b, c))
            except ValueError:
                print("VE")
        elif op == 6:
            print(random.uniform(a / 8.0, b / 8.0))
        elif op == 7:
            print(random.gauss(a / 8.0, abs(b / 8.0)))
        elif op == 8:
            try:
                print(random.choice(xs))
            except IndexError:
                print("IE")
        elif op == 9:
            random.shuffle(xs)
            for v in xs:
                print(v, end=" ")
            print()
        else:
            try:
                ys = random.sample(xs, b % (n + 3) - 1)
                for v in ys:
                    print(v, end=" ")
                print()
            except ValueError:
                print("VE")
    return 0


main()
'''


def random_input(count=12000):
    rng = random.Random(77)
    lines = []
    big = [0, 1, -1, 2, 7, 255, 2 ** 31, 2 ** 32, 2 ** 40, 2 ** 62, 2 ** 63 - 1, -2 ** 63]

    def num():
        k = rng.random()
        if k < 0.4:
            return rng.randint(-20, 100)
        if k < 0.6:
            return rng.choice(big)
        return rng.randint(-10 ** 6, 10 ** 6)

    for _ in range(count):
        op = rng.randint(0, 10) if rng.random() < 0.9 else 0
        if op == 0:
            lines.append("0 %d 0 0" % rng.choice([rng.randint(-10 ** 9, 10 ** 9), rng.choice(big), rng.randint(0, 1000)]))
            continue
        a, b, c = num(), num(), num()
        if op in (2, 4, 5):
            if rng.random() < 0.5:
                b = a + rng.randint(-3, 400)
            if op == 5 and rng.random() < 0.7:
                c = rng.choice([1, 2, 3, -1, -2, 7, -5, 0])
            if not (-2 ** 63 <= b < 2 ** 63 - 1):
                b = a
            if b - a >= 2 ** 63 or a - b >= 2 ** 63:
                a, b = 0, 10
        if op in (3,) and rng.random() < 0.6:
            a = rng.randint(-2, 100)
        lines.append("%d %d %d %d" % (op, a, b, c))
    return ("\n".join(lines) + "\n").encode()


ITER_BODY = [
    # (name, loop header, statements before the folding step, folded value)
    ("pr2", "for a, b in product(xs, ys):", [], "a * 7 + b"),
    ("pr3", "for a, b, d in product(xs, ys, xs):", [], "a * 7 + b * 3 + d"),
    ("prr", "for a, b in product(ys, repeat=2):", [], "a * 5 + b"),
    ("perm", "for p in permutations(xs):", [], "len(p) + sum(p) * 5 + (p[0] if len(p) > 0 else 9)"),
    ("pe2", "for a, b in permutations(xs, 2):", [], "a * 11 + b"),
    ("pek", "for p in permutations(xs, k):", [], "len(p) * 3 + sum(p) * 7"),
    ("cb2", "for a, b in combinations(ys, 2):", [], "a * 11 + b"),
    ("cbk", "for p in combinations(xs, k):", [], "len(p) * 3 + sum(p) * 7 + (p[0] if len(p) > 0 else 5)"),
    ("cw2", "for a, b in combinations_with_replacement(xs, 2):", [], "a * 13 + b"),
    ("cwk", "for p in combinations_with_replacement(ys, k % 4):", [], "len(p) * 3 + sum(p) * 7"),
    ("ac", "for v in accumulate(xs):", [], "v"),
    ("acm", "for v in accumulate(xs, lambda s, t: (s * t) % 1009):", [], "v"),
    ("aci", "for v in accumulate(ys, initial=j):", [], "v"),
    ("acx", "for v in accumulate(xs, max):", [], "v"),
    ("ch", "for v in chain(xs, ys, xs):", [], "v"),
    ("chb", "for v in chain(ys, xs):", ["if c == j:", "    break"], "v"),
    ("chr", "for v in chain.from_iterable([xs, ys, xs]):", [], "v"),
    ("is1", "for v in islice(chain(xs, ys), k, j + k, 2):", [], "v"),
    ("is2", "for v in islice(xs, j):", [], "v"),
    ("is3", "for v in islice(count(j, 3), k):", [], "v"),
    ("is4", "for v in islice(ys, 1, None, 2):", [], "v"),
    ("cn", "for v in count(j, 2):", ["if c >= 5:", "    break"], "v"),
    ("rp", "for v in repeat(j, k):", [], "v"),
    ("gb", "for key, g in groupby(sorted(xs)):", [], "key * 17 + len(list(g))"),
    ("gk", "for key, g in groupby(xs, key=lambda v: v % 3):", [], "key * 17 + sum(g)"),
    ("pw", "for a, b in pairwise(xs):", [], "a * 3 + b"),
    ("zl", "for a, b in zip_longest(xs, ys, fillvalue=-1):", [], "a * 3 + b"),
    ("zc", "for i, v in zip(count(1), xs):", [], "i * 3 + v"),
    ("cmp1", "for w1 in [a * b for a, b in product(xs, ys) if a != b]:", [], "w1"),
    ("cmp2", "for w2 in [len(p) + sum(p) for p in combinations(ys, 2)]:", [], "w2"),
]


def iter_program():
    lines = ["import sys",
             "from itertools import product, permutations, combinations, combinations_with_replacement, accumulate, "
             "chain, islice, count, repeat, groupby, pairwise, zip_longest",
             "from functools import reduce", "", "", "def main() -> int:", "    for line in sys.stdin:",
             "        f = line.split()", "        n = int(f[0])", "        m = int(f[1])", "        k = int(f[2])",
             "        j = int(f[3])", "        xs: list[int] = []", "        ys: list[int] = []",
             "        for i in range(n):", "            xs.append(int(f[4 + i]))", "        for i in range(m):",
             "            ys.append(int(f[4 + n + i]))"]
    for name, header, pre, value in ITER_BODY:
        lines += ["        h = 0", "        c = 0", "        " + header]
        lines += ["            " + p for p in pre]
        lines += ["            h = (h * 131 + (%s)) %% 1000000007" % value, "            c += 1",
                  "        print(\"%s\", h, c)" % name]
    lines += [
        "        s1 = sum(a * b for a, b in product(xs, ys))",
        "        s2 = len([1 for a, b in combinations(xs, 2) if a < b])",
        "        s3 = any(a == b for a, b in product(xs, ys))",
        "        s4 = all(a < b for a, b in pairwise(xs))",
        "        print(\"agg\", s1, s2, s3, s4, sum(accumulate(xs)), len(list(chain(xs, ys))))",
        "        r1 = reduce(lambda a, b: (a * 3 + b) % 1000000007, xs, 1)",
        "        print(\"red\", r1)",
        "        if n > 0:",
        "            print(\"red2\", reduce(lambda a, b: a * 2 - b, xs), reduce(max, xs), max(accumulate(xs)))",
        "    return 0", "", "", "main()", ""]
    return "\n".join(lines)


def iter_input(count=6000):
    rng = random.Random(5)
    lines = []
    for _ in range(count):
        n, m = rng.randint(0, 5), rng.randint(0, 4)
        k, j = rng.randint(0, 6), rng.randint(0, 7)
        xs = [rng.randint(-9, 9) for _ in range(n)]
        if rng.random() < 0.3:
            xs = sorted(xs)
        ys = [rng.randint(-9, 9) for _ in range(m)]
        lines.append(" ".join(str(v) for v in [n, m, k, j, *xs, *ys]))
    return ("\n".join(lines) + "\n").encode()


class Batch3Tests(unittest.TestCase):
    def same_as_cpython(self, text, name, stdin=b"", oracle_text=None):
        with tempfile.TemporaryDirectory() as directory:
            built, source, exe = compile_python(directory, text, name)
            self.assertEqual(built.returncode, 0, built.stdout + built.stderr)
            oracle = Path(directory, name + "_oracle.py")
            oracle.write_text(oracle_text if oracle_text is not None else text, encoding="utf-8")
            ran = subprocess.run([str(exe)], input=stdin, capture_output=True, timeout=300)
            expected = subprocess.run([sys.executable, str(oracle)], input=stdin, capture_output=True, timeout=300)
            self.assertEqual(expected.returncode, 0, expected.stderr)
            self.assertEqual((ran.returncode, ran.stdout), (0, expected.stdout), ran.stderr[:500])
            return expected.stdout

    def refused(self, text, wanted, name="prog"):
        with tempfile.TemporaryDirectory() as directory:
            built, _, exe = compile_python(directory, text, name)
            self.assertEqual(built.returncode, 3, built.stdout + built.stderr)
            self.assertIn(wanted, built.stderr)
            self.assertFalse(exe.exists())

    # -- random ---------------------------------------------------------------------------------------
    def test_random_generated_operations_are_bit_exact(self):
        out = self.same_as_cpython(RANDOM_PROGRAM, "random_fuzz", random_input())
        self.assertGreater(len(out.split(b"\n")), 8000)

    def test_random_unseeded_and_unbuilt_are_refused(self):
        self.refused("import random\n\n\ndef main():\n    print(random.random())\n\n\nmain()\n",
                     "random without random.seed(<int>)")
        self.refused("import random\n\n\ndef main():\n    random.seed()\n    print(random.random())\n\n\nmain()\n",
                     "seeding from the clock")
        self.refused("import random\n\n\ndef main():\n    random.seed(1)\n    print(random.triangular(1, 2))\n\n\n"
                     "main()\n", "random.triangular is not built")
        self.refused("import random\n\n\ndef main():\n    random.seed('abc')\n\n\nmain()\n", "only an int seed")

    # -- itertools ---------------------------------------------------------------------------------------
    def test_itertools_generated_sequences_match_cpython(self):
        out = self.same_as_cpython(iter_program(), "iter_fuzz", iter_input())
        self.assertGreater(len(out.split(b"\n")), 150000)

    def test_itertools_shapes(self):
        for name in ("i1", "i2", "i3"):
            self.same_as_cpython(SHAPES[name], "shape_" + name)

    def test_itertools_refusals_are_named(self):
        head = "import itertools\n\n\ndef main():\n    xs = [1, 2]\n"
        self.refused(head + "    it = itertools.chain(xs, xs)\n    print(1)\n\n\nmain()\n", "itertools.chain used here")
        self.refused(head + "    for v in itertools.cycle(xs):\n        print(v)\n\n\nmain()\n", "itertools.cycle is not built")
        self.refused(head + "    for v in itertools.permutations(xs):\n        print(v)\n\n\nmain()\n",
                     "holds a tuple in CPython")
        self.refused(head + "    for v in itertools.zip_longest(xs, xs):\n        print(v)\n\n\nmain()\n",
                     "fillvalue")
        self.refused(head + "    d = {1: 2}\n    for v in itertools.chain(xs, d):\n        print(v)\n\n\nmain()\n",
                     "not known to be a list")
        self.refused(head + "    for v in itertools.chain(xs, xs):\n        xs = [3]\n        print(v)\n\n\nmain()\n",
                     "assigned inside the loop")

    # -- functools -----------------------------------------------------------------------------------------
    def test_functools_cache_reduce_cmp_to_key(self):
        self.same_as_cpython(SHAPES["f1"], "functools_shapes")

    def test_functools_generated_cmp_and_cache(self):
        rng = random.Random(9)
        lines = [" ".join(str(rng.randint(-99, 99)) for _ in range(rng.randint(0, 9))) for _ in range(1500)]
        self.same_as_cpython(CMP_PROGRAM, "cmp_fuzz", ("\n".join(lines) + "\n").encode())

    def test_functools_refusals_are_named(self):
        self.refused("from functools import lru_cache\n\n\n@lru_cache(maxsize=None)\ndef f(n: int) -> int:\n"
                     "    print(n)\n    return n\n\n\ndef main():\n    print(f(1))\n\n\nmain()\n", "pure function")
        self.refused("from functools import lru_cache\n\n\n@lru_cache\ndef f(n: float) -> int:\n    return 1\n\n\n"
                     "def main():\n    print(f(1.5))\n\n\nmain()\n", "annotated int, str or bool")
        self.refused("from functools import lru_cache\n\n\n@lru_cache\ndef f(n: int) -> int:\n    return n\n\n\n"
                     "def main():\n    print(f.cache_info())\n\n\nmain()\n", "cache_info")

    # -- json ----------------------------------------------------------------------------------------------
    def test_json_shapes(self):
        self.same_as_cpython(SHAPES["j1"], "json_shapes")

    def test_json_generated_documents(self):
        docs = json_documents()
        ail = JSON_PROGRAM.replace("@MSG@", "e.message")
        py = JSON_PROGRAM.replace("@MSG@", "str(e)").replace("#CHK:", "")
        py = py.replace("def main()", JSON_ORACLE_GUARD + "def main()", 1)
        out = self.same_as_cpython(ail, "json_fuzz", docs, oracle_text=py)
        self.assertGreater(len(out.split(b"\n")), 10000)

    def test_json_refusals_are_named(self):
        self.refused("import json\n\n\ndef main():\n    d = json.loads('[1]')\n    print(len(d))\n\n\nmain()\n",
                     "the type of the result is not declared")
        self.refused("import json\n\n\ndef main():\n    d: list[dict[str, int]] = json.loads('[]')\n\n\nmain()\n",
                     "is not built (built:")
        self.refused("import json\n\n\ndef main():\n    xs = []\n    print(json.dumps(xs, default=str))\n\n\nmain()\n",
                     "default=")

    def test_json_type_mismatch_is_loud(self):
        text = ("import json\n\n\ndef main():\n    xs: list[int] = json.loads('[1, 2.5]')\n    print(len(xs))\n\n\nmain()\n")
        with tempfile.TemporaryDirectory() as directory:
            built, _, exe = compile_python(directory, text, "loud")
            self.assertEqual(built.returncode, 0, built.stderr)
            ran = subprocess.run([str(exe)], capture_output=True, timeout=60)
            self.assertNotEqual(ran.returncode, 0)
            self.assertIn(b"declared type needs an int", ran.stderr)


SHAPES = {}
SHAPES['i1'] = r'''import itertools
from itertools import product, permutations, combinations, accumulate, chain, islice, count, repeat, groupby, pairwise, zip_longest, combinations_with_replacement


def main() -> int:
    xs = [1, 2, 3]
    ys = [10, 20]
    for a, b in product(xs, ys):
        print(a, b)
    for a, b in permutations(xs, 2):
        print("p", a, b)
    for a, b, c in permutations(xs):
        print("pp", a, b, c)
    for a, b in combinations(xs, 2):
        print("c", a, b)
    for a, b in combinations_with_replacement(xs, 2):
        print("cw", a, b)
    for p in permutations(xs):
        print("pl", p[0], p[1], p[2], len(p), sum(p))
    for v in accumulate(xs):
        print("acc", v)
    for v in accumulate(xs, lambda s, t: s * t):
        print("accm", v)
    for v in accumulate(xs, initial=100):
        print("acci", v)
    for v in chain(xs, ys, [7]):
        print("ch", v)
    for v in islice(xs, 1, 3):
        print("is", v)
    for v in islice(count(5, 2), 4):
        print("ic", v)
    for v in repeat(9, 3):
        print("rp", v)
    for i, x in zip(count(1), xs):
        print("zc", i, x)
    for a, b in pairwise(xs):
        print("pw", a, b)
    for a, b in zip_longest(xs, ys, fillvalue=0):
        print("zl", a, b)
    words = ["aa", "ab", "ba", "bb", "bc"]
    for k, g in groupby(words, key=lambda w: w[0]):
        n = 0
        for w in g:
            n += 1
        print("g", k, n)
    for k, g in groupby([1, 1, 2, 3, 3, 3]):
        print("gi", k, len(list(g)))
    total = sum(a * b for a, b in product(xs, ys))
    print(total)
    sq = [a + b for a, b in combinations(xs, 2) if a + b > 3]
    print(len(sq), sq[0])
    print(sum(accumulate(xs)))
    print(len(list(chain(xs, ys))))
    print(any(a == b for a, b in product(xs, ys)), all(a < b for a, b in product(xs, ys)))
    return 0


main()
'''
SHAPES['i2'] = r'''import itertools
import functools
from itertools import chain, islice, count, repeat, product, permutations, combinations, accumulate
from functools import reduce


def total(xs: list[int]) -> int:
    t = 0
    for a, b in combinations(xs, 2):
        t += a * b
    return t


def firstbig(xs: list[int], ys: list[int]) -> int:
    for v in chain(xs, ys):
        if v > 5:
            return v
    return -1


def main() -> int:
    xs = [4, 1, 3]
    ys = [9, 2]
    empty: list[int] = []
    print(total(xs), total(empty), firstbig(xs, ys), firstbig(ys, xs), firstbig(empty, empty))
    for v in chain(empty, xs, empty, ys):
        if v == 1:
            continue
        print("c", v)
        if v == 9:
            break
    for v in islice(xs, 0, None, 2):
        print("s2", v)
    for v in islice(chain(xs, ys), 1, 4):
        print("ci", v)
    for v in islice(xs, 5):
        print("big", v)
    for v in islice(count(), 0):
        print("never", v)
    for x in count(0.5, 0.25):
        if x > 1.6:
            break
        print("cf", x)
    for s in repeat("ab"):
        print(s)
        break
    n = 0
    for i in count(10):
        n += i
        if n > 40:
            print("n", i, n)
            break
    for t in product(range(2), [5, 6]):
        print("pt", t[0], t[1])
    for a, b in product(xs, repeat=2):
        if a == b:
            continue
        print("pr", a, b)
    for p in permutations(range(3), 2):
        print("pp", p[0], p[1])
    r = reduce(lambda a, b: a * b, xs)
    q = reduce(lambda a, b: a + b, xs, 100)
    e = reduce(max, ys)
    print(r, q, e)
    sq = [x * x for x in chain(xs, ys) if x % 2 == 1]
    print(len(sq), sq[0])
    print(sorted(chain(xs, ys)) == [1, 2, 3, 4, 9])
    best = max(a + b for a, b in product(xs, ys))
    print(best)
    acc = list(accumulate(xs, max))
    print(acc[0], acc[1], acc[2])
    for za, zb in zip(count(1), "xyz"):
        print(za, zb)
    try:
        for v in islice(xs, -1):
            print(v)
    except ValueError:
        print("ve")
    return 0


main()
'''
SHAPES['i3'] = r'''import math
import operator
from operator import mul
from functools import reduce
from itertools import accumulate


def main() -> int:
    xs = [12, 18, 30]
    print(reduce(math.gcd, xs))
    print(reduce(operator.add, xs), reduce(mul, xs, 1))
    print(list(accumulate(xs, operator.mul))[2])
    print(sorted(xs, key=operator.neg)[0])
    return 0


main()
'''
SHAPES['f1'] = r'''import functools
from functools import lru_cache, cache, cmp_to_key


@lru_cache(maxsize=None)
def fib(n: int) -> int:
    if n < 2:
        return n
    return fib(n - 1) + fib(n - 2)


@functools.cache
def grid(r: int, c: int) -> int:
    if r == 0 or c == 0:
        return 1
    return grid(r - 1, c) + grid(r, c - 1)


@lru_cache(maxsize=128)
def is_pal(s: str) -> bool:
    if len(s) < 2:
        return True
    return s[0] == s[-1] and is_pal(s[1:-1])


@lru_cache
def collatz(n: int) -> int:
    if n == 1:
        return 0
    if n % 2 == 0:
        return 1 + collatz(n // 2)
    return 1 + collatz(3 * n + 1)


def helper(k: int) -> int:
    return fib(k) + grid(k, k)


def by_len(a: int, b: int) -> int:
    return (a % 10) - (b % 10)


def main() -> int:
    for i in range(0, 60, 7):
        print(i, fib(i))
    print(grid(8, 8), helper(5))
    print(is_pal("racecar"), is_pal("abca"), is_pal(""))
    best = 0
    for n in range(1, 3000):
        c = collatz(n)
        if c > best:
            best = c
    print(best)
    xs = [15, 22, 31, 40, 59, 8, 77]
    ys = sorted(xs, key=cmp_to_key(by_len))
    for y in ys:
        print(y, end=" ")
    print()
    zs = sorted(xs, key=cmp_to_key(by_len), reverse=True)
    for z in zs:
        print(z, end=" ")
    print()
    xs.sort(key=cmp_to_key(by_len))
    for x in xs:
        print(x, end=" ")
    print()
    return 0


main()
'''
SHAPES['j1'] = r'''import json
import sys


def parse_scores(text: str) -> dict[str, int]:
    return json.loads(text)


def main() -> int:
    data: dict[str, int] = json.loads('{"a": 1, "b": -22, "c": 333}')
    for k in data:
        print(k, data[k])
    xs: list[int] = json.loads(" [1, 2,\n 3 ] ")
    print(len(xs), xs[2])
    names: list[str] = json.loads('["x", "caf\\u00e9", "\\ud83d\\ude00", "a\\nb"]')
    for n in names:
        print(n, len(n))
    fs: list[float] = json.loads("[1.5, 2.0, -0.0, 1e3, 1E-2]")
    for f in fs:
        print(f)
    grid: list[list[int]] = json.loads("[[1,2],[],[3]]")
    print(len(grid), len(grid[1]), grid[2][0])
    sc = parse_scores('{"q": 5}')
    print(sc["q"])
    try:
        bad: list[int] = json.loads("[1, 2,]")
        print(len(bad))
    except json.JSONDecodeError as e:
        print("err")
    try:
        bad2: list[int] = json.loads('[1, "x"')
        print(len(bad2))
    except ValueError as e:
        print("err")
    name = "wörld"
    count = 3
    ratio = 0.25
    flags = [True, False]
    print(json.dumps({"name": name, "count": count, "ratio": ratio, "ok": True, "none": None, "flags": flags}))
    print(json.dumps(xs), json.dumps(names), json.dumps(fs))
    print(json.dumps(data, sort_keys=True), json.dumps(grid))
    print(json.dumps({"b": [1, 2, {"c": "d"}], "a": []}, indent=2, sort_keys=True))
    print(json.dumps(names, ensure_ascii=False), json.dumps(name), json.dumps("q\"\\\x01\x7f"))
    print(json.dumps({"x": 1, "y": [1, 2]}, separators=(",", ":")))
    print(json.dumps(grid, indent=1))
    print(json.dumps(data, indent="\t"))
    return 0


main()
'''
CMP_PROGRAM = r'''import sys
from functools import cmp_to_key, lru_cache, reduce


def by_mod(a: int, b: int) -> int:
    return (a % 7) - (b % 7)


@lru_cache(maxsize=None)
def tri(n: int) -> int:
    if n <= 0:
        return 0
    return n + tri(n - 1)


def main() -> int:
    for line in sys.stdin:
        xs = [int(t) for t in line.split()]
        ys = sorted(xs, key=cmp_to_key(by_mod))
        zs = sorted(xs, key=cmp_to_key(by_mod), reverse=True)
        t = 0
        for v in ys:
            t = (t * 31 + v) % 1000003
        for v in zs:
            t = (t * 17 + v) % 1000003
        xs.sort(key=cmp_to_key(by_mod))
        for v in xs:
            t = (t * 13 + v) % 1000003
        rr = reduce(lambda a, b: (a * 5 + b) % 1000003, xs, 7)
        print(t, tri(len(xs) * 3), rr)
    return 0


main()
'''

JSON_ORACLE_GUARD = r'''
def _bad(v):
    raise RuntimeError("type")


def _str_ok(s):
    return isinstance(s, str) and not any(0xD800 <= ord(ch) < 0xE000 for ch in s)


def _int_ok(x):
    return type(x) is int and -2 ** 63 <= x < 2 ** 63


def chk_int(xs):
    if not isinstance(xs, list) or not all(_int_ok(x) for x in xs):
        _bad(xs)


def chk_float(xs):
    if not isinstance(xs, list) or any(type(x) is not float for x in xs):
        _bad(xs)


def chk_str(xs):
    if not isinstance(xs, list) or not all(_str_ok(x) for x in xs):
        _bad(xs)


def chk_dict(d):
    if not isinstance(d, dict) or not all(_str_ok(k) and _int_ok(v) for k, v in d.items()):
        _bad(d)


def chk_ll(g):
    if not isinstance(g, list) or not all(isinstance(r, list) and all(_int_ok(x) for x in r) for r in g):
        _bad(g)


'''


def json_documents(count=12000):
    rng = random.Random(21)
    alphabet = ["a", "b", "é", "日", "😀", "\\", '"', " ", "z", "0", "/", "\x01", "\x7f", "\t"]

    def rstr():
        return "".join(rng.choice(alphabet) for _ in range(rng.choice([0, 1, 2, 5, 12])))

    def rint():
        return rng.choice([0, 1, -1, 7, 123456789, -2 ** 63, 2 ** 63 - 1, rng.randint(-1000, 1000)])

    def rfloat():
        return rng.choice([0.0, -0.0, 1.5, 1e22, 5e-324, 1.7976931348623157e308, 0.1, rng.uniform(-1e6, 1e6),
                           rng.uniform(-1, 1) * 10 ** rng.randint(-30, 30)])

    def render(obj):
        kw = {"ensure_ascii": rng.random() < 0.5}
        if rng.random() < 0.2:
            kw["separators"] = (rng.choice([",", ", ", " ,"]), rng.choice([":", ": ", " : "]))
        if rng.random() < 0.15:
            kw["indent"] = rng.choice([0, 1, 2, "\t"])
        return json.dumps(obj, **kw).replace("\n", "\\n") if "indent" not in kw else json.dumps(obj, **kw).replace(
            "\n", " ")

    def mutate(text):
        if not text:
            return text
        pos = rng.randrange(len(text))
        op = rng.choice(["del", "ins", "rep", "trunc", "dup"])
        ch = rng.choice(list('[]{},:"\\ 0123456789.eE+-tfnuNI') + ["\\u12", "\\ud83d", "\x01", "é", "\\ud83d\\ude00"])
        if op == "del":
            return text[:pos] + text[pos + 1:]
        if op == "ins":
            return text[:pos] + ch + text[pos:]
        if op == "rep":
            return text[:pos] + ch + text[pos + 1:]
        if op == "trunc":
            return text[:pos]
        return text[:pos] + text[pos:pos + 3] + text[pos:]

    lines = []
    for _ in range(count):
        kind = rng.choice("ifsdl")
        if kind == "i":
            obj = [rint() for _ in range(rng.randint(0, 6))]
        elif kind == "f":
            obj = [rfloat() for _ in range(rng.randint(0, 6))]
        elif kind == "s":
            obj = [rstr() for _ in range(rng.randint(0, 5))]
        elif kind == "d":
            obj = {rstr(): rint() for _ in range(rng.randint(0, 5))}
        else:
            obj = [[rint() for _ in range(rng.randint(0, 3))] for _ in range(rng.randint(0, 4))]
        text = render(obj)
        for _ in range(rng.choice([0, 0, 0, 1, 2])):
            text = mutate(text)
        text = text.replace("\n", "\\n").replace("\r", "\\r")
        lines.append(kind + text)
    return ("\n".join(lines) + "\n").encode()


JSON_PROGRAM = r'''import json
import sys


def fold(text: str) -> int:
    h = 0
    for ch in text:
        h = (h * 131 + ord(ch)) % 1000000007
    return h


def main() -> int:
    for line in sys.stdin:
        kind = line[0]
        text = line[1:].rstrip("\n")
        try:
            if kind == "i":
                xs: list[int] = json.loads(text)
                #CHK:chk_int(xs)
                print("i", fold(json.dumps(xs)), fold(json.dumps(xs, indent=2)), fold(json.dumps(xs, separators=(",", ":"))))
            elif kind == "f":
                fs: list[float] = json.loads(text)
                #CHK:chk_float(fs)
                print("f", fold(json.dumps(fs)), fold(json.dumps(fs, indent=1)))
            elif kind == "s":
                ss: list[str] = json.loads(text)
                #CHK:chk_str(ss)
                print("s", len(ss), fold(json.dumps(ss)), fold(json.dumps(ss, ensure_ascii=False)))
            elif kind == "d":
                d: dict[str, int] = json.loads(text)
                #CHK:chk_dict(d)
                print("d", len(d), fold(json.dumps(d)), fold(json.dumps(d, sort_keys=True, indent=2)))
            else:
                g: list[list[int]] = json.loads(text)
                #CHK:chk_ll(g)
                print("l", len(g), fold(json.dumps(g)), fold(json.dumps(g, indent="\t")))
        except ValueError as e:
            print("VE", @MSG@)
        except RuntimeError as e:
            print("RT")
    return 0


main()
'''


if __name__ == "__main__":
    unittest.main()

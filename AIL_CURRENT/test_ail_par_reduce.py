"""fbred3: the exact shared-int reduction (`acc += e` / `acc -= e`) and `sum(ex.map(...))`.

Every program is built from one source twice: with `par_range` and with the `range` it stands for.
The outputs and the exit status must agree at AIL_THREADS 1, 2, 4 and 16 (three runs each), as
`docs/design/PAR_REDUCE.md` proves: the chunk partials and prefix bounds are exact `__int128`
values, and the chunk where the sequential loop stops is re-run alone with the checked add.
A spelling outside v1 is refused by name with a `write instead:` line.
"""
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent
THREADS = (1, 2, 4, 16)
RUNS = 3

SUM = "def main():\n    acc = 0\n    for i in %s(0, 100):\n        acc += i\n    print(acc)\nmain()\n"
NEG = "def main():\n    acc = 0\n    for i in %s(0, 100):\n        acc += -3 * i - 7\n    print(acc)\nmain()\n"
SUB = "def main():\n    acc = -10\n    for i in %s(-5, 5):\n        acc -= i\n    print(acc)\nmain()\n"
TWO = ("def main():\n    acc = 0\n    neg = 0\n    for i in %s(0, 100):\n        acc += i\n"
       "        neg -= i\n    print(acc, neg)\nmain()\n")
LIST = ("def main():\n    xs = [100, 3, 2]\n    acc = xs[0]\n    for i in %s(0, 10):\n"
        "        acc += xs[1]\n    print(acc)\nmain()\n")
INNER = ("def main():\n    acc = 0\n    for i in %s(0, 4):\n        for j in range(0, 4):\n"
         "            acc += i * 4 + j\n    print(acc)\nmain()\n")
PREFIX = ("BIG = 4611686018427387904\n\n\ndef main():\n    xs = [BIG, BIG, -9223372036854775803]\n"
          "    acc = 0\n    for i in %s(0, 3):\n        acc += xs[i]\n    print(acc)\nmain()\n")
LAST = ("BIG = 4611686018427387904\n\n\ndef main():\n    xs = [1] * 9 + [BIG, BIG]\n    acc = 0\n"
        "    for i in %s(0, 11):\n        acc += xs[i]\n    print(acc)\nmain()\n")
MIN_OVER = ("BIG = 4611686018427387904\n\n\ndef main():\n    xs = [-BIG, -BIG, -1]\n    acc = 0\n"
            "    for i in %s(0, 3):\n        acc += xs[i]\n    print(acc)\nmain()\n")
EXC_BEFORE = ("BIG = 4611686018427387904\n\n\ndef term(i: int) -> int:\n    if i == 1:\n"
              "        return 1000 // (i - 1)\n    if i >= 3:\n        return BIG\n    return 0\n\n\n"
              "def main():\n    acc = 0\n    for i in %s(0, 8):\n        acc += term(i)\n"
              "    print(acc)\nmain()\n")
EXC_AFTER = ("BIG = 4611686018427387904\n\n\ndef term(i: int) -> int:\n    if i == 1:\n"
             "        return BIG\n    if i == 6:\n        return 1000 // (i - 6)\n    return 0\n\n\n"
             "def main():\n    acc = 0\n    for i in %s(0, 8):\n        acc += term(i)\n"
             "    print(acc)\nmain()\n")
BIGCHUNK = ("BIG = 4611686018427387904\n\n\ndef main():\n    xs = [0] * 2000\n"
            "    for i in range(0, 2000):\n        xs[i] = -1\n    xs[1000] = BIG\n    xs[1500] = BIG\n"
            "    acc = 0\n    for i in %s(0, 2000):\n        acc += xs[i]\n    print(acc)\nmain()\n")
TRY = ("def term(i: int) -> int:\n    x = 1e308\n    if i == 3:\n        return int(x * x)\n    return i\n\n\n"
       "def main():\n    acc = 0\n    try:\n        for i in %s(0, 200):\n            acc += term(i)\n"
       "    except OverflowError:\n        print(\"caught\", acc)\n    acc += 7\n    print(acc)\nmain()\n")
CASES = {
    "small": SUM, "negative": NEG, "subtract": SUB, "two accumulators": TWO, "list item": LIST,
    "inner loop": INNER, "prefix overflows, total fits": PREFIX, "overflow last": LAST,
    "min overflow": MIN_OVER, "exception before overflow": EXC_BEFORE,
    "exception after overflow": EXC_AFTER, "overflow at a chunk boundary": BIGCHUNK,
    "reduction inside try": TRY,
    "n zero": "def main():\n    acc = 7\n    for i in %s(0, 0):\n        acc += i\n    print(acc)\nmain()\n",
    "n one": "def main():\n    acc = 7\n    for i in %s(0, 1):\n        acc += i\n    print(acc)\nmain()\n",
}

SUM_MAP = ("from concurrent.futures import ThreadPoolExecutor\n\n\ndef f(x: int) -> int:\n"
           "    if x == 3:\n        return 1000 // (x - 3)\n    return 4611686018427387904\n\n\n"
           "def main():\n    acc = 0\n    try:\n        with ThreadPoolExecutor(max_workers=3) as ex:\n"
           "            acc = sum(ex.map(f, range(5)))\n    except ZeroDivisionError:\n"
           "        print(\"caught ZeroDivisionError\", acc)\n    print(acc)\nmain()\n")
POOL_MAP = ("from multiprocessing import Pool\n\n\ndef sq(x: int) -> int:\n    return x * x\n\n\n"
            "if __name__ == \"__main__\":\n    with Pool(4) as p:\n        acc = sum(p.map(sq, range(10)))\n"
            "    print(acc)\n")

REFUSED = {
    "a float accumulator": ("def main():\n    acc = 0.0\n    for i in par_range(0, 10):\n"
                            "        acc += 1.5\n    print(acc)\nmain()\n", "write instead:"),
    "the accumulator read in the body": ("def main():\n    out = [0] * 10\n    acc = 0\n"
                                         "    for i in par_range(0, 10):\n        acc += i\n"
                                         "        out[i] = acc\n    print(out[3])\nmain()\n",
                                         "read before the body assigns it"),
    "mixed += and -=": ("def main():\n    acc = 0\n    for i in par_range(0, 10):\n        acc += i\n"
                        "        acc -= 1\n    print(acc)\nmain()\n", "read before the body assigns it"),
    "a list element written in the same body": (
        "def main():\n    ys = [0] * 100\n    acc = 0\n    for i in par_range(0, 100):\n"
        "        acc += i\n        ys[i] = i\n    print(acc, ys[99])\nmain()\n", "write instead:"),
}


def build(directory, name, source):
    path, exe = Path(directory, name + ".py"), Path(directory, name)
    path.write_text(source)
    built = subprocess.run([sys.executable, str(ROOT / "ail_chatgpt.py"), "compile", str(path),
                            "--syntax", "python", "-o", str(exe)], capture_output=True, text=True,
                           timeout=300)
    return built, exe


def run(exe, threads):
    return subprocess.run([str(exe)], capture_output=True, text=True, timeout=120,
                          env=dict(os.environ, AIL_THREADS=str(threads)))


def kind(stderr):
    return stderr.strip().split(":")[0] if stderr.strip() else ""


class ParReduceTests(unittest.TestCase):
    def test_each_shape_matches_its_sequential_twin_at_every_thread_count(self):
        with tempfile.TemporaryDirectory() as directory:
            for number, (name, source) in enumerate(CASES.items()):
                with self.subTest(name):
                    built, par = build(directory, "par%d" % number, source % "par_range")
                    self.assertEqual(built.returncode, 0, built.stdout + built.stderr)
                    built, seq = build(directory, "seq%d" % number, source % "range")
                    self.assertEqual(built.returncode, 0, built.stdout + built.stderr)
                    expected = run(seq, 1)
                    for threads in THREADS:
                        for _ in range(RUNS):
                            got = run(par, threads)
                            self.assertEqual((got.returncode, got.stdout, kind(got.stderr)),
                                             (expected.returncode, expected.stdout, kind(expected.stderr)),
                                             "AIL_THREADS=%d" % threads)

    def test_sum_over_a_map_is_the_sequential_map_then_sum(self):
        with tempfile.TemporaryDirectory() as directory:
            for number, (name, source) in enumerate((("executor", SUM_MAP), ("pool", POOL_MAP))):
                with self.subTest(name):
                    built, par = build(directory, "map%d" % number, source)
                    self.assertEqual(built.returncode, 0, built.stdout + built.stderr)
                    expected = subprocess.run([sys.executable, "-c", source], capture_output=True,
                                              text=True, timeout=120)
                    for threads in THREADS:
                        got = run(par, threads)
                        self.assertEqual((got.returncode, got.stdout),
                                         (expected.returncode, expected.stdout), name)

    def test_out_of_scope_spellings_are_refused_by_name(self):
        with tempfile.TemporaryDirectory() as directory:
            for number, (name, (source, message)) in enumerate(REFUSED.items()):
                with self.subTest(name):
                    built, _ = build(directory, "no%d" % number, source)
                    self.assertNotEqual(built.returncode, 0, name)
                    self.assertIn(message, built.stdout + built.stderr)


if __name__ == "__main__":
    unittest.main()

"""The realistic `random` programs in lab/stdlib/random, compared with CPython 3.12.

Eleven of the twelve build in the default mode; each must print CPython's stdout and exit with its
status.  The twelfth (`secure_token.py`) exercises `random.SystemRandom`, which is still a named
refusal (see lab/stdlib/random/RESULTS.md), so it is not part of the passing set.

The last two tests pin the features added for those programs, on both builds:
`getrandbits(0 / 1 / 32 / 33 / 62 / 63 / -1)`, `normalvariate(mu, sigma)` including keyword,
attribute, list-item and variable arguments, and `choices` with `cum_weights=` and its errors.
"""
import math
import os
import random
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent
LAB = ROOT.parent / "lab" / "stdlib" / "random"
CLI = ROOT / "ail_chatgpt.py"
PKG = ROOT / "python" / "pkg-v12"
if str(PKG) not in sys.path:
    sys.path.insert(0, str(PKG))

PASSING = [
    "card_deck",
    "cumulative_raffle",
    "dice_stats",
    "lottery_ticket",
    "monte_carlo_pi",
    "password_generator",
    "pin_generator",
    "random_walk",
    "rng_class",
    "sampling_errors",
    "weighted_raffle",
]

FEATURES = '''import random


class Box:
    def __init__(self, k: int, mu: float, sigma: float) -> None:
        self.k = k
        self.mu = mu
        self.sigma = sigma


def main() -> None:
    random.seed(123)
    for k in [0, 1, 31, 32, 33, 62, 63]:
        print("k", k, random.getrandbits(k))
    y = 31
    print("var", random.getrandbits(y))
    nums = [7, 32]
    print("list", random.getrandbits(nums[0]), random.getrandbits(nums[1]))
    b = Box(16, -2.0, 3.0)
    print("attr", random.getrandbits(b.k))
    d = {"k": 20}
    print("dict", random.getrandbits(d["k"]))
    try:
        print(random.getrandbits(-1))
    except ValueError as error:
        print("ValueError", error)
    print("n1", random.normalvariate(0.0, 1.0))
    print("n2", random.normalvariate(mu=-2.0, sigma=3.0))
    print("n3", random.normalvariate(b.mu, b.sigma))
    vals = [-1.5, 2.5]
    print("n4", random.normalvariate(vals[0], vals[1]))
    print("n5", random.normalvariate(2.0, -3.0))
    mu = 0.25
    sigma = 4.0
    print("n6", random.normalvariate(mu, sigma))


main()
'''

CHOICES = '''import random


class Box:
    def __init__(self, w: list[int]) -> None:
        self.w = w


def main() -> None:
    random.seed(77)
    p = ["a", "b", "c", "d"]
    print("cum", random.choices(p, cum_weights=[1, 3, 6, 10], k=6))
    print("rel", random.choices(p, weights=[0, 1, 0, 2], k=5))
    print("zero", random.choices(p, cum_weights=[1, 2, 3, 4], k=0))
    print("empty", random.choices([], k=0))
    w = [1, 2, 3, 4]
    c = [10, 20, 40, 100]
    print("cumvar", random.choices(p, cum_weights=c, k=3))
    print("relvar", random.choices(p, weights=w, k=3))
    box = Box([1, 2, 3, 4])
    print("attr", random.choices(p, weights=box.w, k=4))
    d = {"cw": [1, 4, 5, 10]}
    print("dict", random.choices(p, cum_weights=d["cw"], k=2))
    print("neg", random.choices(p, weights=[-1, 2, 3, 4], k=3))
    try:
        random.choices(p, weights=[1, 2, 3, 4], cum_weights=[1, 2, 3, 4])
    except TypeError as error:
        print("TypeError", error)
    try:
        random.choices(p, cum_weights=[1, 2, 3])
    except ValueError as error:
        print("ValueError", error)
    try:
        random.choices(p, cum_weights={0: 1, 1: 3, 2: 6, 3: 10}, k=2)
    except KeyError as error:
        print("KeyError", error)
    try:
        random.choices(p, cum_weights={1, 2, 3, 4}, k=2)
    except TypeError as error:
        print("TypeError", error)
    try:
        random.choices(p, cum_weights=4, k=2)
    except TypeError as error:
        print("TypeError", error)
    try:
        random.choices(p, weights=[0, 0, 0, 0])
    except ValueError as error:
        print("ValueError", error)
    try:
        random.choices(p, weights=[-1, -1, -1, -1])
    except ValueError as error:
        print("ValueError", error)
    try:
        random.choices(p, weights=[float("inf"), 1, 1, 1])
    except ValueError as error:
        print("ValueError", error)
    try:
        random.choices(p, weights=[float("nan"), 1, 1, 1])
    except ValueError as error:
        print("ValueError", error)
    try:
        random.choices([], cum_weights=[], k=0)
    except IndexError as error:
        print("IndexError", error)


main()
'''

CLASS_FEATURES = '''import random


def main() -> None:
    rng = random.Random(321)
    print("bits", [rng.getrandbits(k) for k in [0, 1, 32, 33, 62, 63]])
    print("n1", rng.normalvariate(0.0, 1.0))
    print("n2", rng.normalvariate(mu=-3.0, sigma=0.5))
    p = ["a", "b", "c", "d"]
    print("cum", rng.choices(p, cum_weights=[1, 3, 6, 10], k=6))
    print("rel", rng.choices(p, weights=[1, 2, 3, 4], k=4))
    try:
        rng.getrandbits(-1)
    except ValueError as error:
        print("ValueError", error)
    try:
        rng.choices(p, weights=[1, 2, 3, 4], cum_weights=[1, 2, 3, 4])
    except TypeError as error:
        print("TypeError", error)


main()
'''


def build(directory, source, name, **extra):
    exe = Path(directory) / (name + ".bin")
    env = dict(os.environ, AIL_NO_CACHE="1", AIL_QUIET_FALLBACK="1")
    for key in ("AIL_UNIFIED_FORCE", "AIL_NO_GENERAL"):
        env.pop(key, None)
    env.update(extra)
    done = subprocess.run([sys.executable, "-B", str(CLI), "compile", str(source), "--syntax", "python",
                           "-o", str(exe)], cwd=directory, capture_output=True, text=True, timeout=900, env=env)
    return done, exe


@unittest.skipUnless(LAB.is_dir(), "lab/stdlib/random is not part of this tree")
class StdlibRandomPrograms(unittest.TestCase):
    def check(self, directory, source, name, **extra):
        built, exe = build(directory, source, name, **extra)
        self.assertEqual(built.returncode, 0, built.stdout[-1000:] + built.stderr[-3000:])
        want = subprocess.run([sys.executable, "-X", "utf8", str(source)], cwd=directory, capture_output=True,
                              timeout=300)
        got = subprocess.run([str(exe)], cwd=directory, capture_output=True, timeout=300)
        self.assertEqual(got.returncode, want.returncode, (name, got.stderr[-1000:]))
        self.assertEqual(got.stdout, want.stdout, name)

    def test_lab_programs(self):
        with tempfile.TemporaryDirectory() as directory:
            for name in PASSING:
                with self.subTest(program=name):
                    self.check(directory, LAB / (name + ".py"), name)

    def test_new_features_both_builds(self):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "features.py"
            source.write_text(FEATURES, encoding="utf-8")
            for tag, extra in (("default", {}), ("typed", {"AIL_NO_GENERAL": "1"}),
                               ("general", {"AIL_UNIFIED_FORCE": "1"})):
                with self.subTest(build=tag):
                    self.check(directory, source, "features_" + tag, **extra)

    def test_choices_cum_weights(self):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "choices.py"
            source.write_text(CHOICES, encoding="utf-8")
            for tag, extra in (("default", {}), ("general", {"AIL_UNIFIED_FORCE": "1"})):
                with self.subTest(build=tag):
                    self.check(directory, source, "choices_" + tag, **extra)

    def test_random_object_new_methods(self):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "class_features.py"
            source.write_text(CLASS_FEATURES, encoding="utf-8")
            for tag, extra in (("default", {}), ("general", {"AIL_UNIFIED_FORCE": "1"})):
                with self.subTest(build=tag):
                    self.check(directory, source, "class_features_" + tag, **extra)


class PreludeRandomNewMethods(unittest.TestCase):
    def test_normalvariate_and_cum_weights(self):
        import prelude_random as P
        P.math = math
        rnd = random.Random(17)
        for seed in (0, 1, 7, 321, -9, 2 ** 40 + 3):
            a, b = P.Random(seed), random.Random(seed)
            for _ in range(30):
                mu = rnd.choice([0.0, -3.0, 1.25, 100.0])
                sigma = rnd.choice([0.5, 1.0, 4.0, -2.0])
                self.assertEqual(a.normalvariate(mu, sigma), b.normalvariate(mu, sigma), (seed, mu, sigma))
                n = rnd.randint(1, 8)
                weights = [rnd.randint(1, 20) for _ in range(n)]
                cum = []
                total = 0
                for w in weights:
                    total += w
                    cum.append(total)
                k = rnd.randint(0, 6)
                self.assertEqual(a.choices(list(range(n)), cum_weights=cum, k=k),
                                 b.choices(list(range(n)), cum_weights=cum, k=k), (seed, cum, k))
        for bad, kind in (({0: 1, 1: 2}, KeyError), ({1, 2}, TypeError), (2, TypeError)):
            with self.assertRaises(kind):
                P.Random(1).choices(list(range(2)), cum_weights=bad, k=1)
            with self.assertRaises(kind):
                random.Random(1).choices(list(range(2)), cum_weights=bad, k=1)


if __name__ == "__main__":
    unittest.main()

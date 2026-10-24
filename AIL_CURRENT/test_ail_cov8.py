"""Branch cov8: random.Random on the typed path, compared with CPython 3.12.

The census's first refusals included `Random.randrange must take plain positional arguments, no
defaults, *args or **kwargs`: the typed class lowering has no method defaults, so the typed
prelude (prelude_random_typed.py) spells randrange's one- and three-argument forms as
`randrange1` / `randrange3`.  randlib.py rewrites a call on a proven Random to the right name and
drops the hidden generator when `random.seed` is the only module-level function used.

* PROGRAMS are compiled twice (AIL_UNIFIED_FORCE=1, the general path; and the default build,
  which now stays on the typed path) and must print what CPython prints;
* the typed-only programs must also build with AIL_STRICT=1;
* prelude_random_typed.py is plain Python: random draws are compared with CPython's Random.
"""
import ast
import math
import os
import random
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent
PKG = ROOT / "python" / "pkg-v12"

PROGRAMS = {}
PROGRAMS['forms'] = r'''import random


def show(rng: random.Random, label: str) -> None:
    print(label)
    i = 0
    while i < 4:
        print(rng.randrange(10))
        print(rng.randrange(-5, 5))
        print(rng.randrange(0, 20, 3))
        print(rng.randrange(20, 0, -3))
        print(rng.randint(1, 6))
        print(rng.getrandbits(8))
        print(rng.choice([10, 20, 30]))
        print(rng.uniform(1.0, 2.0))
        i = i + 1


def via_param(rng: random.Random, n: int) -> int:
    return rng.randrange(n, n * 10, 7)


def main() -> None:
    rng = random.Random(7)
    show(rng, "first")
    print(via_param(rng, 3))
    rng.seed(42)
    print(rng.randrange(100))
    print(rng.randrange(100, 200))
    print(rng.randrange(200, 100, -1))
    alias = rng
    print(alias.randrange(5))
    other = random.Random(99)
    print(other.randrange(5))
    print(rng.randrange(5))


if __name__ == "__main__":
    main()
'''
PROGRAMS['seedonly'] = r'''import random


def main() -> None:
    random.seed(7)
    rng = random.Random(7)
    i = 0
    while i < 5:
        print(rng.randrange(100))
        i = i + 1
    print(rng.randint(0, 9))


if __name__ == "__main__":
    main()
'''
PROGRAMS['initcall'] = r'''import random


class Guess:
    def __init__(self, rng: random.Random) -> None:
        self.rng = rng
        self.previous: int = self.rng.randint(1, 13)

    def next_value(self) -> int:
        value = self.rng.randint(1, 13)
        return value


def main() -> None:
    rng = random.Random(11)
    game = Guess(rng)
    print(game.previous)
    print(game.next_value())


if __name__ == "__main__":
    main()
'''
PROGRAMS['module'] = r'''import random


def main() -> None:
    random.seed(5)
    i = 0
    while i < 5:
        print(random.randrange(10))
        print(random.randrange(10, 20))
        print(random.randrange(0, 30, 4))
        print(random.randint(1, 6))
        i = i + 1


if __name__ == "__main__":
    main()
'''

PROGRAMS['shadow'] = r'''import random


class Fake:
    def randrange(self, n: int) -> int:
        return 999


class FakeError(ValueError):
    def randrange(self, n: int) -> int:
        return 888


class Ctx:
    def __enter__(self) -> Fake:
        return Fake()

    def __exit__(self, a: int, b: int, c: int) -> None:
        return None


def main() -> None:
    r = random.Random(1)
    for r in [Fake()]:
        print(r.randrange(10))
    r = random.Random(1)
    with Ctx() as r:
        print(r.randrange(10))
    r = random.Random(1)
    try:
        raise FakeError("x")
    except FakeError as r:
        print(r.randrange(10))
    print(random.Random(1).randrange(10))


main()
'''
PROGRAMS['star'] = r'''import random


def main() -> None:
    r = random.Random(1)
    print(r.randrange(*[1, 10]))
    pair = (1, 10)
    print(r.randrange(*pair))


main()
'''
PROGRAMS['width'] = r'''import random


def main() -> None:
    r = random.Random(1)
    print(r.randrange(2 ** 62))
    print(r.getrandbits(63))
    print(r.randrange(9223372036854775807))
    print(r.randrange(-2 ** 62, -2 ** 62 + 10))
    print(r.randrange(0, 2 ** 62, 3))


main()
'''
PROGRAMS['seedexpr'] = r'''import random


def show(x) -> None:
    print(x)


def main() -> None:
    r = random.Random(7)
    x = random.seed(7)
    print(x)
    if random.seed(8) is None:
        print("none")
    show(random.seed(9))
    print(r.randrange(10))


main()
'''

TYPED_ONLY = ('forms', 'seedonly')


def build(directory, text, name, **env):
    source, exe = Path(directory, name + ".py"), Path(directory, name)
    source.write_text(text, encoding="utf-8")
    built = subprocess.run([sys.executable, "-B", str(ROOT / "ail_chatgpt.py"), "compile", source.name,
                            "--syntax", "python", "-o", exe.name], cwd=directory, capture_output=True,
                           text=True, timeout=1800,
                           env=dict(os.environ, AIL_NO_CACHE="1", AIL_QUIET_FALLBACK="1", **env))
    return built, exe


class Programs(unittest.TestCase):
    def check(self, name, **env):
        text = PROGRAMS[name]
        with tempfile.TemporaryDirectory() as directory:
            oracle = Path(directory, "oracle.py")
            oracle.write_text(text, encoding="utf-8")
            want = subprocess.run([sys.executable, "-X", "utf8", str(oracle)], capture_output=True, timeout=300)
            built, exe = build(directory, text, "p_" + name, **env)
            self.assertEqual(built.returncode, 0, "%s: %s%s" % (name, built.stdout[-400:], built.stderr[-600:]))
            got = subprocess.run([str(exe)], capture_output=True, timeout=300)
            self.assertEqual(got.returncode, want.returncode, "%s: %s" % (name, got.stderr[-300:]))
            self.assertEqual(got.stdout.decode(), want.stdout.decode(), name)

    def test_general_path(self):
        for name in PROGRAMS:
            with self.subTest(program=name):
                self.check(name, AIL_UNIFIED_FORCE="1")

    def test_default_build(self):
        for name in PROGRAMS:
            with self.subTest(program=name):
                self.check(name)

    def test_typed_path(self):
        for name in TYPED_ONLY:
            with self.subTest(program=name):
                self.check(name, AIL_STRICT="1")

    def test_typed_refuses_initializer_method_call(self):
        # The typed prelude lets the typed path reach a field initializer that calls a method on
        # another instance; that stays a by-name refusal (not a KeyError), so the general path can
        # still build the program.
        with tempfile.TemporaryDirectory() as directory:
            built, _ = build(directory, PROGRAMS["initcall"], "refuse", AIL_STRICT="1")
            self.assertEqual(built.returncode, 3, built.stdout[-400:] + built.stderr[-600:])
            self.assertNotIn("Traceback", built.stdout + built.stderr)


class Analysis(unittest.TestCase):
    def test_shadowing_bindings_are_not_random(self):
        sys.path.insert(0, str(PKG))
        try:
            import randlib
        finally:
            sys.path.remove(str(PKG))
        source = ("r = Random(1)\n"
                  "for r in []:\n    pass\n"
                  "r = Random(1)\n"
                  "with ctx as r:\n    pass\n"
                  "r = Random(1)\n"
                  "try:\n    pass\nexcept E as r:\n    pass\n"
                  "r = Random(1)\n"
                  "from m import x as r\n"
                  "r = Random(1)\n")
        self.assertNotIn("r", randlib._scope_known(ast.parse(source), set()))
        self.assertIn("r", randlib._scope_known(ast.parse("r = Random(1)\n"), set()))


class PreludeRandomTyped(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.ns = {"math": math}
        exec(compile((PKG / "prelude_random_typed.py").read_text(encoding="utf-8"),
                     "prelude_random_typed.py", "exec"), cls.ns)

    def test_randrange(self):
        for seed in (0, 1, 7, 42, 123456789, 2 ** 31, 2 ** 63 - 1, -7):
            ours = self.ns["Random"](seed)
            theirs = random.Random(seed)
            for _ in range(30):
                self.assertEqual(ours.randrange1(10), theirs.randrange(10))
                self.assertEqual(ours.randrange(-5, 5), theirs.randrange(-5, 5))
                self.assertEqual(ours.randrange3(0, 20, 3), theirs.randrange(0, 20, 3))
                self.assertEqual(ours.randrange3(20, 0, -3), theirs.randrange(20, 0, -3))
                self.assertEqual(ours.randint(1, 6), theirs.randint(1, 6))
                self.assertEqual(ours.getrandbits(17), theirs.getrandbits(17))
                self.assertEqual(ours.choice([10, 20, 30]), theirs.choice([10, 20, 30]))
                self.assertEqual(ours.uniform(1.0, 2.0), theirs.uniform(1.0, 2.0))

    def test_wide_widths(self):
        ours = self.ns["Random"](1)
        theirs = random.Random(1)
        self.assertEqual(ours.randrange1(2 ** 62), theirs.randrange(2 ** 62))
        self.assertEqual(ours.getrandbits(63), theirs.getrandbits(63))
        self.assertEqual(ours.randrange1(2 ** 63 - 1), theirs.randrange(2 ** 63 - 1))
        self.assertEqual(ours.randrange3(0, 2 ** 62, 3), theirs.randrange(0, 2 ** 62, 3))

    def test_empty_ranges(self):
        ours = self.ns["Random"](1)
        theirs = random.Random(1)
        for mine, theirs_call in ((lambda: ours.randrange1(0), lambda: theirs.randrange(0)),
                                  (lambda: ours.randrange(5, 5), lambda: theirs.randrange(5, 5)),
                                  (lambda: ours.randrange3(0, 5, 0), lambda: theirs.randrange(0, 5, 0)),
                                  (lambda: ours.randrange3(5, 0, 1), lambda: theirs.randrange(5, 0, 1))):
            with self.assertRaises(ValueError) as a:
                mine()
            with self.assertRaises(ValueError) as b:
                theirs_call()
            self.assertEqual(str(a.exception), str(b.exception))


if __name__ == "__main__":
    unittest.main()

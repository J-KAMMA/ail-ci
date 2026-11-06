"""Stage T3a of docs/design/TYPED_ARRAY.md: native f32 arrays (job fdarr1).

Before this stage every program that named `ta.f32` was refused by name (`LATER` in python/pkg-v12/ailarray.py): 0/8 of
array_t3_cases built. After it: 8/8 build and print what CPython prints with the reference `ail_array.py`, in the default
build and with AIL_UNIFIED_FORCE=1. f16 and int8 stay refused by name.

* exactness of the helpers (CPython only): `_ail_ta_r32` (the f32 rounding done in binary64 arithmetic) against `struct`
  on random values of every binade, every kind of tie (f32 value +- half an ulp, and its neighbours), subnormals,
  the overflow threshold and specials; `_ail_ta_bits32` / `_ail_ta_unbits32` against `struct` bit patterns;
* white box: the lowered text of each case, run by CPython with no `ail_array.py` beside it, prints what the reference prints;
* native: each case built in the default build and with AIL_UNIFIED_FORCE=1 prints the same bytes and exit status;
* refusals: f16 and int8 are still refused by name; `//` and `%` on f32 arrays are refused.
"""
import math
import os
import random
import shutil
import struct
import subprocess
import sys
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parent
PKG = ROOT / "python" / "pkg-v12"
sys.path.insert(0, str(PKG))
import ailarray  # noqa: E402

CASES = ROOT / "array_t3_cases"
CC = os.environ.get("PIPE_CC") or shutil.which("cc") or shutil.which("gcc")
NAMES = sorted(p.stem for p in CASES.glob("*.py"))


def prelude_namespace():
    ns = {}
    exec(compile((PKG / "prelude_ailarray.py").read_text(encoding="utf-8"), "prelude_ailarray.py", "exec"), ns)
    return ns


def ref32(x):
    if x != x:
        return math.nan
    try:
        return struct.unpack("<f", struct.pack("<f", x))[0]
    except OverflowError:
        return math.copysign(math.inf, x)


def b64(x):
    return struct.pack("<d", x)


def run_py(directory, name):
    env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1")
    env.pop("PYTHONPATH", None)
    return subprocess.run([sys.executable, "-B", name], cwd=directory, capture_output=True, text=True, timeout=600, env=env)


class Helpers(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.ns = prelude_namespace()

    def test_r32_matches_struct(self):
        r32 = self.ns["_ail_ta_r32"]
        rng = random.Random(3)
        values = [0.0, -0.0, math.inf, -math.inf, 2.0 ** -149, 2.0 ** -150, -2.0 ** -150, 2.0 ** -150 * 1.0000001,
                  2.0 ** -126, 2.0 ** 128 - 2.0 ** 103, math.nextafter(2.0 ** 128 - 2.0 ** 103, 0), 1e300, -1e300,
                  5e-324, 16777217.0, 0.1, 1.7976931348623157e308]
        for _ in range(60000):
            values.append(rng.uniform(1, 2) * 2.0 ** rng.randint(-160, 130) * rng.choice((1, -1)))
        for _ in range(40000):
            u = rng.getrandbits(31)
            v = struct.unpack("<f", struct.pack("<I", u))[0]
            if v != v or v == math.inf:
                continue
            nxt = struct.unpack("<f", struct.pack("<I", u + 1))[0]
            mid = (v + nxt) / 2 if nxt != math.inf else 2.0 ** 128 - 2.0 ** 103
            values += [v, -v, mid, -mid, math.nextafter(mid, 0), math.nextafter(mid, math.inf)]
        for x in values:
            self.assertEqual(b64(r32(x)), b64(ref32(x)), repr(x))
        self.assertEqual(b64(r32(math.nan)), b64(math.nan))

    def test_bits32_round_trip(self):
        bits32, unbits32 = self.ns["_ail_ta_bits32"], self.ns["_ail_ta_unbits32"]
        rng = random.Random(5)
        patterns = [0, 0x80000000, 1, 0x80000001, 0x007FFFFF, 0x00800000, 0x7F7FFFFF, 0xFF7FFFFF, 0x7F800000, 0xFF800000,
                    0x3F800000, 0x3DCCCCCD] + [rng.getrandbits(32) for _ in range(30000)]
        for u in patterns:
            v = struct.unpack("<f", struct.pack("<I", u))[0]
            if v != v:
                continue
            self.assertEqual(b64(unbits32(u)), b64(v), hex(u))
            self.assertEqual(bits32(v), u, hex(u))
        self.assertEqual(bits32(math.nan), 0x7FC00000)
        self.assertTrue(math.isnan(unbits32(0x7FC00000)))
        with self.assertRaises(RuntimeError):
            unbits32(0xFFC00000)


class WhiteBox(unittest.TestCase):
    def test_cases_lowered_text_equals_reference(self):
        for name in NAMES:
            with self.subTest(case=name), tempfile.TemporaryDirectory() as tmp:
                tmp = Path(tmp)
                source = (CASES / (name + ".py")).read_text(encoding="utf-8")
                (tmp / "ref").mkdir()
                shutil.copy(ROOT / "ail_array.py", tmp / "ref" / "ail_array.py")
                (tmp / "ref" / "prog.py").write_text(source, encoding="utf-8")
                notes = []
                text = ailarray.rewrite_text(source, notes)
                self.assertEqual(notes, [])
                (tmp / "low").mkdir()
                (tmp / "low" / "prog.py").write_text(text, encoding="utf-8")
                ref = run_py(tmp / "ref", "prog.py")
                low = run_py(tmp / "low", "prog.py")
                self.assertEqual(ref.returncode, 0, ref.stderr[-500:])
                self.assertEqual(low.stdout, ref.stdout)
                self.assertEqual(low.returncode, ref.returncode)


REFUSED = [
    ("f16", "import ail_array as ta\na = ta.zeros(3, ta.f16)\n", "stage T3"),
    ("int8", "import ail_array as ta\na = ta.zeros(3, ta.int8)\n", "stage T3"),
    ("f32 floordiv", "import ail_array as ta\na = ta.zeros(3, ta.f32)\nb = a // 2.0\n", "// on f32 arrays"),
    ("f32 mod", "import ail_array as ta\na = ta.zeros(3, ta.f32)\nb = 2.0 % a\n", "% on f32 arrays"),
    ("f32 pow", "import ail_array as ta\na = ta.zeros(3, ta.f32)\nb = a ** 2\n", "write instead"),
    ("f32 compare", "import ail_array as ta\na = ta.zeros(3, ta.f32)\nb = a < a\n", "write instead"),
]


class Refusals(unittest.TestCase):
    def test_each_refusal_has_a_line_and_a_hint(self):
        for name, src, needle in REFUSED:
            with self.subTest(case=name):
                notes = []
                text = ailarray.rewrite_text(src, notes)
                self.assertEqual(text, src)
                self.assertTrue(notes, name)
                self.assertGreaterEqual(notes[0][0], 1)
                self.assertIn(needle, notes[0][1])


@unittest.skipUnless(CC, "installed C compiler required")
class Native(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory(prefix="ail-array-t3-")
        cls.dir = Path(cls.tmp.name)
        cls.ref = {}
        for name in NAMES:
            d = cls.dir / name / "ref"
            d.mkdir(parents=True)
            shutil.copy(ROOT / "ail_array.py", d)
            shutil.copy(CASES / (name + ".py"), d / "prog.py")
            cls.ref[name] = run_py(d, "prog.py")

        def build(job):
            name, mode = job
            d = cls.dir / name / mode
            d.mkdir(parents=True)
            shutil.copy(CASES / (name + ".py"), d / "prog.py")
            env = dict(os.environ, PYTHONPATH=str(ROOT))
            for key in ("AIL_UNIFIED_FORCE", "AIL_NO_GENERAL"):
                env.pop(key, None)
            if mode == "forced":
                env["AIL_UNIFIED_FORCE"] = "1"
            done = subprocess.run([sys.executable, "-B", str(ROOT / "ail_chatgpt.py"), "compile", "prog.py", "-o", "prog.out"],
                                  cwd=d, capture_output=True, text=True, timeout=1800, env=env)
            run = None
            if done.returncode == 0:
                run = subprocess.run([str(d / "prog.out")], capture_output=True, text=True, timeout=600)
            return job, done, run

        jobs = [(n, m) for n in NAMES for m in ("default", "forced")]
        with ThreadPoolExecutor(max_workers=2) as pool:
            cls.out = dict(pool.map(lambda j: (j, build(j)), jobs))

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def check(self, name, mode):
        job, done, run = self.out[(name, mode)]
        self.assertEqual(done.returncode, 0, (done.stdout + done.stderr)[-1500:])
        ref = self.ref[name]
        self.assertEqual(ref.returncode, 0, ref.stderr[-500:])
        self.assertEqual(run.stdout, ref.stdout)
        self.assertEqual(run.returncode, ref.returncode)


def _add(name, mode):
    setattr(Native, "test_%s_%s" % (name, mode), lambda self: self.check(name, mode))


for _n in NAMES:
    for _m in ("default", "forced"):
        _add(_n, _m)


if __name__ == "__main__":
    unittest.main()

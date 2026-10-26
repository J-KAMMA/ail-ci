"""fuzz46: a large fixed-point float field in an f-string is not truncated or over-read.

`ail_obj_format`'s float branch formatted `{v:.2f}` into a 65-byte stack buffer but used
snprintf's return value (the full length, e.g. 302 for 1e300) as the text length, so the
padding step read past the buffer.  The first visible case was `f"{1e300:.2f}"`: CPython
prints 302 bytes, AIL printed the prefix and then stack memory.  Both builds must print
CPython's bytes, including empty/negative/inf/nan fields and a .400f spec whose text is
longer than the old 400-byte paths ever handled.
"""
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent
CLI = str(ROOT / "ail_chatgpt.py")

PROGRAM = r'''class C:
    v = 1e300

def f(x):
    return x

d = {"big": 1e300, "small": 1e-300}
xs = [1e300, -1e300, 1e-300]
c = C()
for v in [0.0, -0.0, 1.0, -1.0, 1e300, -1e300, 1e-300, 1e308, -1e308, 5e-324]:
    print(f"[{v:.0f}]")
    print(f"[{v:.2f}]")
    print(f"[{v:.400f}]")
    print(f"[{v:20.2f}]")
    print(f"[{v:<20.2f}]")
    print(f"[{f(v):.2f}]")
    print(f"[{xs[1]:.2f}]")
    print(f"[{c.v:.2f}]")
    print(f"[{d['big']:.2f}]")
print(f"[{float('inf'):.2f}] [{float('-inf'):.2f}] [{float('nan'):.2f}]")
print(f"[{float('inf'):400.2f}]")
'''


def run_py(path):
    r = subprocess.run([sys.executable, "-B", str(path)], capture_output=True, timeout=60)
    return r.returncode, r.stdout


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="ail-fuzz46-")
        self.dir = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def build(self, src, general):
        path = self.dir / "p.py"
        path.write_text(src, encoding="utf-8")
        env = dict(os.environ, AIL_NO_CACHE="1", AIL_QUIET_FALLBACK="1")
        env.pop("AIL_UNIFIED_FORCE", None)
        if general:
            env["AIL_UNIFIED_FORCE"] = "1"
        exe = self.dir / ("exe_g" if general else "exe_d")
        built = subprocess.run([sys.executable, "-B", CLI, "compile", str(path),
                                "--syntax", "python", "-o", str(exe)],
                               cwd=self.dir, capture_output=True, text=True, env=env)
        return built, exe

    def same(self, src):
        path = self.dir / "ref.py"
        path.write_text(src, encoding="utf-8")
        code, out = run_py(path)
        for general in (False, True):
            built, exe = self.build(src, general)
            self.assertEqual(built.returncode, 0, built.stdout + built.stderr)
            ran = subprocess.run([str(exe)], capture_output=True, timeout=60)
            self.assertEqual(ran.stdout, out, "general" if general else "default")
            self.assertEqual(ran.returncode, code)
        return out


class LargeFixedFloat(Base):
    def test_large_and_huge_precision_fixed_fields(self):
        out = self.same(PROGRAM)
        self.assertIn(b"[nan]", out)
        self.assertTrue(max(len(line) for line in out.splitlines()) > 400)


if __name__ == "__main__":
    unittest.main()

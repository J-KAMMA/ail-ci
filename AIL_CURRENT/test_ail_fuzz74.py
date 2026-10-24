"""fuzz74: exact int64/float comparisons on the IR path.

`x = 9223372036854775807; f = 9223372036854775807.0` compared equal because the int was
converted to a double first: the double is 2**63 and the int64 max is one below it.  The IR now
emits an exact integer/double relation; the legacy typed path uses the same relation when a
tagged int/float cell is compared.  Checked against CPython on both builds and the default
build, with boundary values, reversed operands, chained comparisons and NaN.
"""
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent
CLI = str(ROOT / "ail_chatgpt.py")
HAVE_CC = bool(shutil.which("gcc") or shutil.which("cc"))

SOURCE = r'''
def main():
    ints = [-9223372036854775807 - 1, -9223372036854775807, -9007199254740993,
            -9007199254740992, -1, 0, 1, 9007199254740992, 9007199254740993,
            9223372036854775806, 9223372036854775807]
    floats = [float("-inf"), -9223372036854775808.0, -9223372036854777856.0,
              -9007199254740992.0, -2.5, -0.0, 0.0, 2.5, 9007199254740992.0,
              9223372036854774784.0, 9223372036854775808.0, float("inf"), float("nan")]
    for i in ints:
        for f in floats:
            print(i == f, i != f, i < f, i <= f, i > f, i >= f)
            print(f == i, f != i, f < i, f <= i, f > i, f >= i)
    x = 9223372036854775807
    f = 9223372036854775807.0
    print(x < f < 9223372036854775808.0)
    print(x < f < 9223372036854775806.0)
    print(f > x > 9223372036854775806)
    print(x == f != x)
    print(x != f == x)
    print(9007199254740993 == 9007199254740992.0)
    print(9007199254740993 > 9007199254740992.0)
    print(float("nan") != 0, float("nan") == 0, float("nan") < 0, float("nan") > 0)

main()
'''


@unittest.skipUnless(HAVE_CC, "no C compiler")
class IntFloatComparisonTests(unittest.TestCase):
    def _build(self, directory, tag, extra):
        path = Path(directory) / "probe.ail"
        path.write_text(SOURCE)
        exe = Path(directory) / ("probe." + tag)
        stats = Path(directory) / ("probe." + tag + ".stats")
        env = dict(os.environ)
        for name in ("AIL_IR", "AIL_IR_EXC", "AIL_UNIFIED_FORCE"):
            env.pop(name, None)
        env["AIL_IR_STATS"] = str(stats)
        env.update(extra)
        built = subprocess.run([sys.executable, "-B", CLI, "compile", str(path), "--syntax", "python",
                                "-o", str(exe)], capture_output=True, text=True, timeout=600, env=env)
        entries = [json.loads(line) for line in stats.read_text().splitlines()] if stats.exists() else []
        return built, exe, entries

    def test_mixed_comparisons_match_cpython(self):
        expected = subprocess.run([sys.executable, "-B", "-c", SOURCE], capture_output=True, text=True, timeout=120)
        self.assertEqual(expected.returncode, 0, expected.stderr)
        with tempfile.TemporaryDirectory(prefix="ail-fuzz74-") as directory:
            for tag, extra in (("default", {}), ("ir", {"AIL_IR": "verify"}), ("legacy", {"AIL_IR": "0"})):
                with self.subTest(tag=tag):
                    built, exe, entries = self._build(directory, tag, extra)
                    self.assertEqual(built.returncode, 0, built.stdout + built.stderr + SOURCE)
                    if tag != "legacy":
                        on_ir = {entry["fn"] for entry in entries if entry["path"] == "ir"}
                        self.assertIn("main", on_ir, entries)
                    actual = subprocess.run([str(exe)], capture_output=True, text=True, timeout=120)
                    self.assertEqual(actual.returncode, expected.returncode, actual.stderr)
                    self.assertEqual(actual.stdout, expected.stdout, SOURCE)


if __name__ == "__main__":
    unittest.main()

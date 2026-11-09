"""fbfsum1: the opt-in fixed-order float sum (`AIL_PAR_FSUM=fixed`).

`acc += e` on a float accumulator in a parallel body is summed in fixed chunks of 4096 iterations,
each starting from `-0.0` and added left to right, then the chunk sums added to `acc` left to right
in chunk order (`lab/race/fsum/model.py` is that order in Python).  The output must be bit-identical
at AIL_THREADS 1, 2, 4 and 16 and over several runs, and equal to the reference -- which is not
CPython's serial last bits, so this module compares the reference, not CPython.

Without the opt-in the shape stays refused exactly as before.
"""
import importlib.util
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent
PROBES = ROOT.parent / "lab" / "race" / "fsum"
MODEL = PROBES / "model.py"
THREADS = (1, 2, 4, 16)
RUNS = 3
REFUSAL = ("'acc' carries a value between iterations, so it must be an int local of the enclosing "
           "function")


def load_model():
    spec = importlib.util.spec_from_file_location("fsum_model", MODEL)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def build(directory, name, source_path, opt_in=True):
    exe = Path(directory, name)
    env = dict(os.environ, PYTHONHASHSEED=str(0))
    if opt_in:
        env["AIL_PAR_FSUM"] = "fixed"
    else:
        env.pop("AIL_PAR_FSUM", None)
    return subprocess.run([sys.executable, str(ROOT / "ail_chatgpt.py"), "compile",
                           str(source_path), "--syntax", "python", "-o", str(exe)],
                          capture_output=True, text=True, timeout=300, env=env), exe


def run(exe, threads):
    return subprocess.run([str(exe)], capture_output=True, text=True, timeout=120,
                          env=dict(os.environ, AIL_THREADS=str(threads)))


class ParFsumTests(unittest.TestCase):
    def test_probes_match_the_reference_order_at_every_thread_count(self):
        model = load_model()
        with tempfile.TemporaryDirectory() as directory:
            for probe in model.probes():
                with self.subTest(probe.name):
                    built, exe = build(directory, probe.stem, probe)
                    self.assertEqual(built.returncode, 0, built.stdout + built.stderr)
                    expected = repr(model.expected(probe))
                    outputs = set()
                    for threads in THREADS:
                        for _ in range(RUNS):
                            got = run(exe, threads)
                            outputs.add((got.returncode, got.stdout))
                    self.assertEqual(outputs, {(0, expected + "\n")},
                                     "%s at threads %s" % (probe.name, THREADS))

    def test_without_the_opt_in_the_float_reduction_is_still_refused(self):
        model = load_model()
        with tempfile.TemporaryDirectory() as directory:
            for probe in model.probes():
                with self.subTest(probe.name):
                    built, _ = build(directory, probe.stem, probe, opt_in=False)
                    self.assertNotEqual(built.returncode, 0, probe.name)
                    self.assertIn(REFUSAL, built.stdout + built.stderr, probe.name)

    def test_a_value_other_than_fixed_does_not_opt_in(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory, "src.py")
            path.write_text("def main():\n    acc = 0.0\n    for i in par_range(0, 4):\n"
                            "        acc += i\n    print(acc)\nmain()\n")
            exe = Path(directory, "out")
            env = dict(os.environ, AIL_PAR_FSUM="yes")
            built = subprocess.run([sys.executable, str(ROOT / "ail_chatgpt.py"), "compile", str(path),
                                    "--syntax", "python", "-o", str(exe)], capture_output=True,
                                   text=True, timeout=300, env=env)
            self.assertNotEqual(built.returncode, 0)
            self.assertIn(REFUSAL, built.stdout + built.stderr)


if __name__ == "__main__":
    unittest.main()

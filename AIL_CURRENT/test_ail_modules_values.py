"""Modules used as values (modval2): ten probes compared with CPython, and two named refusals.

Each probe is a small program under `tests/modval/`. The merged program gives a module that is used
as a value one generated class and one instance: `m is pkg.util` stays true, `m.name` and
`m.name = value` reach the module's names, and `repr(m)`, `__name__`, `__file__`, `__package__`,
`__path__`, `__spec__`, `__loader__` and `__cached__` have CPython's values. Both the default build
and `AIL_UNIFIED_FORCE=1` must match CPython. A `getattr(m, name)` whose name is not a constant
string, and a store of a name the module does not define, are still refused by name.
"""
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent
CLI = str(ROOT / "ail_chatgpt.py")
PROBES = ROOT / "tests" / "modval"


def build(directory, forced):
    env = dict(os.environ)
    for key in ("AIL_IR", "AIL_NO_GENERAL", "AIL_PATH", "AIL_UNIFIED_FORCE", "PYTHONPATH"):
        env.pop(key, None)
    if forced:
        env["AIL_UNIFIED_FORCE"] = "1"
    output = "out_forced" if forced else "out_default"
    return subprocess.run([sys.executable, "-B", CLI, "compile", "main.py", "-o", output],
                          cwd=directory, capture_output=True, text=True, timeout=600, env=env), output


class ModuleValues(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="ail-modval-")

    def tearDown(self):
        self.tmp.cleanup()

    def copied(self, name):
        target = Path(self.tmp.name) / name
        shutil.copytree(PROBES / name, target)
        return target

    def stdin(self, directory):
        path = directory / "stdin.txt"
        return path.read_bytes() if path.is_file() else b""

    def test_probes_match_cpython_in_both_builds(self):
        for name in sorted(p.name for p in PROBES.iterdir() if p.is_dir()):
            if name.endswith("_refused"):
                continue
            with self.subTest(probe=name):
                directory = self.copied(name)
                expected = subprocess.run([sys.executable, "-B", "main.py"], cwd=directory,
                                          input=self.stdin(directory), capture_output=True, timeout=60)
                self.assertEqual(expected.returncode, 0, expected.stderr.decode())
                for forced in (False, True):
                    built, output = build(directory, forced)
                    self.assertEqual(built.returncode, 0, "forced=%s: %s" % (forced, built.stderr))
                    ran = subprocess.run([str(directory / output)], cwd=directory, input=self.stdin(directory),
                                         capture_output=True, timeout=60)
                    self.assertEqual(ran.stdout, expected.stdout, "forced=%s" % forced)
                    self.assertEqual(ran.returncode, expected.returncode, "forced=%s" % forced)

    def test_refusals_are_named(self):
        needles = {
            "probe09_dynamic_getattr_refused": ("pkg.util", "computed at run time", "write instead"),
            "probe11_new_attribute_refused": ("pkg.a", "NEW", "write instead"),
        }
        for name, wanted in needles.items():
            with self.subTest(probe=name):
                directory = self.copied(name)
                for forced in (False, True):
                    built, output = build(directory, forced)
                    self.assertNotEqual(built.returncode, 0, built.stdout + built.stderr)
                    self.assertFalse((directory / output).exists())
                    for needle in wanted:
                        self.assertIn(needle, built.stderr)
                    self.assertNotIn("Traceback", built.stderr)


if __name__ == "__main__":
    unittest.main()

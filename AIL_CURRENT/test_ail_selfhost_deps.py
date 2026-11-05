"""The self-hosting import graph tool, checked on a fixture with a known graph.

``tools/selfhost_deps.py`` reads Python sources with ``ast`` only and reports, per module,
the eager and lazy import edges, and per graph (eager, full) the strongly connected
components, a layer per component (0 = leaf) and a leaf-first order.  The real graph changes
with every merge, so this module pins the tool on ``lab/selfhost/deps_fixture`` instead:
seven files, a two-module cycle (beta <-> gamma), one lazy edge into a package, and two
standard-library imports that must be listed but not followed.
"""
import json
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TOOL = ROOT / "tools" / "selfhost_deps.py"
FIXTURE = ROOT / "lab" / "selfhost" / "deps_fixture"

EAGER = {
    "entry": ["alpha", "delta"],
    "alpha": ["beta"],
    "beta": ["gamma"],
    "gamma": ["beta"],
    "delta": ["alpha"],
    "pkg": ["pkg.leaf"],
    "pkg.leaf": [],
}
LAZY = {
    "entry": ["pkg", "pkg.leaf"],
    "alpha": [],
    "beta": [],
    "gamma": [],
    "delta": [],
    "pkg": [],
    "pkg.leaf": [],
}


class SelfhostDepsTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        run = subprocess.run(
            [sys.executable, str(TOOL), "--root", str(FIXTURE), "--entry", "entry.py", "--json"],
            cwd=str(ROOT), capture_output=True, text=True)
        if run.returncode != 0:
            raise AssertionError(f"tool failed:\n{run.stdout}\n{run.stderr}")
        cls.data = json.loads(run.stdout)
        cls.modules = {m["name"]: m for m in cls.data["modules"]}

    def test_schema_and_module_set(self):
        self.assertEqual(self.data["schema"], "ail.selfhost_deps/1")
        self.assertEqual(sorted(self.modules), sorted(EAGER))
        self.assertEqual(self.data["module_count"], {"eager": 5, "full": 7})

    def test_exact_edges(self):
        for name, expected in EAGER.items():
            self.assertEqual(self.modules[name]["eager"], expected, f"{name} eager")
        for name, expected in LAZY.items():
            self.assertEqual(self.modules[name]["lazy"], expected, f"{name} lazy")

    def test_stdlib_is_listed_not_followed(self):
        self.assertEqual(self.modules["entry"]["stdlib"], ["os"])
        self.assertNotIn("os", self.modules)

    def test_one_cycle(self):
        for label in ("eager", "full"):
            cycles = self.data["graphs"][label]["cycles"]
            self.assertEqual(cycles, [["beta", "gamma"]], label)

    def test_layers(self):
        layers = {name: module["layer_full"] for name, module in self.modules.items()}
        self.assertEqual(layers, {
            "pkg.leaf": 0,
            "beta": 0,
            "gamma": 0,
            "pkg": 1,
            "alpha": 1,
            "delta": 2,
            "entry": 3,
        })
        for label in ("eager", "full"):
            self.assertEqual(self.data["graphs"][label]["layers"], 4, label)

    def test_leaf_first_order(self):
        self.assertEqual(
            self.data["graphs"]["full"]["leaf_first_order"],
            ["beta", "gamma", "pkg.leaf", "alpha", "pkg", "delta", "entry"])


if __name__ == "__main__":
    unittest.main()

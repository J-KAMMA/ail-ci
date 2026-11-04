"""The generated typeshed signature table and its lookup API.

Running `tools/typeshed_convert.py --check` must reproduce the committed
`python/pkg-v12/stubsigs_table.py` byte for byte, a few signatures must have the return the converter rules
choose, and `third_party/typeshed/VERSION.md` must name a full commit and ship its `LICENSE`.
"""
import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parent
PKG = HERE / "python" / "pkg-v12"
if str(PKG) not in sys.path:
    sys.path.insert(0, str(PKG))

import stubsigs  # noqa: E402


class StubSigsTest(unittest.TestCase):
    def test_converter_reproduces_table(self):
        result = subprocess.run(
            [sys.executable, str(REPO / "tools" / "typeshed_convert.py"), "--check"],
            capture_output=True, text=True, cwd=str(REPO))
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_returns(self):
        self.assertEqual(stubsigs.lookup("math.gcd")[0], "int")
        self.assertEqual(stubsigs.lookup("math.sqrt")[0], "float")
        self.assertEqual(stubsigs.lookup("math.isclose")[0], "bool")
        self.assertEqual(stubsigs.lookup("heapq.heappop")[0], "obj")
        self.assertIsNone(stubsigs.lookup("no.such"))

    def test_agreeing_overloads_have_no_flag(self):
        ret, _params, flags = stubsigs.lookup("bisect.bisect_left")
        self.assertEqual(ret, "int")
        self.assertEqual(flags, "")

    def test_inherited_constructor_params(self):
        self.assertEqual(stubsigs.lookup("builtins.ValueError")[1],
                         (("args", "star", "object"),))

    def test_property_is_not_the_setter(self):
        self.assertEqual(stubsigs.lookup("sqlite3.Connection.autocommit"),
                         ("obj", (), ""))

    def test_constructor_params(self):
        # typeshed puts these constructors in `__new__`; params must not be empty.
        self.assertEqual(
            stubsigs.lookup("datetime.date")[1],
            (("year", "kw", "SupportsIndex"),
             ("month", "kw", "SupportsIndex"),
             ("day", "kw", "SupportsIndex")))
        self.assertIn("iterable", [p[0] for p in stubsigs.lookup("collections.deque")[1]])

    def test_aliased_import_resolves(self):
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "alias.py"
            source.write_text("import math as m\nm.sqrt(4)\n", encoding="utf-8")
            result = subprocess.run(
                [sys.executable, str(REPO / "tools" / "typeshed_reach.py"), str(source), "--list"],
                capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("math.sqrt float", result.stdout)

    def test_vendor_record(self):
        version = (REPO / "third_party" / "typeshed" / "VERSION.md").read_text(encoding="utf-8")
        self.assertRegex(version, r"\b[0-9a-f]{40}\b")
        self.assertTrue((REPO / "third_party" / "typeshed" / "LICENSE").is_file())
        self.assertIn("Apache", (REPO / "third_party" / "typeshed" / "LICENSE").read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()

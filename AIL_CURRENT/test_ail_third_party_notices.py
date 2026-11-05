"""Third-party notices for vendored and derived code.

`THIRD_PARTY_NOTICES.md` must list every file under `AIL_CURRENT/stdlib/` and
`third_party/`, every file marked as derived from CPython must name
`LICENSE-PSF.txt` in its first 15 lines, and every license file the notices
name must exist.  When a C compiler and the wheel backend are available the
wheel is built and checked for the derived stdlib files, `LICENSE-PSF.txt` and
the two root licenses under `.dist-info/licenses/`.
"""
import re
import shutil
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parent
STDLIB = HERE / "stdlib"
THIRD_PARTY = REPO / "third_party"
NOTICES = REPO / "THIRD_PARTY_NOTICES.md"
BACKEND = REPO / "packaging" / "ail_wheel_backend.py"
CPYTHON_MARK = "Derived from CPython 3.12 "
PSF_LICENSE = "LICENSE-PSF.txt"
LICENSE_FILES = ("LICENSE-APACHE", "LICENSE-MIT")
ROW = re.compile(r"^\|\s*`([^`]+)`\s*\|\s*([^|]*?)\s*\|\s*([^|]*?)\s*\|\s*([^|]*?)\s*\|\s*$")
CC = shutil.which("cc") or shutil.which("gcc") or shutil.which("clang")


def text():
    return NOTICES.read_text(encoding="utf-8")


def inventory():
    """{path: (origin, license, notice)} from the Markdown table."""
    rows = {}
    for line in text().splitlines():
        found = ROW.match(line)
        if found:
            path, origin, license_name, notice = (part.strip() for part in found.groups())
            rows[path] = (origin, license_name, notice)
    return rows


def covered_files():
    for base in (STDLIB, THIRD_PARTY):
        for path in base.rglob("*"):
            if path.is_file() and "__pycache__" not in path.parts:
                yield path.relative_to(REPO).as_posix()


def derived_files(rows):
    return sorted(path for path, (origin, _, _) in rows.items()
                  if origin.startswith("CPython"))


class NoticesTest(unittest.TestCase):
    def setUp(self):
        self.rows = inventory()
        self.assertTrue(self.rows, "THIRD_PARTY_NOTICES.md has no inventory table")

    def test_every_file_is_listed(self):
        missing = sorted(set(covered_files()) - set(self.rows))
        self.assertEqual(missing, [], "files without an entry in THIRD_PARTY_NOTICES.md")
        absent = sorted(path for path in self.rows if not (REPO / path).is_file())
        self.assertEqual(absent, [], "inventory lists files that do not exist")

    def test_derived_CPython_files_have_the_notice(self):
        derived = derived_files(self.rows)
        self.assertEqual(len(derived), 11, "the CPython-derived file count changed")
        for path in derived:
            origin, _, notice = self.rows[path]
            self.assertEqual(notice.lower(), "yes", path + " is marked with no notice")
            head = "\n".join((REPO / path).read_text(encoding="utf-8").splitlines()[:15])
            self.assertIn(CPYTHON_MARK, head, path + " has no CPython derivation line")
            self.assertIn(PSF_LICENSE, head, path + " does not name " + PSF_LICENSE)

    def test_every_marked_file_is_in_the_inventory(self):
        marked = []
        for path in covered_files():
            if path.endswith((".py", ".c", ".h")):
                head = "\n".join((REPO / path).read_text(encoding="utf-8", errors="replace").splitlines()[:15])
                if CPYTHON_MARK in head:
                    marked.append(path)
        self.assertEqual(sorted(marked), derived_files(self.rows))

    def test_license_files_exist(self):
        named = set(re.findall(r"License file:\s*`([^`]+)`", text()))
        named.add(PSF_LICENSE)
        for name in sorted(named):
            if name == PSF_LICENSE:
                path = STDLIB / PSF_LICENSE
            else:
                path = REPO / name
            self.assertTrue(path.is_file(), "license file named in the notices is missing: " + name)
        typeshed = THIRD_PARTY / "typeshed" / "LICENSE"
        self.assertIn("Apache", typeshed.read_text(encoding="utf-8"))
        self.assertIn("Python Software Foundation", (STDLIB / PSF_LICENSE).read_text(encoding="utf-8"))

    @unittest.skipUnless(CC and BACKEND.is_file(),
                         "a C compiler and the wheel backend are needed for the wheel check")
    def test_wheel_contains_notices(self):
        sys.path.insert(0, str(REPO / "packaging"))
        import ail_wheel_backend
        with tempfile.TemporaryDirectory(prefix="ail-notices-wheel-") as tmp:
            name = ail_wheel_backend.build_wheel(tmp)
            with zipfile.ZipFile(Path(tmp) / name) as archive:
                names = set(archive.namelist())
        for path in derived_files(self.rows):
            inside = path[len("AIL_CURRENT/"):]
            self.assertIn("ail_lang/sdk/" + inside, names, "derived file missing from the wheel: " + path)
        self.assertTrue(any(Path(member).name == PSF_LICENSE for member in names),
                        "the wheel does not contain " + PSF_LICENSE)
        info = next((member.split("/")[0] for member in names
                     if member.endswith(".dist-info/METADATA")), None)
        self.assertIsNotNone(info, "the wheel has no .dist-info directory")
        for license_name in LICENSE_FILES:
            self.assertIn(info + "/licenses/" + license_name, names,
                          "root license missing from .dist-info/licenses/")


if __name__ == "__main__":
    unittest.main()

"""Third-party notices: every vendored or derived file is listed and every license is present.

`THIRD_PARTY_NOTICES.md` is the inventory. The test checks:

* every file under `AIL_CURRENT/stdlib/` and `third_party/` is matched by an inventory row
  (a row is a path or a glob, e.g. `AIL_CURRENT/stdlib/tomllib/*.py`);
* every file whose row names CPython as its origin says `LICENSE-PSF.txt` in its first 15 lines;
* every license file the rows name exists;
* when a C compiler and the wheel backend are available, `ail_wheel_backend.build_wheel` produces a
  wheel that carries each derived stdlib file, the PSF notice (`stdlib/LICENSE-PSF.txt`) under
  `.dist-info/licenses/`, and the two root licenses under `.dist-info/licenses/`.
"""
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parent
NOTICES = REPO / "THIRD_PARTY_NOTICES.md"
STDLIB = ROOT / "stdlib"
THIRD_PARTY = REPO / "third_party"
BACKEND = REPO / "packaging" / "ail_wheel_backend.py"
LICENSE_FILES = ("LICENSE-APACHE", "LICENSE-MIT")
CC = os.environ.get("PIPE_CC") or shutil.which("cc") or shutil.which("gcc") or shutil.which("clang")


def read_rows():
    """[(path_or_glob, origin, license_name, license_file, notice)] from the inventory table."""
    rows = []
    text = NOTICES.read_text(encoding="utf-8")
    for line in text.splitlines():
        line = line.strip()
        if not line.startswith("|"):
            continue
        cells = [cell.strip() for cell in line.strip("|").split("|")]
        if len(cells) != 5:
            continue
        if cells[0].lower() == "file" or set(cells[0]) <= set("-: "):
            continue
        rows.append(tuple(cell.replace("`", "") for cell in cells))
    return rows


def expand(pattern):
    if any(char in pattern for char in "*?["):
        return {p for p in REPO.glob(pattern) if p.is_file()}
    path = REPO / pattern
    return {path} if path.is_file() else set()


def covered_files():
    found = set()
    for row in read_rows():
        found |= expand(row[0])
    return found


def all_third_party_files():
    files = set()
    for base in (STDLIB, THIRD_PARTY):
        for path in base.rglob("*"):
            if path.is_file() and "__pycache__" not in path.parts:
                files.add(path)
    return files


def derived_from_cpython():
    """[(path, row)] for rows whose origin names CPython."""
    pairs = []
    for row in read_rows():
        if row[1].startswith("CPython"):
            pairs.extend((path, row) for path in sorted(expand(row[0])))
    return pairs


class Inventory(unittest.TestCase):
    def test_notices_file_exists(self):
        self.assertTrue(NOTICES.is_file(), NOTICES)

    def test_every_file_is_listed(self):
        missing = sorted(str(p.relative_to(REPO)) for p in all_third_party_files() - covered_files())
        self.assertEqual(missing, [], "files without an inventory row in THIRD_PARTY_NOTICES.md")

    def test_derived_files_name_the_psf_license(self):
        bad = []
        for path, _row in derived_from_cpython():
            first = "\n".join(path.read_text(encoding="utf-8").splitlines()[:15])
            if "LICENSE-PSF.txt" not in first:
                bad.append(str(path.relative_to(REPO)))
        self.assertEqual(bad, [], "derived files whose first 15 lines do not name LICENSE-PSF.txt")

    def test_named_license_files_exist(self):
        missing = []
        for row in read_rows():
            for name in re.split(r"[,\s]+", row[3]):
                name = name.strip()
                if not name or name == "-":
                    continue
                if not (REPO / name).is_file():
                    missing.append(name)
        self.assertEqual(missing, [], "license files named in THIRD_PARTY_NOTICES.md that do not exist")


class Wheel(unittest.TestCase):
    def setUp(self):
        if not BACKEND.is_file() or not (REPO / "pyproject.toml").is_file():
            self.skipTest("repository root with pyproject.toml is not beside AIL_CURRENT")
        if not CC:
            self.skipTest("no C compiler")
        self.wheel_dir = tempfile.mkdtemp(prefix="ail-notice-wheel-")
        self.addCleanup(shutil.rmtree, self.wheel_dir, True)
        done = subprocess.run(
            [sys.executable, "-c",
             "import sys; sys.path.insert(0, 'packaging'); import ail_wheel_backend as b; print(b.build_wheel(sys.argv[1]))",
             self.wheel_dir], cwd=REPO, capture_output=True, text=True, timeout=300)
        if done.returncode:
            self.fail("wheel build failed: " + done.stderr)
        self.zip = zipfile.ZipFile(Path(self.wheel_dir) / done.stdout.strip())
        self.addCleanup(self.zip.close)
        self.names = set(self.zip.namelist())

    def info(self):
        for name in self.names:
            match = re.match(r"(ailc-[^/]+\.dist-info)/METADATA$", name)
            if match:
                return match.group(1)
        self.fail("no .dist-info/METADATA in the wheel")

    def test_derived_stdlib_files_are_in_the_wheel(self):
        missing = []
        for path, _row in derived_from_cpython():
            name = "ail_lang/sdk/" + path.relative_to(ROOT).as_posix()
            if name not in self.names:
                missing.append(name)
        self.assertEqual(missing, [], "derived stdlib files missing from the wheel")

    def test_psf_license_is_in_the_wheel(self):
        self.assertTrue(any(name.endswith("LICENSE-PSF.txt") for name in self.names),
                        "the wheel lacks the PSF notice; see Follow-ups in THIRD_PARTY_NOTICES.md")

    def test_root_licenses_are_under_dist_info(self):
        info = self.info()
        for name in LICENSE_FILES:
            self.assertIn("%s/licenses/%s" % (info, name), self.names)


if __name__ == "__main__":
    unittest.main(verbosity=2)

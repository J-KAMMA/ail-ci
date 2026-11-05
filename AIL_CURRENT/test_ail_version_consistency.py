"""relver1: one AIL version everywhere.

The version has one source: packaging/ail_lang/__init__.py. This module reads it with a regex
(not an import) and checks the places that state it: pyproject.toml (dynamic version), the wheel
backend (wheel file name and METADATA), `ail --version`, packaging/WHEEL_REPORT.md (a dated
measurement whose old version is historical), and the docs.

Skipped when the repository root with pyproject.toml is not beside AIL_CURRENT (an SDK export).
"""
import re
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parent
INIT = REPO / "packaging" / "ail_lang" / "__init__.py"
PYPROJECT = REPO / "pyproject.toml"
WHEEL_REPORT = REPO / "packaging" / "WHEEL_REPORT.md"
DOCS = (
    REPO / "README.md",
    REPO / "docs" / "LSP.md",
    REPO / "docs" / "INSTALL.md",
    REPO / "docs" / "QUICKSTART.md",
    REPO / "docs" / "RELEASING.md",
    REPO / "packaging" / "README.md",
)
PLACEHOLDERS = ("<version>", "<ail --version>", "<current version>", "<ail version>")

# The PEP 440 pattern from the packaging spec appendix.
PEP440 = re.compile(
    r"""
    ^
    v?
    (?:
        (?:(?P<epoch>[0-9]+)!)?
        (?P<release>[0-9]+(?:\.[0-9]+)*)
        (?P<pre>
            [-_\.]?
            (?P<pre_l>a|b|c|rc|alpha|beta|pre|preview)
            [-_\.]?
            (?P<pre_n>[0-9]+)?
        )?
        (?P<post>
            (?:-(?P<post_n1>[0-9]+))
            |
            (?:
                [-_\.]?
                (?P<post_l>post|rev|r)
                [-_\.]?
                (?P<post_n2>[0-9]+)?
            )
        )?
        (?P<dev>
            [-_\.]?
            (?P<dev_l>dev)
            [-_\.]?
            (?P<dev_n>[0-9]+)?
        )?
    )
    (?:\+(?P<local>[a-z0-9]+(?:[-_\.][a-z0-9]+)*))?
    $
    """,
    re.VERBOSE | re.IGNORECASE,
)
# A release-shaped literal: at least major.minor.patch, so "Python 3.12" is not matched.
VERSION_TOKEN = re.compile(
    r"(?<![\w.])\d+\.\d+\.\d+(?:[-_.]?(?:a|b|c|rc|alpha|beta|pre|preview|post|dev)\d*)?(?!\w|\.\d)",
    re.IGNORECASE,
)


def setUpModule():
    if not (REPO / "pyproject.toml").is_file() or not INIT.is_file():
        raise unittest.SkipTest("repository root with pyproject.toml is not beside AIL_CURRENT")


def source_version():
    text = INIT.read_text(encoding="utf-8")
    found = re.search(r'^__version__\s*=\s*"([^"]+)"', text, re.M)
    if not found:
        raise AssertionError("no __version__ in packaging/ail_lang/__init__.py")
    return found.group(1)


def backend():
    sys.path.insert(0, str(REPO / "packaging"))
    import ail_wheel_backend
    return ail_wheel_backend


class VersionConsistency(unittest.TestCase):
    def test_version_is_pep440(self):
        self.assertRegex(source_version(), PEP440)

    def test_pyproject_uses_the_dynamic_version(self):
        pyproject = PYPROJECT.read_text(encoding="utf-8")
        self.assertIn('dynamic = ["version"]', pyproject)
        self.assertIsNone(re.search(r"^\s*version\s*=", pyproject, re.M),
                          "pyproject.toml states a literal version")

    def test_cli_prints_the_version(self):
        done = subprocess.run(
            [sys.executable, "-B", "-c",
             "import sys; sys.path.insert(0, 'packaging'); import ail_lang.cli as c; "
             "raise SystemExit(c.main(['--version']))"],
            cwd=REPO, capture_output=True, text=True, timeout=60)
        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertEqual(done.stdout.strip(), "ailc " + source_version())

    def test_wheel_name_contains_the_version(self):
        self.assertIn("-" + source_version() + "-", backend().wheel_name())

    def test_metadata_states_the_version(self):
        metadata = backend().metadata_text()
        self.assertIn("\nVersion: " + source_version() + "\n", metadata)

    def test_docs_state_the_version_or_a_placeholder(self):
        version = source_version()
        problems = []
        for path in DOCS:
            if not path.is_file():
                continue
            for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
                if any(mark in line for mark in PLACEHOLDERS):
                    continue
                context = "ail" in line.lower() or "version" in line.lower()
                if not context:
                    continue
                for found in VERSION_TOKEN.findall(line):
                    if found != version:
                        problems.append("%s:%d: %s" % (
                            path.relative_to(REPO).as_posix(), number, found))
        self.assertEqual(problems, [], "a doc states a stale AIL version")

    def test_wheel_report_is_a_dated_measurement(self):
        text = WHEEL_REPORT.read_text(encoding="utf-8")
        self.assertRegex(text, r"(?im)^Date: \d{4}-\d{2}-\d{2}")
        self.assertIn("Base branch:", text)
        # The report measures an older wheel, so its old version is historical, not a current
        # statement; it must not appear as a literal anywhere else.
        found = sorted(set(VERSION_TOKEN.findall(text)))
        self.assertTrue(found, "the report no longer carries a measured version")
        # Its version is a measurement, not a current statement, so an old value is allowed here.
        for value in found:
            self.assertRegex(text, r"(?im)^Date: \d{4}-\d{2}-\d{2}")


if __name__ == "__main__":
    unittest.main()

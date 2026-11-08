"""Supply-chain SBOM: tools/sbom.py names every shared library and bundled source of a build.

Three programs are compiled with `--debug-dir`, an SBOM is written for each, and the BOM is
cross-checked against `readelf -d`, the recorded link line, the generated C and the nearest
Cargo.lock.  The shared-library set must be exactly the DT_NEEDED set, the bundled C set must be
exactly what the generated C carries, and no crate may be missing or extra.

Skips without a C compiler or readelf.
"""
import importlib.util
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parent
CLI = str(ROOT / "ail_chatgpt.py")
SBOM = REPO / "tools" / "sbom.py"
CC = os.environ.get("PIPE_CC") or shutil.which("cc") or shutil.which("gcc")
READELF = shutil.which("readelf")

ZLIB = """
import zlib

def main():
    data = b"hello hello hello hello world " * 30
    packed = zlib.compress(data)
    print(len(packed), zlib.crc32(data), zlib.adler32(data))
    print(zlib.decompress(packed) == data)

main()
"""

PROGRAMS = (
    ("compare_echo_pack", REPO / "lab" / "compare" / "src" / "echo_pack" / "typed.py"),
    ("ffi_zlib", REPO / "examples" / "ffi" / "zlib_check.py"),
    ("stdlib_zlib", None),
)


def load_sbom():
    spec = importlib.util.spec_from_file_location("ail_sbom_tool", SBOM)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@unittest.skipUnless(CC, "installed C compiler required")
@unittest.skipUnless(READELF, "readelf required")
class SupplyChainSbomTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory(prefix="ail-sbom-test-")
        cls.dir = Path(cls.temp.name)
        cls.builds = {}
        env = dict(os.environ, AIL_NO_CACHE="1")
        env.pop("PYTHONPATH", None)
        for name, source in PROGRAMS:
            if source is None:
                source = cls.dir / "stdlib_zlib.py"
                source.write_text(ZLIB, encoding="utf8")
            work = cls.dir / name
            work.mkdir()
            exe = work / "prog"
            debug = work / "debug"
            built = subprocess.run(
                [sys.executable, "-B", CLI, "compile", str(source), "-o", str(exe),
                 "--debug-dir", str(debug)],
                cwd=str(work), env=env, capture_output=True, text=True, timeout=900)
            if built.returncode != 0:
                cls.temp.cleanup()
                raise AssertionError("the AIL build of %s failed:\n%s" % (name, built.stderr[-2000:]))
            bom_path = work / "bom.cdx.json"
            checked = subprocess.run(
                [sys.executable, "-B", str(SBOM), str(exe), "--source", str(source),
                 "--debug-dir", str(debug), "-o", str(bom_path), "--check"],
                cwd=str(REPO), capture_output=True, text=True, timeout=300)
            if checked.returncode != 0:
                cls.temp.cleanup()
                raise AssertionError("sbom/--check failed for %s:\n%s\n%s"
                                     % (name, checked.stdout[-2000:], checked.stderr[-2000:]))
            cls.builds[name] = {
                "source": source, "exe": exe, "debug": debug,
                "bom": json.loads(bom_path.read_text(encoding="utf8")),
                "check": json.loads(checked.stdout or "{}"),
            }

    @classmethod
    def tearDownClass(cls):
        cls.temp.cleanup()

    def test_cyclonedx_shape_is_valid(self):
        tool = load_sbom()
        for name, build in self.builds.items():
            with self.subTest(program=name):
                self.assertEqual(tool.validate_bom(build["bom"]), [])
                self.assertEqual(build["bom"]["specVersion"], "1.5")

    def test_cross_check_is_empty(self):
        for name, build in self.builds.items():
            with self.subTest(program=name):
                self.assertEqual(build["check"], {
                    "missing": [], "extra": [], "link_missing": [],
                    "link_static_missing": [], "bundled_missing": [],
                    "bundled_extra": [], "crate_missing": [], "crate_extra": [],
                })

    def test_shared_libraries_are_the_dt_needed_set(self):
        tool = load_sbom()
        for name, build in self.builds.items():
            expected = set(tool.readelf_needed(build["exe"]))
            actual = tool.bom_shared(build["bom"])
            with self.subTest(program=name):
                self.assertEqual(actual, expected)
                self.assertIn("libc.so.6", actual)

    def test_bundled_c_sources_follow_the_generated_c(self):
        tool = load_sbom()
        compare = tool.bom_bundled(self.builds["compare_echo_pack"]["bom"])
        ffi_zlib = tool.bom_bundled(self.builds["ffi_zlib"]["bom"])
        stdlib_zlib = tool.bom_bundled(self.builds["stdlib_zlib"]["bom"])
        self.assertEqual(compare, set())
        self.assertEqual(ffi_zlib, set())
        self.assertIn("AIL_CURRENT/stdlib/zlib_glue.c", stdlib_zlib)
        self.assertIn("AIL_CURRENT/stdlib/zlib_glue.h", stdlib_zlib)
        component = next(item for item in self.builds["stdlib_zlib"]["bom"]["components"]
                         if item["name"] == "AIL_CURRENT/stdlib/zlib_glue.c")
        digest = tool.file_digest(REPO / "AIL_CURRENT" / "stdlib" / "zlib_glue.c")
        self.assertEqual(component["hashes"][0]["content"], digest)

    def test_tools_and_commit_are_recorded(self):
        for name, build in self.builds.items():
            with self.subTest(program=name):
                metadata = build["bom"]["metadata"]
                names = {tool.get("name"): tool for tool in metadata["tools"]}
                self.assertIn("ailc", names)
                self.assertTrue(names["ailc"]["version"])
                compiler = [tool for tool in metadata["tools"] if tool["name"] != "ailc"]
                self.assertEqual(len(compiler), 1)
                self.assertTrue(compiler[0]["version"])
                props = {item["name"]: item["value"] for item in metadata["properties"]}
                self.assertTrue(props.get("ail:git:commit"))
                self.assertIn("ail:link:line", props)

    def test_dpkg_version_and_licence_where_known(self):
        if not shutil.which("dpkg-query"):
            self.skipTest("dpkg-query is not installed")
        known = []
        for build in self.builds.values():
            for component in build["bom"]["components"]:
                if component.get("type") == "library" and component.get("purl", "").startswith("pkg:deb/"):
                    if component.get("version"):
                        known.append(component)
        self.assertTrue(known, "no Debian package was identified")
        for component in known:
            self.assertRegex(component["version"], r"\d")
            self.assertTrue(component.get("licenses"), component["name"])


class BundledDetectionTests(unittest.TestCase):
    def test_runtime_headers_and_glue_are_detected_in_generated_c(self):
        tool = load_sbom()
        with tempfile.TemporaryDirectory() as name:
            debug = Path(name)
            (debug / "entry.c").write_text(
                "#ifndef AILFILE_CORE_H\n#define AILFILE_CORE_H\n"
                "static int64_t ailf_open(void) { return 0; }\n#endif\n"
                "int64_t ffi_1_zglue_deflate(void);\n", encoding="utf8")
            found = {item["relative"] for item in tool.bundled_sources(REPO, debug)}
            self.assertIn("AIL_CURRENT/python/pkg-v12/ailfile_core.h", found)
            self.assertIn("AIL_CURRENT/stdlib/zlib_glue.c", found)


class CrateLockTests(unittest.TestCase):
    def test_every_crate_in_the_nearest_lock_is_named(self):
        tool = load_sbom()
        crates, lock = tool.cargo_crates(REPO / "examples" / "crate" / "bits" / "main.py")
        self.assertEqual(Path(lock), REPO / "examples" / "crate" / "bits" / "Cargo.lock")
        rows = {(item["name"], item["version"]) for item in crates}
        self.assertEqual(rows, {("bits", "0.1.0"), ("tinydep", "0.1.0")})
        components = [tool.crate_component(item) for item in crates]
        for component in components:
            self.assertEqual(component["type"], "library")
            self.assertTrue(component["purl"].startswith("pkg:cargo/"))
            self.assertIn("Cargo.lock", str(component["properties"]))

    def test_a_source_outside_a_crate_has_no_crates(self):
        tool = load_sbom()
        crates, lock = tool.cargo_crates(REPO / "examples" / "ffi" / "zlib_check.py")
        self.assertEqual(crates, [])
        self.assertIsNone(lock)


if __name__ == "__main__":
    unittest.main()

"""ffpkg1: `ail_pkg.py add/remove/sync/list` against a local fake index.

The index and its three small pure-Python wheels (alpha, beta, gamma) are built in a
temporary directory and served by `http.server` on 127.0.0.1; the test never touches
the network.  Extra fixture wheels exercise the refusals: an sdist, a platform wheel,
a pure-tagged wheel that carries a `.so`, a path escape, an absolute path, a wrong
SHA-256, a dependency closure and a duplicate top-level module.
"""
import functools
import hashlib
import http.server
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import threading
import unittest
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent
AIL_PKG = ROOT / "ail_pkg.py"
sys.path.insert(0, str(ROOT))
import ail_pkg  # noqa: E402


def sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def version_key(version):
    return ail_pkg._version_key(version)


def wheel_name(name, version, tag="py3-none-any"):
    return "%s-%s-%s.whl" % (name.replace("-", "_"), version, tag)


def build_wheel(directory, name, version, files, requires=(), raw_entries=(), tag="py3-none-any",
                filename=None):
    """Write a tiny wheel; `files` maps package-relative paths to bytes/text."""
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    dist = re.sub(r"[-_.]+", "_", name) + "-" + version + ".dist-info"
    metadata = ["Metadata-Version: 2.1", "Name: " + name, "Version: " + version,
                "Requires-Python: >=3.8", "License: MIT"]
    metadata += ["Requires-Dist: " + requirement for requirement in requires]
    path = directory / (filename or wheel_name(name, version, tag))
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as archive:
        for relative, data in files.items():
            archive.writestr(relative, data.encode("utf-8") if isinstance(data, str) else data)
        for relative, data in raw_entries:
            archive.writestr(relative, data.encode("utf-8") if isinstance(data, str) else data)
        archive.writestr(dist + "/METADATA", "\n".join(metadata) + "\n")
        archive.writestr(dist + "/WHEEL", "Wheel-Version: 1.0\nGenerator: test\nRoot-Is-Purelib: true\n"
                         "Tag: " + tag + "\n")
        archive.writestr(dist + "/RECORD", "")
        archive.writestr(dist + "/LICENSE", "MIT\n")
    return path


class QuietHandler(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *args):
        pass


class Base(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory(prefix="ail-pkg-test-")
        cls.index = Path(cls.tmp.name) / "index"
        (cls.index / "files").mkdir(parents=True)
        cls.server = http.server.ThreadingHTTPServer(
            ("127.0.0.1", 0), functools.partial(QuietHandler, directory=str(cls.index)))
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()
        cls.base = "http://127.0.0.1:%d" % cls.server.server_address[1]
        cls.staging = Path(cls.tmp.name) / "wheels"
        cls.releases = {}
        cls.publish_fixtures()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join(timeout=10)
        cls.tmp.cleanup()

    @classmethod
    def record_for(cls, wheel, *, yanked=False, digest=None, packagetype="bdist_wheel",
                   requires_python=">=3.8"):
        copied = cls.index / "files" / wheel.name
        shutil.copyfile(wheel, copied)
        return {
            "filename": wheel.name,
            "url": cls.base + "/files/" + wheel.name,
            "digests": {"sha256": digest or sha256(wheel)},
            "size": wheel.stat().st_size,
            "packagetype": packagetype,
            "yanked": yanked,
            "requires_python": requires_python,
        }

    @classmethod
    def publish(cls, name, version, wheel, **kwargs):
        cls.releases.setdefault(name, {})[version] = cls.record_for(wheel, **kwargs)

    @classmethod
    def publish_fixtures(cls):
        staging = cls.staging
        alpha = build_wheel(staging, "alpha", "1.0.0", {
            "alpha/__init__.py": "VALUE = 'alpha'\n\n\ndef value():\n    return VALUE\n",
            "alpha/data.txt": "not a Python source\n",
        })
        beta = build_wheel(staging, "beta", "2.0.0", {
            "beta/__init__.py": "from alpha import value\n\n\ndef value2():\n    return value() + '-beta'\n",
        }, requires=("alpha>=1.0",))
        gamma = build_wheel(staging, "gamma", "3.0.0", {
            "gamma/__init__.py": "def value():\n    return 'gamma'\n",
        })
        gamma_yanked = build_wheel(staging, "gamma", "3.2.0", {
            "gamma/__init__.py": "def value():\n    return 'yanked'\n",
        })
        cls.publish("alpha", "1.0.0", alpha)
        cls.publish("beta", "2.0.0", beta)
        cls.publish("gamma", "3.0.0", gamma)
        cls.publish("gamma", "3.2.0", gamma_yanked, yanked=True)

        hashbad = build_wheel(staging, "hashbad", "1.0.0", {"hashbad/__init__.py": "X = 1\n"})
        cls.publish("hashbad", "1.0.0", hashbad, digest="0" * 64)

        sdist = staging / "sdistpkg-1.0.0.tar.gz"
        sdist.write_bytes(b"not a wheel")
        cls.publish("sdistpkg", "1.0.0", sdist, packagetype="sdist")

        platform = build_wheel(staging, "plat", "1.0.0", {"plat/__init__.py": "X = 1\n"},
                               tag="cp312-cp312-linux_x86_64",
                               filename=wheel_name("plat", "1.0.0", "cp312-cp312-linux_x86_64"))
        cls.publish("plat", "1.0.0", platform)

        cext = build_wheel(staging, "cext", "1.0.0", {
            "cext/__init__.py": "X = 1\n",
            "cext/_speed.so": b"\x7fELF",
        })
        cls.publish("cext", "1.0.0", cext)

        escape = build_wheel(staging, "escape", "1.0.0", {"escape/__init__.py": "X = 1\n"},
                             raw_entries=(("../escape.py", "ESCAPED = True\n"),))
        cls.publish("escape", "1.0.0", escape)

        absolute = build_wheel(staging, "absolute", "1.0.0", {"absolute/__init__.py": "X = 1\n"},
                               raw_entries=(("/absolute_escape.py", "ESCAPED = True\n"),))
        cls.publish("absolute", "1.0.0", absolute)

        dup = build_wheel(staging, "dup", "1.0.0", {"alpha/__init__.py": "DUP = True\n"})
        cls.publish("dup", "1.0.0", dup)

        pre_stable = build_wheel(staging, "pre", "1.0.0", {"pre/__init__.py": "VALUE = 'stable'\n"})
        pre_rc = build_wheel(staging, "pre", "1.0.0rc1", {"pre/__init__.py": "VALUE = 'rc'\n"})
        cls.publish("pre", "1.0.0", pre_stable)
        cls.publish("pre", "1.0.0rc1", pre_rc)

        needsalpha2 = build_wheel(staging, "needsalpha2", "1.0.0", {
            "needsalpha2/__init__.py": "VALUE = 'needsalpha2'\n",
        }, requires=("alpha>=2.0",))
        cls.publish("needsalpha2", "1.0.0", needsalpha2)

        py2only = build_wheel(staging, "py2only", "1.0.0", {"py2only/__init__.py": "VALUE = 'py2'\n"},
                              tag="py2-none-any", filename=wheel_name("py2only", "1.0.0", "py2-none-any"))
        cls.publish("py2only", "1.0.0", py2only)

        pytag_py2 = build_wheel(staging, "pytag", "1.0.0", {"pytag/__init__.py": "VALUE = 'py2'\n"},
                                tag="py2-none-any", filename=wheel_name("pytag", "1.0.0", "py2-none-any"))
        pytag_py3 = build_wheel(staging, "pytag", "1.0.0", {"pytag/__init__.py": "VALUE = 'py3'\n"},
                                tag="py3-none-any", filename=wheel_name("pytag", "1.0.0", "py3-none-any"))
        pytag_records = [cls.record_for(pytag_py2), cls.record_for(pytag_py3)]
        cls.write_json("pytag/1.0.0/json", {
            "info": {"name": "pytag", "version": "1.0.0"},
            "urls": pytag_records,
        })
        cls.write_json("pytag/json", {
            "info": {"name": "pytag", "version": "1.0.0"},
            "urls": pytag_records,
            "releases": {"1.0.0": pytag_records},
        })

        for name, versions in cls.releases.items():
            for version, record in versions.items():
                cls.write_json(name + "/" + version + "/json", {
                    "info": {"name": name, "version": version},
                    "urls": [record],
                })
            stable = [version for version, record in versions.items() if not record["yanked"]]
            latest = max(stable, key=version_key) if stable else max(versions, key=version_key)
            cls.write_json(name + "/json", {
                "info": {"name": name, "version": latest},
                "urls": [versions[latest]],
                "releases": {version: [record] for version, record in versions.items()},
            })

    @classmethod
    def write_json(cls, relative, data):
        path = cls.index / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(data), encoding="utf-8")

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="ail-pkg-project-")
        self.addCleanup(self.tmp.cleanup)
        self.project = Path(self.tmp.name)

    def run_pkg(self, *args):
        environment = dict(os.environ, AIL_PYPI_URL=self.base, PYTHONUTF8="1")
        environment.pop("AIL_PATH", None)
        return subprocess.run([sys.executable, "-B", str(AIL_PKG), *args], cwd=self.project,
                              env=environment, capture_output=True, text=True, encoding="utf-8", timeout=120)

    def ok(self, *args):
        done = self.run_pkg(*args)
        self.assertEqual(done.returncode, 0, done.stdout + done.stderr)
        return done

    def refused(self, *args):
        done = self.run_pkg(*args)
        self.assertEqual(done.returncode, 1, done.stdout + done.stderr)
        self.assertTrue(done.stderr.strip(), "a refusal must name the problem on stderr")
        return done

    def lock(self):
        return ail_pkg.load_lock(self.project)

    def vendor(self, name, version):
        return self.project / ail_pkg.VENDOR / name / version


class AddRemoveList(Base):
    def test_add_pin_vendors_only_sources_and_metadata(self):
        done = self.ok("add", "alpha==1.0.0")
        self.assertIn("added alpha 1.0.0", done.stdout)
        self.assertIn("MIT", done.stdout)
        entry = self.lock()["package"]["alpha"]
        self.assertEqual((entry["version"], entry["wheel"], entry["license"]), ("1.0.0", "alpha-1.0.0-py3-none-any.whl", "MIT"))
        self.assertEqual(entry["sha256"], sha256(self.project / ail_pkg.WHEEL_CACHE / entry["wheel"]))
        self.assertEqual(entry["tree_sha256"], ail_pkg.tree_digest(self.vendor("alpha", "1.0.0")))
        self.assertTrue((self.vendor("alpha", "1.0.0") / "alpha" / "__init__.py").is_file())
        self.assertTrue((self.vendor("alpha", "1.0.0") / "alpha-1.0.0.dist-info" / "METADATA").is_file())
        self.assertFalse((self.vendor("alpha", "1.0.0") / "alpha" / "data.txt").exists())
        self.assertEqual((self.vendor("alpha", "1.0.0") / "alpha" / "__init__.py").read_text(encoding="utf-8"),
                         "VALUE = 'alpha'\n\n\ndef value():\n    return VALUE\n")
        listed = self.ok("list")
        self.assertIn("alpha 1.0.0 MIT", listed.stdout)

    def test_bare_name_skips_yanked_and_picks_highest_stable(self):
        self.ok("add", "gamma")
        entry = self.lock()["package"]["gamma"]
        self.assertEqual(entry["version"], "3.0.0")
        self.assertIn("return 'gamma'", (self.vendor("gamma", "3.0.0") / "gamma" / "__init__.py").read_text(encoding="utf-8"))

    def test_bare_name_skips_prereleases(self):
        self.ok("add", "pre")
        entry = self.lock()["package"]["pre"]
        self.assertEqual(entry["version"], "1.0.0")
        self.assertIn("VALUE = 'stable'", (self.vendor("pre", "1.0.0") / "pre" / "__init__.py").read_text(encoding="utf-8"))

    def test_version_picks_the_python3_wheel(self):
        self.ok("add", "pytag==1.0.0")
        entry = self.lock()["package"]["pytag"]
        self.assertEqual(entry["wheel"], "pytag-1.0.0-py3-none-any.whl")
        self.assertIn("VALUE = 'py3'", (self.vendor("pytag", "1.0.0") / "pytag" / "__init__.py").read_text(encoding="utf-8"))

    def test_remove_deletes_tree_lock_and_cached_wheel(self):
        self.ok("add", "gamma==3.0.0")
        wheel = self.project / ail_pkg.WHEEL_CACHE / "gamma-3.0.0-py3-none-any.whl"
        self.assertTrue(wheel.is_file())
        self.ok("remove", "gamma")
        self.assertNotIn("gamma", self.lock()["package"])
        self.assertFalse((self.project / ail_pkg.VENDOR / "gamma").exists())
        self.assertFalse(wheel.exists())
        self.refused("remove", "gamma")

    def test_dependency_closure(self):
        missing = self.refused("add", "beta==2.0.0")
        self.assertIn("requires alpha", missing.stderr)
        self.assertNotIn("beta", ail_pkg.load_lock(self.project, missing_ok=True)["package"])
        self.ok("add", "alpha==1.0.0")
        self.ok("add", "beta==2.0.0")
        self.assertEqual(self.lock()["package"]["beta"]["requires"], ["alpha"])
        self.assertEqual(self.lock()["package"]["beta"]["require_specs"], ["alpha>=1.0"])
        blocked = self.refused("remove", "alpha")
        self.assertIn("required by beta", blocked.stderr)
        self.ok("remove", "beta")
        self.ok("remove", "alpha")

    def test_dependency_specifier_enforced(self):
        self.ok("add", "alpha==1.0.0")
        done = self.refused("add", "needsalpha2==1.0.0")
        self.assertIn("requires alpha>=2.0", done.stderr)
        self.assertNotIn("needsalpha2", self.lock()["package"])

    def test_duplicate_top_level_name_refused(self):
        self.ok("add", "alpha==1.0.0")
        done = self.refused("add", "dup==1.0.0")
        self.assertIn("already provided by alpha", done.stderr)
        self.assertNotIn("dup", self.lock()["package"])

    def test_add_after_locked_tree_removed_refuses_by_name(self):
        self.ok("add", "alpha==1.0.0")
        shutil.rmtree(self.project / ail_pkg.VENDOR / "alpha")
        done = self.refused("add", "gamma==3.0.0")
        self.assertIn("run `ail sync` first", done.stderr)
        self.assertNotIn("gamma", self.lock()["package"])


class Refusals(Base):
    def assert_not_locked(self, name):
        self.assertNotIn(name, ail_pkg.load_lock(self.project, missing_ok=True)["package"])
        self.assertFalse((self.project / ail_pkg.VENDOR / name).exists())

    def test_wrong_sha256_refused(self):
        done = self.refused("add", "hashbad==1.0.0")
        self.assertIn("sha256 mismatch", done.stderr)
        self.assert_not_locked("hashbad")

    def test_sdist_refused_by_name(self):
        done = self.refused("add", "sdistpkg==1.0.0")
        self.assertIn("sdists run code at build time", done.stderr)
        self.assert_not_locked("sdistpkg")

    def test_platform_wheel_refused_by_name(self):
        done = self.refused("add", "plat==1.0.0")
        self.assertIn("C extension", done.stderr)
        self.assert_not_locked("plat")

    def test_pure_tagged_extension_refused_by_name(self):
        done = self.refused("add", "cext==1.0.0")
        self.assertIn("requires a C extension", done.stderr)
        self.assert_not_locked("cext")

    def test_python2_only_wheel_refused_by_name(self):
        done = self.refused("add", "py2only==1.0.0")
        self.assertIn("Python 2", done.stderr)
        self.assert_not_locked("py2only")

    def test_parent_escape_refused(self):
        done = self.refused("add", "escape==1.0.0")
        self.assertIn("escapes its directory", done.stderr)
        self.assert_not_locked("escape")
        self.assertFalse((self.project / "escape.py").exists())
        self.assertFalse((self.project.parent / "escape.py").exists())

    def test_absolute_path_refused(self):
        done = self.refused("add", "absolute==1.0.0")
        self.assertIn("absolute path", done.stderr)
        self.assert_not_locked("absolute")
        self.assertFalse(Path("/absolute_escape.py").exists())


class Sync(Base):
    def snapshot(self):
        result = {}
        vendor = self.project / ail_pkg.VENDOR
        for path in sorted(vendor.rglob("*")):
            if path.is_file():
                result[path.relative_to(vendor).as_posix()] = path.read_bytes()
        return result

    def test_sync_reproduces_byte_for_byte_and_removes_extras(self):
        self.ok("add", "alpha==1.0.0")
        self.ok("add", "beta==2.0.0")
        before = self.snapshot()
        self.assertTrue(before)
        (self.project / ail_pkg.VENDOR / "stray" / "1.0.0").mkdir(parents=True)
        (self.project / ail_pkg.VENDOR / "stray" / "1.0.0" / "stray.py").write_text("X = 1\n", encoding="utf-8")
        (self.vendor("alpha", "1.0.0") / "alpha" / "__init__.py").write_text("BROKEN = 1\n", encoding="utf-8")
        shutil.rmtree(self.project / ail_pkg.VENDOR)
        done = self.ok("sync")
        self.assertIn("synced 2 packages", done.stdout)
        self.assertEqual(self.snapshot(), before)
        self.assertFalse((self.project / ail_pkg.VENDOR / "stray").exists())

    def test_sync_refetches_when_cache_and_tree_are_missing(self):
        self.ok("add", "alpha==1.0.0")
        before = self.snapshot()
        shutil.rmtree(self.project / ail_pkg.WHEEL_CACHE)
        shutil.rmtree(self.project / ail_pkg.VENDOR)
        done = self.ok("sync")
        self.assertIn("synced 1 package", done.stdout)
        self.assertEqual(self.snapshot(), before)
        self.assertTrue((self.project / ail_pkg.WHEEL_CACHE / "alpha-1.0.0-py3-none-any.whl").is_file())

    def test_sync_refetches_one_missing_cached_wheel(self):
        self.ok("add", "alpha==1.0.0")
        self.ok("add", "gamma==3.0.0")
        before = self.snapshot()
        (self.project / ail_pkg.WHEEL_CACHE / "alpha-1.0.0-py3-none-any.whl").unlink()
        shutil.rmtree(self.vendor("alpha", "1.0.0"))
        done = self.ok("sync")
        self.assertIn("synced 2 packages", done.stdout)
        self.assertEqual(self.snapshot(), before)

    def test_tampered_cached_wheel_fails_loudly(self):
        self.ok("add", "alpha==1.0.0")
        wheel = self.project / ail_pkg.WHEEL_CACHE / "alpha-1.0.0-py3-none-any.whl"
        wheel.write_bytes(wheel.read_bytes() + b"tampered")
        before = self.snapshot()
        done = self.refused("sync")
        self.assertIn("tampered", done.stderr)
        self.assertEqual(self.snapshot(), before)

    def test_sync_without_lock_refuses(self):
        done = self.refused("sync")
        self.assertIn("no ail.lock", done.stderr)


if __name__ == "__main__":
    unittest.main()

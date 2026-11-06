"""PEP 517 build backend for ailc (G14). Standard library only, so it works offline and without `wheel`.

The wheel holds three things:

* ail_lang/{__init__,__main__,cli,project,lsp}.py   the `ail` command (packaging/ail_lang/)
* ail_lang/sdk/...                      what AIL_CURRENT/ail_sdk.py export_sdk() writes: the
                                        MANIFEST.json "sdk_files" list with its SHA-256 pins, plus
                                        the SDK's own MANIFEST.json and SDK_README_JA.md, minus the
                                        files a user never needs at run time (the compiler's own test
                                        programs and the language_examples reference/host/baseline C
                                        files; see unused_sdk_file). Whatever the SDK export refuses or
                                        leaves out (experiments/, docs/design, tasks-novel, evidence/ ...)
                                        cannot get into the wheel.
* ailc-<version>.dist-info/             METADATA, WHEEL, entry_points.txt, RECORD,
                                        licenses/LICENSE-APACHE, licenses/LICENSE-MIT and
                                        licenses/LICENSE-PSF.txt (for the CPython-derived stdlib)

Only a wheel is built (`pip install .`, `pip wheel .`, `python -m build --wheel`). An sdist would have to
carry the whole private repository, so build_sdist refuses.
"""
import base64
import csv
import hashlib
import importlib.util
import io
import json
import os
import re
import sys
import tempfile
import zipfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
PACKAGE = Path(__file__).resolve().parent / "ail_lang"
SOURCE = REPO / "AIL_CURRENT"
NAME = "ailc"
DIST = "ailc"
IMPORT = "ail_lang"                                     # the import package and the `ail` command module
SUMMARY = "AIL: a Python-like language that compiles to standalone C executables"
REQUIRES_PYTHON = ">=3.10"
PACKAGE_FILES = ("__init__.py", "__main__.py", "cli.py", "project.py", "lsp.py")
LICENSE_EXPRESSION = "MIT OR Apache-2.0"
LICENSE_FILES = ("LICENSE-APACHE", "LICENSE-MIT")      # repository root; pyproject.toml license-files lists the same
PSF_NOTICE = SOURCE / "stdlib" / "LICENSE-PSF.txt"     # the PSF text beside the CPython-derived stdlib modules
ENTRY_POINTS = "[console_scripts]\nail = ail_lang.cli:main\n"


def version():
    """The one version: ail_lang/__init__.py (read, not imported)."""
    text = (PACKAGE / "__init__.py").read_text(encoding="utf-8")
    found = re.search(r'^__version__\s*=\s*"([^"]+)"', text, re.M)
    if not found:
        raise RuntimeError("no __version__ in packaging/ail_lang/__init__.py")
    return found.group(1)


def unused_sdk_file(name):
    """A selected SDK file that no run-time reader uses (proved by tools/wheel_same_c.py and wheel_check.py).

    The compiler's own test programs and the C reference/host/baseline files under language_examples are
    read only by tests and documentation. They stay in the SDK export and in the source tree; the wheel
    leaves them out and the SDK MANIFEST.json in the wheel no longer pins them.
    """
    if name in ("python/pkg-v12/test_all.py", "python/pkg-v12/test_pipeline.py"):
        return True
    if name.startswith("language_examples/") and name.endswith(".c"):
        base = name.rsplit("/", 1)[1]
        return base.endswith(".baseline.c") or base.endswith("_host.c") or "_reference" in base
    return False


def _drop_unused_sdk_files(files):
    """Remove unused_sdk_file entries and their pins from the exported SDK's MANIFEST.json."""
    removed = {name for name in files if unused_sdk_file(name)}
    if not removed:
        return files
    kept = {name: data for name, data in files.items() if name not in removed}
    manifest = json.loads(kept["MANIFEST.json"])
    manifest["sdk_files"] = [name for name in manifest.get("sdk_files", []) if name not in removed]
    for name in removed:
        manifest.get("sha256", {}).pop(name, None)
    manifest["filecount"] = manifest.get("filecount", 0) - len(removed)
    manifest["bytes"] = manifest.get("bytes", 0) - sum(len(files[name]) for name in removed)
    kept["MANIFEST.json"] = (json.dumps(manifest, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    return kept


def sdk_files(work):
    """Run the SDK export into work/sdk and return {relative path: bytes}."""
    # ail_sdk imports its sibling modules (ail_manifest ...) by name; under pip the build runs from a
    # directory that is not AIL_CURRENT, so put the source directory on sys.path for the export.
    sys.path.insert(0, str(SOURCE))
    try:
        spec = importlib.util.spec_from_file_location("ail_sdk", SOURCE / "ail_sdk.py")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        output = Path(work) / "sdk"
        module.export_sdk(SOURCE, output)
    finally:
        sys.path.remove(str(SOURCE))
    files = {}
    for path in sorted(p for p in output.rglob("*") if p.is_file()):
        files[path.relative_to(output).as_posix()] = path.read_bytes()
    return _drop_unused_sdk_files(files)


def metadata_text():
    readme = (Path(__file__).resolve().parent / "README.md").read_text(encoding="utf-8")
    return "\n".join([
        "Metadata-Version: 2.4",
        "Name: " + NAME,
        "Version: " + version(),
        "Summary: " + SUMMARY,
        "License-Expression: " + LICENSE_EXPRESSION,
        "Requires-Python: " + REQUIRES_PYTHON,
        "Project-URL: Homepage, https://github.com/J-KAMMA/ail-ci",
        "Project-URL: Documentation, https://github.com/J-KAMMA/ail-ci/blob/main/docs/INSTALL.md",
        "Project-URL: Issues, https://github.com/J-KAMMA/ail-ci/issues",
        "Classifier: Development Status :: 3 - Alpha",
        "Classifier: Environment :: Console",
        "Classifier: Intended Audience :: Developers",
        "Classifier: Operating System :: POSIX :: Linux",
        "Classifier: Operating System :: MacOS",
        "Classifier: Operating System :: Microsoft :: Windows",
        "Classifier: Programming Language :: C",
        "Classifier: Programming Language :: Python :: 3",
        "Classifier: Programming Language :: Python :: 3.10",
        "Classifier: Programming Language :: Python :: 3.11",
        "Classifier: Programming Language :: Python :: 3.12",
        "Classifier: Programming Language :: Python :: 3.13",
        "Classifier: Topic :: Software Development :: Compilers",
        "Provides-Extra: zig",
        "Requires-Dist: ziglang==0.13.0; extra == \"zig\"",
        *["License-File: " + name for name in LICENSE_FILES],
        "Description-Content-Type: text/markdown",
        "",
        readme,
    ])


def wheel_text():
    return "Wheel-Version: 1.0\nGenerator: ail_wheel_backend\nRoot-Is-Purelib: true\nTag: py3-none-any\n"


def _record_line(name, data):
    digest = base64.urlsafe_b64encode(hashlib.sha256(data).digest()).rstrip(b"=").decode("ascii")
    return name, "sha256=" + digest, str(len(data))


def wheel_name():
    return "%s-%s-py3-none-any.whl" % (DIST, version().replace("-", "_"))


def collect(work):
    """{path inside the wheel: bytes} for the whole wheel except RECORD."""
    entries = {}
    for name in PACKAGE_FILES:
        entries["%s/%s" % (IMPORT, name)] = (PACKAGE / name).read_bytes()
    for name, data in sdk_files(work).items():
        entries["%s/sdk/%s" % (IMPORT, name)] = data
    info = "%s-%s.dist-info" % (DIST, version())
    entries[info + "/METADATA"] = metadata_text().encode("utf-8")
    entries[info + "/WHEEL"] = wheel_text().encode("utf-8")
    entries[info + "/entry_points.txt"] = ENTRY_POINTS.encode("utf-8")
    for name in LICENSE_FILES:
        entries["%s/licenses/%s" % (info, name)] = (REPO / name).read_bytes()
    entries["%s/licenses/LICENSE-PSF.txt" % info] = PSF_NOTICE.read_bytes()
    return entries


def _stamp():
    epoch = int(os.environ.get("SOURCE_DATE_EPOCH", "1577836800"))      # 2020-01-01 unless told otherwise
    import time
    return time.gmtime(max(epoch, 315532800))[:6]


def build_wheel(wheel_directory, config_settings=None, metadata_directory=None):
    with tempfile.TemporaryDirectory(prefix="ail-wheel-") as work:
        entries = collect(work)
    info = "%s-%s.dist-info" % (DIST, version())
    rows = [_record_line(name, data) for name, data in sorted(entries.items())]
    rows.append((info + "/RECORD", "", ""))
    buffer = io.StringIO()
    csv.writer(buffer, lineterminator="\n").writerows(rows)
    entries[info + "/RECORD"] = buffer.getvalue().encode("utf-8")
    target = Path(wheel_directory) / wheel_name()
    stamp = _stamp()
    with zipfile.ZipFile(target, "w", zipfile.ZIP_DEFLATED) as archive:
        for name in sorted(entries):
            item = zipfile.ZipInfo(name, stamp)
            item.compress_type = zipfile.ZIP_DEFLATED
            item.external_attr = 0o644 << 16
            archive.writestr(item, entries[name])
    return target.name


def prepare_metadata_for_build_wheel(metadata_directory, config_settings=None):
    info = Path(metadata_directory) / ("%s-%s.dist-info" % (DIST, version()))
    info.mkdir(parents=True, exist_ok=True)
    (info / "METADATA").write_text(metadata_text(), encoding="utf-8")
    (info / "WHEEL").write_text(wheel_text(), encoding="utf-8")
    (info / "entry_points.txt").write_text(ENTRY_POINTS, encoding="utf-8")
    (info / "licenses").mkdir(exist_ok=True)
    for name in LICENSE_FILES:
        (info / "licenses" / name).write_bytes((REPO / name).read_bytes())
    (info / "licenses" / "LICENSE-PSF.txt").write_bytes(PSF_NOTICE.read_bytes())
    return info.name


def get_requires_for_build_wheel(config_settings=None):
    return []


def build_sdist(sdist_directory, config_settings=None):
    raise RuntimeError("ailc is built as a wheel only (an sdist would carry the private repository); "
                       "use `pip wheel .` or `python -m build --wheel`")

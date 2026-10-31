"""PEP 517 build backend for ail-lang (G14). Standard library only, so it works offline and without `wheel`.

The wheel holds three things:

* ail_lang/{__init__,__main__,cli,project,lsp}.py   the `ail` command (packaging/ail_lang/)
* ail_lang/sdk/...                      exactly what AIL_CURRENT/ail_sdk.py export_sdk() writes: the
                                        MANIFEST.json "sdk_files" list with its SHA-256 pins, plus
                                        the SDK's own MANIFEST.json and SDK_README_JA.md. There is no
                                        second file list here: whatever the SDK export refuses or
                                        leaves out (experiments/, docs/design, tasks-novel, evidence/ ...)
                                        cannot get into the wheel.
* ail_lang-<version>.dist-info/         METADATA, WHEEL, entry_points.txt, RECORD,
                                        licenses/LICENSE-APACHE and licenses/LICENSE-MIT

Only a wheel is built (`pip install .`, `pip wheel .`, `python -m build --wheel`). An sdist would have to
carry the whole private repository, so build_sdist refuses.
"""
import base64
import csv
import hashlib
import importlib.util
import io
import os
import re
import sys
import tempfile
import zipfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
PACKAGE = Path(__file__).resolve().parent / "ail_lang"
SOURCE = REPO / "AIL_CURRENT"
NAME = "ail-lang"
DIST = "ail_lang"
SUMMARY = "AIL: a Python-like language that compiles to standalone C executables"
REQUIRES_PYTHON = ">=3.10"
PACKAGE_FILES = ("__init__.py", "__main__.py", "cli.py", "project.py", "lsp.py")
LICENSE_EXPRESSION = "MIT OR Apache-2.0"
LICENSE_FILES = ("LICENSE-APACHE", "LICENSE-MIT")      # repository root; pyproject.toml license-files lists the same
ENTRY_POINTS = "[console_scripts]\nail = ail_lang.cli:main\n"


def version():
    """The one version: ail_lang/__init__.py (read, not imported)."""
    text = (PACKAGE / "__init__.py").read_text(encoding="utf-8")
    found = re.search(r'^__version__\s*=\s*"([^"]+)"', text, re.M)
    if not found:
        raise RuntimeError("no __version__ in packaging/ail_lang/__init__.py")
    return found.group(1)


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
    return files


def metadata_text():
    readme = (Path(__file__).resolve().parent / "README.md").read_text(encoding="utf-8")
    return "\n".join([
        "Metadata-Version: 2.4",
        "Name: " + NAME,
        "Version: " + version(),
        "Summary: " + SUMMARY,
        "License-Expression: " + LICENSE_EXPRESSION,
        "Requires-Python: " + REQUIRES_PYTHON,
        "Classifier: Programming Language :: Python :: 3",
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
        entries["%s/%s" % (DIST, name)] = (PACKAGE / name).read_bytes()
    for name, data in sdk_files(work).items():
        entries["%s/sdk/%s" % (DIST, name)] = data
    info = "%s-%s.dist-info" % (DIST, version())
    entries[info + "/METADATA"] = metadata_text().encode("utf-8")
    entries[info + "/WHEEL"] = wheel_text().encode("utf-8")
    entries[info + "/entry_points.txt"] = ENTRY_POINTS.encode("utf-8")
    for name in LICENSE_FILES:
        entries["%s/licenses/%s" % (info, name)] = (REPO / name).read_bytes()
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
    return info.name


def get_requires_for_build_wheel(config_settings=None):
    return []


def build_sdist(sdist_directory, config_settings=None):
    raise RuntimeError("ail-lang is built as a wheel only (an sdist would carry the private repository); "
                       "use `pip wheel .` or `python -m build --wheel`")

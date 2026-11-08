#!/usr/bin/env python3
"""Vendor pure-Python PyPI wheels and pin them in ``ail.lock``.

    python3 -m ail_pkg add NAME==VERSION [NAME==VERSION ...]
    python3 -m ail_pkg remove NAME [NAME ...]
    python3 -m ail_pkg sync
    python3 -m ail_pkg list

Run it in the project root.  ``add`` is the only command that uses the network; it
fetches the PyPI JSON metadata and one ``*-none-any.whl`` over HTTPS, verifies the
wheel's SHA-256, unpacks only ``*.py`` files and ``.dist-info`` metadata into
``ail_packages/<name>/<version>/``, caches the verified wheel in ``.ail-wheels/``,
and writes ``ail.lock`` last.  ``sync`` reproduces ``ail_packages/`` from the lock
and the cached wheels (or, when a wheel is missing, from the index) and refuses a
tampered wheel or tree.  ``remove`` and ``list`` only read the lock.

``AIL_PYPI_URL`` overrides the index base URL (the tests point it at a local HTTP
server); the default is ``https://pypi.org/pypi``.  The tool never imports or
executes a downloaded package or reads ``setup.py``.
"""
from __future__ import annotations

import argparse
import email.parser
import email.policy
import hashlib
import json
import os
import platform
import re
import shutil
import sys
import tempfile
import zipfile
from pathlib import Path
from urllib.error import URLError
from urllib.parse import urlparse
from urllib.request import Request, urlopen

LOCK = "ail.lock"
VENDOR = "ail_packages"
WHEEL_CACHE = ".ail-wheels"
DEFAULT_INDEX = "https://pypi.org/pypi"
OFFICIAL_HOSTS = {"pypi.org", "files.pythonhosted.org", "www.pythonhosted.org"}
LOCAL_HOSTS = {"127.0.0.1", "localhost", "::1"}
EXTENSION_SUFFIXES = (".so", ".pyd", ".dll", ".dylib")
MAX_DOWNLOAD = 100 * 1024 * 1024

NAME_RE = re.compile(r"^[A-Za-z0-9]([A-Za-z0-9._-]*[A-Za-z0-9])?$")
VERSION_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._+-]*$")
CANONICAL_RE = re.compile(r"[-_.]+")


class PackageError(Exception):
    """A refusal by name: the message says what was refused and why."""


# ---------------------------------------------------------------- names and files

def canonical(name):
    return CANONICAL_RE.sub("-", name).lower()


def _valid_name(name):
    return bool(NAME_RE.match(name))


def _valid_version(version):
    return bool(VERSION_RE.match(version)) and ".." not in version and "/" not in version


def _sha256_file(path):
    digest = hashlib.sha256()
    with open(path, "rb") as source:
        for chunk in iter(lambda: source.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def tree_digest(tree):
    """A deterministic digest over the sorted vendored relative paths and file bytes."""
    tree = Path(tree)
    files = sorted((path.relative_to(tree).as_posix(), path) for path in tree.rglob("*") if path.is_file())
    digest = hashlib.sha256()
    for relative, path in files:
        data = path.read_bytes()
        digest.update(relative.encode("utf-8") + b"\0" + str(len(data)).encode("ascii") + b"\0")
        digest.update(data)
    return digest.hexdigest()


def top_level_names(tree):
    """The importable top-level names a vendored tree provides."""
    names = set()
    for entry in Path(tree).iterdir():
        if entry.name.endswith((".dist-info", ".data")):
            continue
        if entry.is_file() and entry.suffix == ".py":
            names.add(entry.stem)
        elif entry.is_dir() and any(path.suffix == ".py" for path in entry.rglob("*.py")):
            names.add(entry.name)
    return names


# ---------------------------------------------------------------- index and download

def _index_base(index=None):
    return (index or os.environ.get("AIL_PYPI_URL") or DEFAULT_INDEX).rstrip("/")


def _custom_index(index=None):
    return bool(index or os.environ.get("AIL_PYPI_URL"))


def _check_url(url, index=None):
    parsed = urlparse(url)
    if parsed.scheme == "file":
        if _custom_index(index):
            return
        raise PackageError("refusing a file:// URL from the default index: %s" % url)
    if parsed.scheme not in ("http", "https"):
        raise PackageError("refusing a %s URL: %s" % (parsed.scheme or "relative", url))
    host = (parsed.hostname or "").lower()
    if host in OFFICIAL_HOSTS:
        return
    if _custom_index(index) and host in LOCAL_HOSTS:
        return
    raise PackageError("refusing a URL outside the allowlist (%s): %s" % (", ".join(sorted(OFFICIAL_HOSTS)), url))


def _open(url, index=None):
    _check_url(url, index)
    request = Request(url, headers={"User-Agent": "ail-pkg/1"})
    try:
        response = urlopen(request, timeout=60)
    except (URLError, OSError) as error:
        raise PackageError("cannot fetch %s: %s" % (url, getattr(error, "reason", error))) from None
    _check_url(response.geturl(), index)
    return response


def _fetch_json(url, index=None):
    with _open(url, index) as response:
        data = response.read(MAX_DOWNLOAD + 1)
    if len(data) > MAX_DOWNLOAD:
        raise PackageError("index response is larger than %d bytes: %s" % (MAX_DOWNLOAD, url))
    try:
        return json.loads(data.decode("utf-8"))
    except (UnicodeDecodeError, ValueError) as error:
        raise PackageError("cannot read the index metadata at %s: %s" % (url, error)) from None


def _download(url, destination, index=None):
    total = 0
    with _open(url, index) as response, open(destination, "wb") as output:
        for chunk in iter(lambda: response.read(1 << 20), b""):
            total += len(chunk)
            if total > MAX_DOWNLOAD:
                raise PackageError("download is larger than %d bytes: %s" % (MAX_DOWNLOAD, url))
            output.write(chunk)
    return total


# ---------------------------------------------------------------- versions and markers

def _version_key(version):
    parts = re.findall(r"\d+|[A-Za-z]+", version)
    key = []
    for part in parts:
        key.append((0, int(part)) if part.isdigit() else (1, part.lower()))
    return tuple(key)


def _is_stable(version):
    # PEP 440 puts a pre-release suffix directly after the release segment
    # (``1.0.0rc1``) or after a separator, so accept either boundary.
    return not re.search(r"(?:^|[._-]|\d)(?:alpha|beta|preview|pre|rc|a|b|c|dev)\d*",
                         version, re.IGNORECASE)


def _version_tuple(version):
    match = re.match(r"^(\d+)(?:\.(\d+))?(?:\.(\d+))?", version)
    if not match:
        return ()
    return tuple(int(part or 0) for part in match.groups())


def _compare(left, right, versioned=False):
    if versioned:
        left_key, right_key = _version_key(left), _version_key(right)
        return (left_key > right_key) - (left_key < right_key)
    return (left > right) - (left < right)


def _accepts_python(spec, version):
    """True when a ``Requires-Python`` style specifier accepts `version`."""
    if not spec:
        return True
    for clause in spec.split(","):
        clause = clause.strip()
        if not clause:
            continue
        match = re.match(r"^(~=|==|!=|<=|>=|<|>)\s*([0-9A-Za-z._+*-]+)$", clause)
        if not match:
            raise PackageError("unknown Requires-Python clause %r" % clause)
        operator, wanted = match.groups()
        if operator == "~=":
            prefix = wanted.rsplit(".", 1)[0]
            if not (version == wanted or version.startswith(prefix + ".")):
                return False
            continue
        comparison = _compare(version, wanted, versioned=True)
        accepted = {"==": comparison == 0, "!=": comparison != 0, "<": comparison < 0,
                    "<=": comparison <= 0, ">": comparison > 0, ">=": comparison >= 0}[operator]
        if not accepted:
            return False
    return True


_VERSION_VARS = {"python_version", "python_full_version"}
_MARKER_VARS = {
    "python_version": lambda: "%d.%d" % sys.version_info[:2],
    "python_full_version": lambda: platform.python_version(),
    "sys_platform": lambda: sys.platform,
    "os_name": lambda: os.name,
    "platform_machine": lambda: platform.machine(),
    "platform_system": lambda: platform.system(),
    "implementation_name": lambda: sys.implementation.name,
}
_MARKER_TOKEN = re.compile(r"\s*(?:(==|!=|<=|>=|~=|<|>|\(|\))|(\"[^\"]*\"|'[^']*')|([A-Za-z_][A-Za-z0-9_.]*))")


def _marker_tokens(text):
    tokens, position = [], 0
    while position < len(text):
        match = _MARKER_TOKEN.match(text, position)
        if not match:
            if text[position:].strip():
                raise PackageError("unknown environment marker %r" % text)
            break
        operator, quoted, word = match.groups()
        if operator:
            tokens.append(("op", operator))
        elif quoted:
            tokens.append(("str", quoted[1:-1]))
        else:
            tokens.append(("word", word))
        position = match.end()
    return tokens


def _marker_value(token, extra):
    kind, value = token
    if kind == "str":
        return value, False
    if kind != "word":
        raise PackageError("unknown environment marker token %r" % (value,))
    if value == "extra":
        return extra, False
    if value in _MARKER_VARS:
        return _MARKER_VARS[value](), value in _VERSION_VARS
    if value in ("and", "or", "not", "in"):
        return value, False
    raise PackageError("unknown environment marker variable %r" % value)


def _marker_compare(left_token, operator, right_token, extra):
    left, left_version = _marker_value(left_token, extra)
    right, right_version = _marker_value(right_token, extra)
    versioned = left_version or right_version
    if operator == "in":
        return left in right
    if operator == "not in":
        return left not in right
    comparison = _compare(left, right, versioned=versioned)
    return {"==": comparison == 0, "!=": comparison != 0, "<": comparison < 0,
            "<=": comparison <= 0, ">": comparison > 0, ">=": comparison >= 0,
            "~=": comparison == 0 or left.startswith(right + ".")}[operator]


def _eval_marker(text, extra=""):
    tokens = _marker_tokens(text)
    position = 0

    def peek():
        return tokens[position] if position < len(tokens) else (None, None)

    def take():
        nonlocal position
        token = peek()
        position += 1
        return token

    def expression():
        value = conjunction()
        while peek() == ("word", "or"):
            take()
            right = conjunction()
            value = value or right
        return value

    def conjunction():
        value = atom()
        while peek() == ("word", "and"):
            take()
            right = atom()
            value = value and right
        return value

    def atom():
        if peek() == ("op", "("):
            take()
            value = expression()
            if take() != ("op", ")"):
                raise PackageError("unclosed parenthesis in environment marker %r" % text)
            return value
        left = take()
        if peek() == ("word", "not") and position + 1 < len(tokens) and tokens[position + 1] == ("word", "in"):
            take()
            take()
            return _marker_compare(left, "not in", take(), extra)
        kind, value = peek()
        if kind == "op":
            take()
            return _marker_compare(left, value, take(), extra)
        if (kind, value) == ("word", "in"):
            take()
            return _marker_compare(left, "in", take(), extra)
        raise PackageError("unknown environment marker %r" % text)

    if not tokens:
        return True
    result = expression()
    if position != len(tokens):
        raise PackageError("trailing tokens in environment marker %r" % text)
    return bool(result)


def _parse_requirement(text):
    """(canonical name, extras, marker) for one Requires-Dist value."""
    main, _, marker = text.partition(";")
    main, marker = main.strip(), marker.strip() or None
    match = re.match(r"^([A-Za-z0-9][A-Za-z0-9._-]*)\s*(\[[^\]]*\])?\s*(.*)$", main)
    if not match:
        raise PackageError("cannot read the requirement %r" % text)
    name, extras, specifier = match.groups()
    return canonical(name), (extras or "").strip(), specifier.strip(), marker


# ---------------------------------------------------------------- wheel selection

def _release_files(data):
    release = data.get("releases")
    if isinstance(release, dict):
        return {version: files for version, files in release.items() if isinstance(files, list)}
    version = (data.get("info") or {}).get("version")
    return {version: data.get("urls", [])} if version else {}


def _file_is_pure_wheel(item):
    return item.get("packagetype") == "bdist_wheel" and str(item.get("filename", "")).endswith("-none-any.whl")


def _wheel_python_tags(item):
    """The interpreter tags of a wheel filename: ``py2.py3`` -> ``["py2", "py3"]``."""
    filename = str(item.get("filename", ""))
    if not filename.endswith(".whl"):
        return []
    parts = filename[:-4].split("-")
    if len(parts) < 5:
        return []
    return [tag.lower() for tag in parts[-3].split(".")]


def _python_tag_ok(tag):
    return bool(re.match(r"^(?:py|cp|pp)3\d*$", tag))


def _file_is_python3_wheel(item):
    return _file_is_pure_wheel(item) and any(_python_tag_ok(tag) for tag in _wheel_python_tags(item))


def _file_is_sdist(item):
    filename = str(item.get("filename", ""))
    return item.get("packagetype") == "sdist" or filename.endswith((".tar.gz", ".zip", ".tar.bz2"))


def _pick_file(name, version, files, python_version):
    compatible = []
    for item in files:
        if item.get("yanked"):
            continue
        required = item.get("requires_python")
        if required and not _accepts_python(required, python_version):
            continue
        compatible.append(item)
    for item in compatible:
        if _file_is_python3_wheel(item):
            return item
    pure = [item for item in files if _file_is_pure_wheel(item)]
    if pure:
        if any(_file_is_python3_wheel(item) for item in pure):
            raise PackageError("%s==%s: no pure-Python wheel for Python %s (requires_python excludes it)"
                               % (name, version, python_version))
        raise PackageError("%s==%s: no pure-Python wheel for Python 3 (the wheel is for Python 2)"
                           % (name, version))
    if any(_file_is_sdist(item) for item in files):
        raise PackageError("%s==%s: sdists run code at build time; AIL never does"
                           % (name, version))
    if any(item.get("packagetype") == "bdist_wheel" for item in files):
        raise PackageError("%s==%s: requires a C extension (no *-none-any.whl)"
                           % (name, version))
    raise PackageError("%s==%s: no pure-Python wheel" % (name, version))


def _select_release(name, version, index, python_version):
    base = _index_base(index)
    if version is None:
        data = _fetch_json("%s/%s/json" % (base, name), index)
        releases = _release_files(data)
        candidates = []
        for candidate, files in releases.items():
            if not _valid_version(candidate) or not _is_stable(candidate):
                continue
            try:
                item = _pick_file(name, candidate, files, python_version)
            except PackageError:
                continue
            candidates.append((_version_key(candidate), candidate, item))
        if not candidates:
            raise PackageError("%s: no non-yanked stable version with a pure-Python wheel" % name)
        candidates.sort(key=lambda candidate: candidate[0])
        _, version, item = candidates[-1]
        return version, item
    try:
        data = _fetch_json("%s/%s/%s/json" % (base, name, version), index)
    except PackageError as error:
        if "404" in str(error):
            raise PackageError("%s==%s: no such version on the index" % (name, version)) from None
        raise
    files = data.get("urls")
    if not isinstance(files, list):
        files = _release_files(data).get(version, [])
    item = _pick_file(name, version, files, python_version)
    return version, item


# ---------------------------------------------------------------- archive safety

def _safe_member(name):
    if "\x00" in name or "\\" in name:
        raise PackageError("wheel entry escapes its directory: %r" % name)
    if name.startswith("/") or re.match(r"^[A-Za-z]:", name):
        raise PackageError("wheel entry has an absolute path: %r" % name)
    parts = name.rstrip("/").split("/")
    if not parts or any(part in ("", ".", "..") for part in parts):
        raise PackageError("wheel entry escapes its directory: %r" % name)
    return parts


def _safe_extract(wheel, destination):
    """Extract only *.py and .dist-info metadata below `destination`."""
    destination = Path(destination)
    destination.mkdir(parents=True, exist_ok=True)
    seen = set()
    root = destination.resolve()
    with zipfile.ZipFile(wheel) as archive:
        for info in archive.infolist():
            parts = _safe_member(info.filename)
            mode = (info.external_attr >> 16) & 0o170000
            if mode == 0o120000:
                raise PackageError("%s: wheel contains a symbolic link: %s" % (wheel.name, info.filename))
            folded = "/".join(parts).casefold()
            if folded in seen:
                raise PackageError("%s: wheel contains a duplicate entry: %s" % (wheel.name, info.filename))
            seen.add(folded)
            lowered = [part.lower() for part in parts]
            if any(part.endswith(EXTENSION_SUFFIXES) for part in lowered):
                raise PackageError("%s: requires a C extension (%s)" % (wheel.name, info.filename))
            if info.is_dir():
                continue
            keep = parts[-1].endswith((".py", ".pyi")) or any(part.endswith(".dist-info") for part in lowered)
            if not keep:
                continue
            target = (destination / Path(*parts)).resolve()
            if target != root and root not in target.parents:
                raise PackageError("%s: wheel entry escapes its directory: %s" % (wheel.name, info.filename))
            target.parent.mkdir(parents=True, exist_ok=True)
            with archive.open(info) as source, open(target, "wb") as output:
                shutil.copyfileobj(source, output)


def _metadata(tree):
    files = sorted(Path(tree).glob("*.dist-info/METADATA"))
    if not files:
        raise PackageError("wheel has no .dist-info/METADATA")
    try:
        text = files[0].read_text(encoding="utf-8", errors="replace")
    except OSError as error:
        raise PackageError("cannot read wheel metadata: %s" % error) from None
    return email.parser.Parser(policy=email.policy.compat32).parsestr(text)


def _license(metadata):
    for field in ("License-Expression", "License"):
        value = metadata.get(field)
        if value:
            line = " ".join(value.split())
            return line[:120] if line else "unknown"
    return "unknown"


def _requirements(metadata, name, locked_versions):
    """(dependency names, requirement strings) for the requirements active here."""
    requires, constraints = [], []
    for text in metadata.get_all("Requires-Dist") or []:
        dependency, extras, specifier, marker = _parse_requirement(text)
        if marker is not None and not _eval_marker(marker):
            continue
        if extras:
            raise PackageError("%s: extras in a requirement are not supported (%s)" % (name, text.strip()))
        specifier = re.sub(r"\s+", "", specifier)
        if dependency not in locked_versions:
            raise PackageError("%s requires %s%s; run `ail add %s` first"
                               % (name, dependency, (" " + specifier) if specifier else "", dependency))
        if specifier and not _accepts_python(specifier, locked_versions[dependency]):
            raise PackageError("%s requires %s%s, but %s is locked at %s"
                               % (name, dependency, specifier, dependency, locked_versions[dependency]))
        if dependency not in requires:
            requires.append(dependency)
            constraints.append(dependency + specifier)
    return requires, constraints


def _entry_constraints(entry):
    """The lock entry's requirement strings, falling back to bare names for old locks."""
    constraints = entry.get("require_specs")
    if isinstance(constraints, list) and constraints:
        return constraints
    return list(entry.get("requires", []))


def _check_reverse_requirements(data, key, version):
    """Refuse a version that an already locked package's specifier does not accept."""
    for other, entry in data["package"].items():
        if other == key:
            continue
        for text in _entry_constraints(entry):
            dependency, _extras, specifier, marker = _parse_requirement(text)
            if marker is not None and not _eval_marker(marker):
                continue
            if dependency == key and specifier and not _accepts_python(specifier, version):
                raise PackageError("%s is required by %s (%s), which does not accept %s"
                                   % (key, other, text, version))


# ---------------------------------------------------------------- lock

def _toml_string(value):
    return json.dumps(value, ensure_ascii=False)


def _lock_path(root):
    return Path(root) / LOCK


def _empty_lock():
    return {"version": 1, "package": {}}


def _read_lock_subset(text):
    data = {"version": 1, "package": {}}
    table = data
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("[package.") and line.endswith("]"):
            name = line[len("[package."):-1].strip().strip('"')
            table = data["package"].setdefault(name, {})
            continue
        key, separator, value = line.partition("=")
        if not separator:
            raise PackageError("%s: expected key = value" % LOCK)
        key, value = key.strip().strip('"'), value.strip()
        if value.startswith("["):
            if not value.endswith("]"):
                raise PackageError("%s: an array is not closed" % LOCK)
            items = [item.strip() for item in value[1:-1].split(",") if item.strip()]
            table[key] = [json.loads(item) for item in items]
        elif value.startswith(("\"", "'")):
            table[key] = json.loads(value)
        elif value in ("true", "false"):
            table[key] = value == "true"
        else:
            try:
                table[key] = int(value)
            except ValueError:
                raise PackageError("%s: cannot read the value %r" % (LOCK, value)) from None
    return data


def load_lock(root, missing_ok=False):
    path = _lock_path(root)
    if not path.is_file():
        if missing_ok:
            return _empty_lock()
        raise PackageError("no %s; run `ail add NAME==VERSION` first" % LOCK)
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as error:
        raise PackageError("cannot read %s: %s" % (LOCK, error)) from None
    try:
        import tomllib
    except ImportError:
        data = _read_lock_subset(text)
    else:
        try:
            data = tomllib.loads(text)
        except tomllib.TOMLDecodeError as error:
            raise PackageError("%s: %s" % (LOCK, error)) from None
    if data.get("version") != 1:
        raise PackageError("%s: unsupported lock version %r" % (LOCK, data.get("version")))
    packages = data.get("package") or {}
    if not isinstance(packages, dict):
        raise PackageError("%s: package must be a table" % LOCK)
    data["package"] = packages
    for name, entry in packages.items():
        if not isinstance(entry, dict):
            raise PackageError("%s: package.%s must be a table" % (LOCK, name))
        for key in ("version", "wheel", "sha256", "tree_sha256"):
            if not isinstance(entry.get(key), str) or not entry[key]:
                raise PackageError("%s: package.%s.%s is required" % (LOCK, name, key))
        if not _valid_version(entry["version"]):
            raise PackageError("%s: package.%s.version is not a plain version" % (LOCK, name))
        entry.setdefault("requires", [])
        if not isinstance(entry["requires"], list) or not all(isinstance(item, str) for item in entry["requires"]):
            raise PackageError("%s: package.%s.requires must be a list of names" % (LOCK, name))
        entry.setdefault("require_specs", list(entry["requires"]))
        if not isinstance(entry["require_specs"], list) or not all(isinstance(item, str) for item in entry["require_specs"]):
            raise PackageError("%s: package.%s.require_specs must be a list of requirements" % (LOCK, name))
        entry.setdefault("license", "unknown")
        entry.setdefault("requires_python", "")
        try:
            entry["size"] = int(entry.get("size", 0))
        except (TypeError, ValueError):
            raise PackageError("%s: package.%s.size must be an integer" % (LOCK, name)) from None
    return data


def _write_lock(root, data):
    lines = ["# generated by ail_pkg; do not edit", "version = 1", ""]
    for name in sorted(data["package"]):
        entry = data["package"][name]
        lines.append("[package.%s]" % _toml_string(name))
        lines.append("version = %s" % _toml_string(entry["version"]))
        lines.append("wheel = %s" % _toml_string(entry["wheel"]))
        lines.append("sha256 = %s" % _toml_string(entry["sha256"]))
        lines.append("size = %d" % int(entry.get("size", 0)))
        lines.append("requires_python = %s" % _toml_string(entry.get("requires_python", "")))
        lines.append("license = %s" % _toml_string(entry.get("license", "unknown")))
        lines.append("requires = [%s]" % ", ".join(_toml_string(item) for item in entry.get("requires", [])))
        lines.append("require_specs = [%s]" % ", ".join(_toml_string(item) for item in _entry_constraints(entry)))
        lines.append("tree_sha256 = %s" % _toml_string(entry["tree_sha256"]))
        lines.append("")
    path = _lock_path(root)
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_text("\n".join(lines), encoding="utf-8")
    os.replace(temporary, path)


# ---------------------------------------------------------------- add / remove / sync / list

def _vendor_dir(root, name, version):
    return Path(root) / VENDOR / name / version


def _wheel_cache_path(root, filename):
    return Path(root) / WHEEL_CACHE / filename


def _existing_names(data):
    return set(data["package"])


def _check_conflicts(name, tree, locked, data, tree_of):
    new_names = top_level_names(tree)
    if not new_names:
        raise PackageError("%s: wheel provides no Python modules" % name)
    for other in locked:
        if other == name:
            continue
        other_tree = tree_of(other)
        if not other_tree.is_dir():
            raise PackageError("%s: the vendored tree for %s is missing; run `ail sync` first"
                               % (name, other))
        overlap = new_names & top_level_names(other_tree)
        if overlap:
            raise PackageError("%s provides the top-level name %s, already provided by %s"
                               % (name, ", ".join(sorted(overlap)), other))


def _tree_of_locked(root, name, entry):
    return _vendor_dir(root, name, entry["version"])


def _stage_wheel(root, name, version, index, expected_sha=None, filename=None):
    """Download one wheel into a private directory and return (path, size, sha256)."""
    python_version = "%d.%d" % sys.version_info[:2]
    selected_version, item = _select_release(name, version, index, python_version)
    if version is not None and selected_version != version:
        raise PackageError("%s: index returned version %s for %s" % (name, selected_version, version))
    filename = filename or item.get("filename")
    if not filename or not filename.endswith("-none-any.whl"):
        raise PackageError("%s==%s: requires a C extension" % (name, selected_version))
    if not any(_python_tag_ok(tag) for tag in _wheel_python_tags({"filename": filename})):
        raise PackageError("%s==%s: the wheel %s is not for Python 3" % (name, selected_version, filename))
    digest = (item.get("digests") or {}).get("sha256")
    if not digest:
        raise PackageError("%s==%s: the index has no sha256 for %s" % (name, selected_version, filename))
    if expected_sha and digest.lower() != expected_sha.lower():
        raise PackageError("%s==%s: index sha256 %s does not match the lock's %s"
                           % (name, selected_version, digest, expected_sha))
    url = item.get("url")
    if not url:
        raise PackageError("%s==%s: the index entry has no URL" % (name, selected_version))
    work = Path(tempfile.mkdtemp(prefix=".ail-download-", dir=root))
    path = work / filename
    try:
        size = _download(url, path, index)
    except Exception:
        shutil.rmtree(work, ignore_errors=True)
        raise
    actual = _sha256_file(path)
    if actual.lower() != digest.lower():
        shutil.rmtree(work, ignore_errors=True)
        raise PackageError("%s==%s: wheel sha256 mismatch (index %s, download %s)"
                           % (name, selected_version, digest, actual))
    if expected_sha and actual.lower() != expected_sha.lower():
        shutil.rmtree(work, ignore_errors=True)
        raise PackageError("%s==%s: wheel sha256 %s does not match the lock's %s"
                           % (name, selected_version, actual, expected_sha))
    return path, size, actual, selected_version, work


def add(root, specs, index=None):
    root = Path(root)
    data = load_lock(root, missing_ok=True)
    added = []
    for spec in specs:
        name, separator, version = spec.partition("==")
        name, version = name.strip(), version.strip() if separator else None
        if not separator:
            if re.search(r"[<>=!~]", name):
                raise PackageError("%s: only exact `NAME==VERSION` pins are accepted" % spec)
            version = None
        if not _valid_name(name):
            raise PackageError("invalid package name %r" % name)
        if version is not None and not _valid_version(version):
            raise PackageError("%s: invalid version %r" % (name, version))
        key = canonical(name)
        path, size, digest, selected_version, work = _stage_wheel(root, name, version, index)
        try:
            tree = work / "tree"
            _safe_extract(path, tree)
            metadata = _metadata(tree)
            metadata_name = metadata.get("Name") or ""
            metadata_version = metadata.get("Version") or ""
            if canonical(metadata_name) != key:
                raise PackageError("%s==%s: wheel metadata names %r"
                                   % (name, selected_version, metadata_name))
            if metadata_version != selected_version:
                raise PackageError("%s: wheel metadata version %r is not %r"
                                   % (name, metadata_version, selected_version))
            required_python = metadata.get("Requires-Python") or ""
            python_version = "%d.%d" % sys.version_info[:2]
            if required_python and not _accepts_python(required_python, python_version):
                raise PackageError("%s==%s: requires_python %r does not accept Python %s"
                                   % (name, selected_version, required_python, python_version))
            locked = _existing_names(data)
            locked_versions = {other: data["package"][other]["version"] for other in locked}
            requires, constraints = _requirements(metadata, name, locked_versions)
            _check_conflicts(key, tree, locked, data, lambda other: _tree_of_locked(root, other, data["package"][other]))
            _check_reverse_requirements(data, key, selected_version)
            old = data["package"].get(key)
            if old and old["sha256"].lower() != digest.lower():
                raise PackageError("%s: lock already pins sha256 %s, the index has %s"
                                   % (name, old["sha256"], digest))
            destination = _vendor_dir(root, key, selected_version)
            destination.parent.mkdir(parents=True, exist_ok=True)
            if destination.exists():
                shutil.rmtree(destination)
            for stale in destination.parent.iterdir():
                if stale.is_dir() and stale != destination:
                    shutil.rmtree(stale)
            os.replace(tree, destination)
            cache = _wheel_cache_path(root, path.name)
            cache.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(path, cache)
            data["package"][key] = {
                "version": selected_version,
                "wheel": path.name,
                "sha256": digest,
                "size": size,
                "requires_python": required_python,
                "license": _license(metadata),
                "requires": requires,
                "require_specs": constraints,
                "tree_sha256": tree_digest(destination),
            }
            _write_lock(root, data)
            added.append(key)
            print("added %s %s (%s) sha256:%s" % (key, selected_version,
                                                 data["package"][key]["license"], digest[:12]))
        finally:
            shutil.rmtree(work, ignore_errors=True)
    return 0


def remove(root, names):
    root = Path(root)
    data = load_lock(root)
    for name in names:
        key = canonical(name)
        if key not in data["package"]:
            raise PackageError("%s is not in %s" % (key, LOCK))
        dependents = sorted(other for other, entry in data["package"].items()
                            if other != key and key in entry.get("requires", []))
        if dependents:
            raise PackageError("%s is required by %s; remove %s first"
                               % (key, ", ".join(dependents), dependents[0]))
    for name in names:
        key = canonical(name)
        entry = data["package"].pop(key)
        shutil.rmtree(Path(root) / VENDOR / key, ignore_errors=True)
        cache = _wheel_cache_path(root, entry["wheel"])
        if cache.is_file() and not any(item["wheel"] == entry["wheel"] for item in data["package"].values()):
            cache.unlink()
        print("removed %s %s" % (key, entry["version"]))
    _write_lock(root, data)
    return 0


def sync(root, index=None):
    root = Path(root)
    data = load_lock(root)
    packages = data["package"]
    for name, entry in packages.items():
        for text in _entry_constraints(entry):
            dependency, _extras, specifier, marker = _parse_requirement(text)
            if marker is not None and not _eval_marker(marker):
                continue
            if dependency not in packages:
                raise PackageError("%s requires %s, which is not in %s; run `ail add %s`"
                                   % (name, dependency, LOCK, dependency))
            if specifier and not _accepts_python(specifier, packages[dependency]["version"]):
                raise PackageError("%s requires %s%s, but %s is locked at %s"
                                   % (name, dependency, specifier, dependency, packages[dependency]["version"]))
    work = Path(tempfile.mkdtemp(prefix=".ail-sync-", dir=root))
    downloads = []
    staged = []
    try:
        for name in sorted(packages):
            entry = packages[name]
            wheel = _wheel_cache_path(root, entry["wheel"])
            if wheel.is_file():
                actual = _sha256_file(wheel)
                if actual.lower() != entry["sha256"].lower():
                    raise PackageError("%s: cached wheel %s has sha256 %s, the lock says %s (tampered)"
                                       % (name, entry["wheel"], actual, entry["sha256"]))
                source = wheel
            else:
                source, _size, _digest, _version, download = _stage_wheel(
                    root, name, entry["version"], index, expected_sha=entry["sha256"], filename=entry["wheel"])
                downloads.append(download)
                cache = _wheel_cache_path(root, entry["wheel"])
                cache.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy(source, cache)
                source = cache
            tree = work / name
            _safe_extract(source, tree)
            metadata = _metadata(tree)
            if canonical(metadata.get("Name") or "") != name or (metadata.get("Version") or "") != entry["version"]:
                raise PackageError("%s: wheel metadata does not match the lock (%s %s)"
                                   % (name, metadata.get("Name"), metadata.get("Version")))
            actual_tree = tree_digest(tree)
            if actual_tree != entry["tree_sha256"]:
                raise PackageError("%s: vendored tree digest %s does not match the lock's %s"
                                   % (name, actual_tree, entry["tree_sha256"]))
            staged.append((name, tree, entry["version"]))
        vendor = root / VENDOR
        if vendor.exists():
            for directory in sorted(vendor.iterdir()):
                if directory.name not in packages:
                    shutil.rmtree(directory) if directory.is_dir() else directory.unlink()
        for name, tree, version in staged:
            destination = _vendor_dir(root, name, version)
            destination.parent.mkdir(parents=True, exist_ok=True)
            if destination.exists():
                shutil.rmtree(destination)
            for stale in destination.parent.iterdir():
                if stale.is_dir() and stale != destination:
                    shutil.rmtree(stale)
            os.replace(tree, destination)
        print("synced %d package%s" % (len(packages), "" if len(packages) == 1 else "s"))
    finally:
        shutil.rmtree(work, ignore_errors=True)
        for download in downloads:
            shutil.rmtree(download, ignore_errors=True)
    return 0


def list_packages(root):
    root = Path(root)
    data = load_lock(root)
    for name in sorted(data["package"]):
        entry = data["package"][name]
        print("%s %s %s sha256:%s" % (name, entry["version"], entry.get("license", "unknown"),
                                      entry["sha256"][:12]))
    return 0


# ---------------------------------------------------------------- CLI

def main(argv=None):
    parser = argparse.ArgumentParser(prog="ail_pkg", description="Vendor pure-Python wheels and pin ail.lock.")
    parser.add_argument("--index", help="index base URL (default: $AIL_PYPI_URL or %s)" % DEFAULT_INDEX)
    commands = parser.add_subparsers(dest="command", required=True)
    add_parser = commands.add_parser("add", help="fetch, verify and vendor NAME==VERSION")
    add_parser.add_argument("specs", nargs="+", metavar="NAME[==VERSION]")
    remove_parser = commands.add_parser("remove", help="remove vendored packages and their lock entries")
    remove_parser.add_argument("names", nargs="+", metavar="NAME")
    commands.add_parser("sync", help="install exactly what ail.lock says")
    commands.add_parser("list", help="show the locked packages")
    arguments = parser.parse_args(argv)
    root = Path.cwd()
    try:
        if arguments.command == "add":
            return add(root, arguments.specs, arguments.index)
        if arguments.command == "remove":
            return remove(root, arguments.names)
        if arguments.command == "sync":
            return sync(root, arguments.index)
        return list_packages(root)
    except PackageError as error:
        print("ail_pkg: %s" % error, file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())

#!/usr/bin/env python3
"""Write a CycloneDX 1.5 software bill of materials for one AIL binary.

    python3 tools/sbom.py BINARY --source SRC --debug-dir DIR -o out.cdx.json

The BOM names the AIL compiler and its git commit, the C compiler and its version, every
shared library the executable really needs (readelf DT_NEEDED), each bundled C source or
runtime header that the generated C carries, and every Rust crate in the nearest
Cargo.lock.  A Debian package version and licence are filled in where dpkg can tell them.

`--check` writes the same file and also compares the BOM with the binary, the link line
recorded by `--debug-dir` and the generated C.  Only the standard library is used; the
CycloneDX shape is checked by `validate_bom` without a network fetch or a schema file.
"""
import argparse
import hashlib
import json
import os
import re
import shutil
import struct
import subprocess
import sys
import tomllib
import uuid
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import quote

REPO = Path(__file__).resolve().parents[1]
AIL_VERSION = REPO / "packaging" / "ail_lang" / "__init__.py"
COMPONENT_TYPES = frozenset({
    "application", "framework", "library", "container", "platform", "operating-system",
    "device", "device-driver", "firmware", "file", "machine-learning-model", "data",
})
SPDX_IDS = {
    "zlib": "Zlib",
    "lgpl-2.1": "LGPL-2.1-only",
    "lgpl-2.1+": "LGPL-2.1-or-later",
    "lgpl-2.1-or-later": "LGPL-2.1-or-later",
    "lgpl-2.0+": "LGPL-2.0-or-later",
    "gpl-2": "GPL-2.0-only",
    "gpl-2+": "GPL-2.0-or-later",
    "gpl-2.0+": "GPL-2.0-or-later",
    "gpl-3+": "GPL-3.0-or-later",
    "mit": "MIT",
    "apache-2.0": "Apache-2.0",
    "isc": "ISC",
    "curl": "curl",
    "bsd-2-clause": "BSD-2-Clause",
    "bsd-3-clause": "BSD-3-Clause",
}
AIL_LICENSE = [{"expression": "MIT OR Apache-2.0"}]


def run(command, timeout=60):
    try:
        return subprocess.run(command, capture_output=True, text=True, timeout=timeout)
    except (OSError, subprocess.TimeoutExpired) as error:
        return None


def digest(data):
    return hashlib.sha256(data).hexdigest()


def file_digest(path):
    try:
        return digest(Path(path).read_bytes())
    except OSError:
        return None


def read_json(path):
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def readelf_needed(binary):
    done = run(["readelf", "-d", "-W", str(binary)])
    if done is None or done.returncode != 0:
        return elf_needed(Path(binary))
    return re.findall(r"\(NEEDED\)\s+Shared library: \[([^\]]+)\]", done.stdout)


def elf_needed(path):
    """DT_NEEDED names from the .dynamic section, for a host without readelf."""
    try:
        data = Path(path).read_bytes()
    except OSError:
        return []
    if len(data) < 0x34 or data[:4] != b"\x7fELF":
        return []
    try:
        endian = "<" if data[5] == 1 else ">"
        if data[4] == 2:
            shoff = struct.unpack_from(endian + "Q", data, 0x28)[0]
            shentsize, shnum = struct.unpack_from(endian + "HH", data, 0x3A)
            fmt = endian + "IIQQQQIIQQ"
        else:
            shoff = struct.unpack_from(endian + "I", data, 0x20)[0]
            shentsize, shnum = struct.unpack_from(endian + "HH", data, 0x2E)
            fmt = endian + "IIIIIIIIII"
        rows = []
        for index in range(shnum):
            fields = struct.unpack_from(fmt, data, shoff + index * shentsize)
            rows.append((fields[0], fields[1], fields[4], fields[5], fields[6]))
        wanted = [(kind, offset, size, link) for (_, kind, offset, size, link) in rows
                  if kind == 6]
        if not wanted:
            return []
        _, offset, size, link = wanted[0]
        if link >= len(rows):
            return []
        _, _, str_off, str_size, _ = rows[link]
        strings = data[str_off:str_off + str_size]
        names = []
        entry = 16 if data[4] == 2 else 8
        for at in range(offset, offset + size, entry):
            if data[4] == 2:
                tag, value = struct.unpack_from(endian + "QQ", data, at)
            else:
                tag, value = struct.unpack_from(endian + "II", data, at)
            if tag == 0:
                break
            if tag == 1:
                end = strings.find(b"\0", value)
                names.append(strings[value:end if end >= 0 else len(strings)].decode("utf-8", "replace"))
        return names
    except (struct.error, IndexError):
        return []


def ldconfig_map():
    done = run(["ldconfig", "-p"])
    found = {}
    if done is None or done.returncode != 0:
        return found
    for line in done.stdout.splitlines():
        match = re.match(r"\s*(\S+)\s+\([^)]*\)\s+=>\s+(\S+)", line)
        if match:
            found.setdefault(match.group(1), match.group(2))
    return found


def ldd_map(binary):
    done = run(["ldd", str(binary)])
    found = {}
    if done is None or done.returncode != 0:
        return found
    for line in done.stdout.splitlines():
        match = re.match(r"\s*(\S+)\s+=>\s+(\S+)", line)
        if match:
            found[match.group(1)] = match.group(2)
    return found


def resolve_library(soname, binary, mapping):
    path = mapping.get(soname)
    if path and Path(path).exists():
        return str(Path(path).resolve())
    for directory in ("/lib", "/usr/lib", "/lib64", "/usr/lib64",
                      "/lib/x86_64-linux-gnu", "/usr/lib/x86_64-linux-gnu",
                      "/lib/aarch64-linux-gnu", "/usr/lib/aarch64-linux-gnu"):
        candidate = Path(directory) / soname
        if candidate.exists():
            return str(candidate.resolve())
    return None


def dpkg_package(path):
    if not path:
        return {}
    for candidate in (path, str(Path(path).resolve())):
        done = run(["dpkg", "-S", candidate])
        if done is None or done.returncode != 0:
            continue
        match = re.search(r"^\s*([^:\s]+)(?::\S+)?:\s", done.stdout, re.M)
        if not match:
            continue
        package = match.group(1)
        info = run(["dpkg-query", "-W", "-f=${Package}\t${Version}\t${Source}\t${Architecture}",
                    package])
        if info is None or info.returncode != 0:
            info = run(["dpkg-query", "-W", "-f=${Package}\t${Version}\t${Source}\t${Architecture}",
                        package + ":amd64"])
        if info is not None and info.returncode == 0:
            parts = (info.stdout.strip().split("\t") + ["", "", "", ""])[:4]
            return {"package": parts[0] or package, "version": parts[1],
                    "source": parts[2] or parts[0], "architecture": parts[3]}
        return {"package": package, "version": "", "source": package, "architecture": ""}
    return {}


def license_from_text(text):
    if not text:
        return None
    if re.search(r"GNU Lesser General Public", text, re.I):
        return "LGPL-2.1-or-later"
    if re.search(r"^License:\s*Zlib", text, re.M | re.I):
        return "Zlib"
    match = re.search(r"^License:\s*(\S+)", text, re.M)
    if match:
        return match.group(1)
    if re.search(r"Permission is hereby granted, free of charge", text):
        return "MIT"
    if re.search(r"Apache License", text, re.I) and re.search(r"Version 2\.0", text):
        return "Apache-2.0"
    if re.search(r"Redistribution and use in source and binary forms", text):
        return "BSD-3-Clause"
    if re.search(r"GNU General Public", text, re.I):
        return "GPL-2.0-or-later"
    return None


def package_license(info):
    for name in (info.get("source"), info.get("package")):
        if not name:
            continue
        for suffix in ("copyright", "README.Debian"):
            path = Path("/usr/share/doc") / name / suffix
            if path.is_file():
                try:
                    text = path.read_text(encoding="utf-8", errors="replace")
                except OSError:
                    continue
                found = license_from_text(text)
                if found:
                    return found
    return None


def license_value(value):
    if not value:
        return None
    key = value.strip().lower()
    if key in SPDX_IDS:
        return {"license": {"id": SPDX_IDS[key]}}
    if re.fullmatch(r"[A-Za-z0-9.+-]+", value) and value.lower() in SPDX_IDS:
        return {"license": {"id": SPDX_IDS[value.lower()]}}
    return {"license": {"name": value}}


def versions(text):
    return re.findall(r"\b\d+(?:\.\d+)+(?:[-+][0-9A-Za-z.-]+)?\b", text)


def compiler_vendor(banner):
    text = banner.lower()
    if "gcc" in text or "free software foundation" in text:
        return "GNU"
    if "clang" in text or "llvm" in text:
        return "LLVM"
    return ""


def compiler_info(command):
    token = command or os.environ.get("CC") or "cc"
    path = shutil.which(token) or token
    real = str(Path(path).resolve()) if Path(path).exists() else path
    done = run([token, "--version"])
    text = done.stdout.strip() if done is not None and done.returncode == 0 else ""
    first = text.splitlines()[0].strip() if text else ""
    found = versions(first) or versions(text)
    version = found[0] if found else ""
    return {"name": Path(real).name or Path(token).name, "path": real,
            "version": version, "banner": first,
            "vendor": compiler_vendor(first),
            "package": dpkg_package(real).get("package", "")}


def ail_info(repo):
    version = ""
    try:
        text = (Path(repo) / "packaging" / "ail_lang" / "__init__.py").read_text(encoding="utf-8")
        match = re.search(r'^__version__\s*=\s*["\']([^"\']+)', text, re.M)
        if match:
            version = match.group(1)
    except OSError:
        pass
    commit = ""
    done = run(["git", "-C", str(repo), "rev-parse", "HEAD"])
    if done is not None and done.returncode == 0:
        commit = done.stdout.strip()
    return {"version": version or "unknown", "commit": commit or "unknown"}


def native_report(debug_dir):
    report = read_json(Path(debug_dir) / "native_report.json")
    if not isinstance(report, dict):
        return {"compiler": "", "link_flags": [], "sources": [], "command": [], "path": None}
    path = Path(debug_dir) / "native_report.json"
    command = []
    for operation in report.get("operations", []):
        if operation.get("phase") == "compile_link" and operation.get("exit_code") == 0:
            command = [str(part) for part in operation.get("command", [])]
    return {
        "compiler": command[0] if command else "",
        "link_flags": [part for part in command if part.startswith("-l") or part.endswith(".a")],
        "sources": [part for part in command if part.endswith((".c", ".o", ".a"))],
        "command": command,
        "path": str(path),
    }


def generated_text(debug_dir):
    parts = []
    for path in sorted(Path(debug_dir).rglob("*.c")):
        try:
            parts.append(path.read_text(encoding="utf-8", errors="replace"))
        except OSError:
            continue
    return "\n".join(parts)


def function_names(path):
    try:
        text = Path(path).read_text(encoding="utf-8", errors="replace")
    except OSError:
        return []
    skip = {"if", "for", "while", "switch", "return", "sizeof", "else", "do"}
    names = []
    for match in re.finditer(r"(?m)^([A-Za-z_][A-Za-z0-9_\s\*]*?)\b([A-Za-z_][A-Za-z0-9_]*)"
                             r"\s*\([^;{}]*\)\s*\{", text):
        if re.search(r"\bstatic\b", match.group(1)):
            continue
        name = match.group(2)
        if name not in skip:
            names.append(name)
    return names


def header_guard(path):
    try:
        text = Path(path).read_text(encoding="utf-8", errors="replace")
    except OSError:
        return None
    match = re.search(r"(?m)^#ifndef\s+([A-Za-z_][A-Za-z0-9_]*)", text)
    return match.group(1) if match else None


def bundled_sources(repo, debug_dir):
    text = generated_text(debug_dir)
    found = []
    seen = set()
    roots = [Path(repo) / "AIL_CURRENT" / "python" / "pkg-v12",
             Path(repo) / "AIL_CURRENT" / "stdlib"]
    candidates = []
    for root in roots:
        if root.is_dir():
            candidates.extend(sorted(root.glob("*.h")))
            candidates.extend(sorted(root.glob("*.c")))
    for path in candidates:
        if path.suffix == ".h":
            guard = header_guard(path)
            if guard and re.search(r"\b" + re.escape(guard) + r"\b", text):
                kind = "runtime-header" if path.parent.name == "pkg-v12" else "bundled-header"
                found.append((path, kind))
                seen.add(path)
    for path in candidates:
        if path.suffix != ".c":
            continue
        names = function_names(path)
        hit = any(re.search(r"\b" + re.escape(name) + r"\b", text) for name in names)
        if hit or path.name == "zlib_glue.c" and "zglue_" in text:
            found.append((path, "bundled-c-source"))
            seen.add(path)
            sibling = path.with_suffix(".h")
            if sibling.is_file() and sibling not in seen:
                found.append((sibling, "bundled-header"))
                seen.add(sibling)
    result = []
    for path, kind in found:
        relative = path.relative_to(repo).as_posix()
        result.append({"path": path, "relative": relative, "kind": kind,
                       "sha256": file_digest(path)})
    return sorted(result, key=lambda item: item["relative"])


def cargo_lock_for(source):
    current = Path(source).resolve().parent
    for directory in (current, *current.parents):
        lock = directory / "Cargo.lock"
        if lock.is_file():
            return lock
    return None


def crate_metadata(lock):
    licenses = {}
    names = {}
    base = lock.parent
    tomls = [base / "Cargo.toml"]
    tomls.extend(sorted(base.glob("vendor/*/Cargo.toml")))
    for path in tomls:
        try:
            text = path.read_text(encoding="utf-8")
        except OSError:
            continue
        name = re.search(r'(?m)^\s*name\s*=\s*"([^"]+)"', text)
        license_value = re.search(r'(?m)^\s*license\s*=\s*"([^"]+)"', text)
        if name:
            names.setdefault(name.group(1), str(path))
            if license_value:
                licenses.setdefault(name.group(1), license_value.group(1))
    return names, licenses


def cargo_crates(source):
    lock = cargo_lock_for(source)
    if lock is None:
        return [], None
    try:
        data = tomllib.loads(lock.read_text(encoding="utf-8"))
    except (OSError, tomllib.TOMLDecodeError):
        return [], str(lock)
    paths, licenses = crate_metadata(lock)
    crates = []
    for package in data.get("package", []):
        name = str(package.get("name", ""))
        version = str(package.get("version", ""))
        if not name or not version:
            continue
        crates.append({
            "name": name,
            "version": version,
            "checksum": str(package.get("checksum", "") or ""),
            "license": licenses.get(name) or package.get("license") or "",
            "path": paths.get(name, ""),
            "lock": str(lock),
        })
    return sorted(crates, key=lambda item: (item["name"], item["version"])), str(lock)


def link_command(report):
    return " ".join(report.get("command", []))


def property_list(**values):
    return [{"name": key.replace("_", ":"), "value": str(value)}
            for key, value in values.items() if value not in (None, "")]


def shared_component(soname, path, mapping):
    info = dpkg_package(path)
    found_license = package_license(info) if info else None
    component = {
        "type": "library",
        "bom-ref": "urn:ail:shared:" + soname,
        "name": info.get("package") or soname,
        "properties": property_list(ail_soname=soname, ail_path=path,
                                    ail_origin="readelf:DT_NEEDED",
                                    ail_package=info.get("package", ""),
                                    ail_architecture=info.get("architecture", "")),
    }
    if info.get("version"):
        component["version"] = info["version"]
    if info.get("package") and info.get("version"):
        purl = "pkg:deb/%s@%s" % (quote(info["package"]), quote(info["version"]))
        if info.get("architecture"):
            purl += "?arch=" + quote(info["architecture"])
        component["purl"] = purl
    if found_license:
        entry = license_value(found_license)
        if entry:
            component["licenses"] = [entry]
    return component


def bundled_component(item):
    return {
        "type": "file",
        "bom-ref": "urn:ail:file:%s:%s" % (item["sha256"][:16], item["relative"]),
        "name": item["relative"],
        "hashes": [{"alg": "SHA-256", "content": item["sha256"]}],
        "licenses": AIL_LICENSE,
        "properties": property_list(ail_origin="generated-c", ail_kind=item["kind"],
                                    ail_path=item["relative"]),
    }


def crate_component(item):
    component = {
        "type": "library",
        "bom-ref": "pkg:cargo/%s@%s" % (item["name"], item["version"]),
        "name": item["name"],
        "version": item["version"],
        "purl": "pkg:cargo/%s@%s" % (item["name"], item["version"]),
        "properties": property_list(ail_origin="Cargo.lock", ail_lock=item["lock"],
                                    ail_path=item["path"]),
    }
    if item["checksum"]:
        component["hashes"] = [{"alg": "SHA-256", "content": item["checksum"]}]
    value = license_value(item["license"])
    if value:
        component["licenses"] = [value]
    return component


def timestamp():
    epoch = os.environ.get("SOURCE_DATE_EPOCH")
    if epoch and epoch.isdigit():
        moment = datetime.fromtimestamp(int(epoch), timezone.utc)
    else:
        moment = datetime.now(timezone.utc)
    return moment.replace(microsecond=0).isoformat().replace("+00:00", "Z")


def build_bom(binary, source, debug_dir, repo=REPO):
    binary = Path(binary).resolve()
    source = Path(source).resolve()
    debug_dir = Path(debug_dir).resolve()
    repo = Path(repo).resolve()
    binary_hash = file_digest(binary) or ""
    report = native_report(debug_dir)
    if not report["compiler"]:
        report["compiler"] = os.environ.get("CC") or "cc"
    compiler = compiler_info(report["compiler"])
    ail = ail_info(repo)
    mapping = ldconfig_map()
    for name, path in ldd_map(binary).items():
        mapping.setdefault(name, path)
    components = []
    for soname in readelf_needed(binary):
        path = resolve_library(soname, binary, mapping)
        components.append(shared_component(soname, path, mapping))
    for item in bundled_sources(repo, debug_dir):
        components.append(bundled_component(item))
    crates, lock = cargo_crates(source)
    for item in crates:
        components.append(crate_component(item))
    root_ref = "urn:ail:binary:" + (binary_hash[:16] or binary.name)
    tool_version = ail["version"] if ail["commit"] == "unknown" else \
        "%s+%s" % (ail["version"], ail["commit"][:12])
    root = {
        "type": "application",
        "bom-ref": root_ref,
        "name": binary.name,
        "version": tool_version,
        "hashes": [{"alg": "SHA-256", "content": binary_hash}] if binary_hash else [],
        "properties": property_list(ail_path=str(binary), ail_source=str(source)),
    }
    bom = {
        "bomFormat": "CycloneDX",
        "specVersion": "1.5",
        "serialNumber": "urn:uuid:" + str(uuid.uuid5(
            uuid.NAMESPACE_URL, "https://github.com/J-KAMMA/ail-ci/sbom/" + binary_hash)),
        "version": 1,
        "metadata": {
            "timestamp": timestamp(),
            "tools": [
                {"vendor": "J-KAMMA", "name": "ailc", "version": ail["version"],
                 "hashes": []},
                {"vendor": compiler["vendor"], "name": compiler["name"],
                 "version": compiler["version"], "hashes": []},
            ],
            "component": root,
            "properties": property_list(
                ail_git_commit=ail["commit"],
                ail_source=str(source),
                ail_debug_dir=str(debug_dir),
                ail_link_line=link_command(report),
                ail_compiler_path=compiler["path"],
                ail_compiler_banner=compiler["banner"],
                ail_rust_lock=lock or "",
            ),
        },
        "components": sorted(components, key=lambda item: item["bom-ref"]),
        "dependencies": [{"ref": root_ref,
                          "dependsOn": [item["bom-ref"] for item in components]}] +
                         [{"ref": item["bom-ref"], "dependsOn": []}
                          for item in components],
    }
    return bom


def validate_bom(bom):
    errors = []
    if not isinstance(bom, dict):
        return ["the BOM is not a JSON object"]
    if bom.get("bomFormat") != "CycloneDX":
        errors.append("bomFormat must be CycloneDX")
    if bom.get("specVersion") != "1.5":
        errors.append("specVersion must be 1.5")
    if bom.get("version") != 1:
        errors.append("version must be 1")
    serial = bom.get("serialNumber", "")
    if not (isinstance(serial, str) and re.fullmatch(r"urn:uuid:[0-9a-fA-F-]{36}", serial)):
        errors.append("serialNumber must be a urn:uuid")
    metadata = bom.get("metadata")
    if not isinstance(metadata, dict):
        errors.append("metadata must be an object")
        metadata = {}
    if not metadata.get("timestamp"):
        errors.append("metadata.timestamp is required")
    tools = metadata.get("tools")
    if not isinstance(tools, list) or not tools:
        errors.append("metadata.tools must be a non-empty list")
    else:
        for index, tool in enumerate(tools):
            if not tool.get("name"):
                errors.append("metadata.tools[%d].name is required" % index)
            if not tool.get("version"):
                errors.append("metadata.tools[%d].version is required" % index)
    component = metadata.get("component")
    if not isinstance(component, dict):
        errors.append("metadata.component is required")
        component = {}
    for key in ("type", "name", "bom-ref"):
        if not component.get(key):
            errors.append("metadata.component.%s is required" % key)
    if component.get("type") and component["type"] not in COMPONENT_TYPES:
        errors.append("metadata.component.type is not a CycloneDX type")
    components = bom.get("components")
    if not isinstance(components, list):
        errors.append("components must be a list")
        components = []
    seen = set()
    for index, item in enumerate(components):
        where = "components[%d]" % index
        for key in ("type", "name", "bom-ref"):
            if not item.get(key):
                errors.append("%s.%s is required" % (where, key))
        if item.get("type") and item["type"] not in COMPONENT_TYPES:
            errors.append("%s.type is not a CycloneDX type" % where)
        ref = item.get("bom-ref")
        if ref in seen:
            errors.append("%s.bom-ref is not unique" % where)
        seen.add(ref)
        for hashed in item.get("hashes", []):
            if hashed.get("alg") != "SHA-256" or not re.fullmatch(r"[0-9a-f]{64}", hashed.get("content", "")):
                errors.append("%s has a malformed SHA-256 hash" % where)
    dependencies = bom.get("dependencies")
    if not isinstance(dependencies, list) or not dependencies:
        errors.append("dependencies must be a non-empty list")
        dependencies = []
    known = {component.get("bom-ref")} | seen
    for index, item in enumerate(dependencies):
        if not item.get("ref"):
            errors.append("dependencies[%d].ref is required" % index)
        elif item["ref"] not in known:
            errors.append("dependencies[%d].ref does not name a component" % index)
        for target in item.get("dependsOn", []):
            if target not in seen:
                errors.append("dependencies[%d] depends on an unknown bom-ref" % index)
    return errors


def bom_properties(component):
    return {item.get("name"): item.get("value") for item in component.get("properties", [])}


def bom_shared(bom):
    names = set()
    for component in bom.get("components", []):
        props = bom_properties(component)
        if props.get("ail:origin") == "readelf:DT_NEEDED" and props.get("ail:soname"):
            names.add(props["ail:soname"])
    return names


def bom_bundled(bom):
    names = set()
    for component in bom.get("components", []):
        props = bom_properties(component)
        if props.get("ail:origin") == "generated-c" and props.get("ail:path"):
            names.add(props["ail:path"])
    return names


def bom_crates(bom):
    names = set()
    for component in bom.get("components", []):
        props = bom_properties(component)
        if props.get("ail:origin") == "Cargo.lock":
            names.add((component.get("name", ""), component.get("version", "")))
    return names


def soname_for_flag(flag, expected):
    stem = flag[2:]
    pattern = re.compile(r"^lib" + re.escape(stem) + r"\.so(?:\..*)?$")
    for name in sorted(expected):
        if pattern.match(name):
            return name
    return None


def cross_check(bom, binary, source, debug_dir, repo=REPO):
    debug_dir = Path(debug_dir).resolve()
    expected_shared = set(readelf_needed(binary))
    actual_shared = bom_shared(bom)
    missing = sorted(expected_shared - actual_shared)
    extra = sorted(actual_shared - expected_shared)
    report = native_report(debug_dir)
    link_missing = []
    static_missing = []
    for flag in report["link_flags"]:
        if flag.startswith("-l"):
            soname = soname_for_flag(flag, expected_shared)
            if soname and soname not in actual_shared:
                link_missing.append(flag + " -> " + soname)
        elif flag.endswith(".a"):
            stem = Path(flag).name
            if stem.startswith("lib"):
                stem = stem[3:]
            if stem.endswith(".a"):
                stem = stem[:-2]
            crate_names = {name for name, _ in bom_crates(bom)}
            if stem and stem not in crate_names:
                static_missing.append(flag)
    expected_bundled = {item["relative"] for item in bundled_sources(repo, debug_dir)}
    actual_bundled = bom_bundled(bom)
    bundled_missing = sorted(expected_bundled - actual_bundled)
    bundled_extra = sorted(actual_bundled - expected_bundled)
    expected_crates, _ = cargo_crates(source)
    expected_names = {(item["name"], item["version"]) for item in expected_crates}
    actual_crates = bom_crates(bom)
    crate_missing = sorted(expected_names - actual_crates)
    crate_extra = sorted(actual_crates - expected_names)
    return {
        "missing": missing,
        "extra": extra,
        "link_missing": link_missing,
        "link_static_missing": static_missing,
        "bundled_missing": bundled_missing,
        "bundled_extra": bundled_extra,
        "crate_missing": [list(item) for item in crate_missing],
        "crate_extra": [list(item) for item in crate_extra],
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description="Write a CycloneDX 1.5 SBOM for an AIL binary.")
    parser.add_argument("binary")
    parser.add_argument("--source", required=True)
    parser.add_argument("--debug-dir", required=True)
    parser.add_argument("-o", "--output", required=True)
    parser.add_argument("--repo", default=str(REPO))
    parser.add_argument("--check", action="store_true",
                        help="also cross-check the BOM against readelf, the link line and the C")
    args = parser.parse_args(argv)
    binary = Path(args.binary)
    if not binary.is_file():
        print("sbom: no such binary: " + str(binary), file=sys.stderr)
        return 2
    if not Path(args.source).is_file():
        print("sbom: no such source: " + args.source, file=sys.stderr)
        return 2
    if not Path(args.debug_dir).is_dir():
        print("sbom: no such debug directory: " + args.debug_dir, file=sys.stderr)
        return 2
    bom = build_bom(binary, args.source, args.debug_dir, args.repo)
    problems = validate_bom(bom)
    if problems:
        for problem in problems:
            print("sbom: invalid CycloneDX: " + problem, file=sys.stderr)
        return 2
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(bom, indent=2, sort_keys=False) + "\n", encoding="utf-8")
    if args.check:
        result = cross_check(bom, binary, args.source, args.debug_dir, args.repo)
        print(json.dumps(result, sort_keys=True))
        return 1 if any(result.values()) else 0
    return 0


if __name__ == "__main__":
    sys.exit(main())

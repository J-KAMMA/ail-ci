#!/usr/bin/env python3
"""Measure the linker/gcc hardening properties of ELF executables with readelf only.

    python3 tools/hardening_check.py BINARY... [--pretty]

One JSON line per binary:

    {"path": "...", "pie": true, "nx": true, "relro": "full", "canary": true,
     "fortify": 5, "stripped": false, "size": 146848}

Properties:
  pie       ELF type DYN and PIE in DT_FLAGS_1
  nx        the GNU_STACK segment exists and is not executable
  relro     "full"   a GNU_RELRO segment and BIND_NOW in DT_FLAGS/DT_FLAGS_1
            "partial" a GNU_RELRO segment only
            "none"    no GNU_RELRO segment
  canary    the dynamic symbol __stack_chk_fail is present
  fortify   the number of distinct dynamic __*_chk symbols (__printf_chk, __memcpy_chk, ...)
  stripped  no .symtab section
  size      file size in bytes

No checksec, no third-party package: every answer comes from `readelf -h/-l/-d/-s`.
"""
import json
import os
import re
import subprocess
import sys

CHK = re.compile(r"^__[A-Za-z0-9_]+_chk$")


def readelf(flag, path):
    got = subprocess.run(["readelf", flag, "-W", path], capture_output=True, text=True)
    if got.returncode != 0:
        raise RuntimeError((got.stderr or got.stdout).strip() or "readelf failed")
    return got.stdout


def elf_type(header):
    match = re.search(r"^\s*Type:\s+(\S+)", header, re.M)
    return match.group(1) if match else "?"


def pie_flag(dynamic):
    for line in dynamic.splitlines():
        if "(FLAGS_1)" in line:
            return "PIE" in line.split("Flags:")[-1].split()
    return False


def bind_now(dynamic):
    for line in dynamic.splitlines():
        if "(FLAGS)" in line and "BIND_NOW" in line:
            return True
        if "(FLAGS_1)" in line and "NOW" in line.split("Flags:")[-1].split():
            return True
    return False


def segments(program_headers):
    found = {}
    for line in program_headers.splitlines():
        parts = line.split()
        if parts and parts[0] in ("GNU_STACK", "GNU_RELRO"):
            found[parts[0]] = parts[1:]
    return found


def symbol_names(text):
    names = set()
    for line in text.splitlines():
        parts = line.split()
        if len(parts) >= 8 and parts[0].rstrip(":").isdigit():
            names.add(parts[7].split("@")[0])
    return names


def measure(path):
    header = readelf("-h", path)
    program = readelf("-l", path)
    dynamic = readelf("-d", path)
    dynamic_symbols = readelf("--dyn-syms", path)
    sections = readelf("-S", path)
    segs = segments(program)
    stack = segs.get("GNU_STACK")
    return {
        "path": path,
        "pie": elf_type(header) == "DYN" and pie_flag(dynamic),
        "nx": bool(stack) and "E" not in stack[5],
        "relro": "full" if "GNU_RELRO" in segs and bind_now(dynamic)
                 else "partial" if "GNU_RELRO" in segs else "none",
        "canary": "__stack_chk_fail" in symbol_names(dynamic_symbols),
        "fortify": len({n for n in symbol_names(dynamic_symbols) if CHK.match(n)}),
        "stripped": not any(re.match(r"^\s*\[\s*\d+\]\s+\.symtab\s", line) for line in sections.splitlines()),
        "size": os.path.getsize(path),
    }


def main(argv):
    paths = [a for a in argv[1:] if not a.startswith("-")]
    if not paths:
        print("usage: hardening_check.py BINARY...", file=sys.stderr)
        return 2
    if subprocess.run(["sh", "-c", "command -v readelf"], capture_output=True).returncode != 0:
        print("hardening_check: readelf not found", file=sys.stderr)
        return 2
    failed = 0
    for path in paths:
        try:
            row = measure(path)
        except (KeyError, OSError, RuntimeError) as error:
            row = {"path": path, "error": str(error)}
            failed += 1
        print(json.dumps(row))
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))

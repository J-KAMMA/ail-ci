#!/usr/bin/env python3
"""Measure whether the same source gives a byte-identical executable in two build setups.

    python3 tools/repro_check.py [-j 2] [--filter SUBSTR] [--json OUT]

The corpus is the 10 ``lab/compare/src/*/main.py`` programs, every ``lab/stdlib/*/*.py``
program and every ``examples/**/*.py`` program.  Each one is built once in

    A: /tmp/a/x/<slug>                 TMPDIR=/tmp/a/tmp     SOURCE_DATE_EPOCH=1000000000
    B: /tmp/b/longer/path/x/<slug>     TMPDIR=/tmp/b/tmp     SOURCE_DATE_EPOCH=2000000000

with different PYTHONHASHSEED values, an isolated HOME and an environment containing only
PATH, LANG and LC_ALL.  AIL_NO_CACHE=1 keeps a previous build out of the comparison.

Both the executable and ``program.c`` (from --debug-dir) are compared by sha256.  When the C
differs the first differing line is printed; when only the executable differs the first
differing ELF section is printed.  No compiler file is edited: this tool is measure-only.

All builds run under a 1.5 GB address-space limit, at most ``--jobs`` at a time.  Exit status is
0 when every program that built in both setups is identical, 1 otherwise, 2 when at least one
program produced different stdout/exit status between its two builds (never expected).
"""
import argparse
import concurrent.futures
import hashlib
import json
import os
import re
import resource
import shutil
import struct
import subprocess
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
COMPILER = REPO / "AIL_CURRENT" / "ail_chatgpt.py"
LIMIT = 1500000 * 1024

ROOT_A = Path("/tmp/a/x")
ROOT_B = Path("/tmp/b/longer/path/x")
TMP_A = Path("/tmp/a/tmp")
TMP_B = Path("/tmp/b/tmp")
HOME_A = Path("/tmp/a/home")
HOME_B = Path("/tmp/b/home")
EPOCH_A = "1000000000"
EPOCH_B = "2000000000"
SEED_A = "0"
SEED_B = "1"


def programs():
    """(display name, source path) for the whole corpus."""
    items = [("compare/" + path.parent.name, path)
             for path in sorted((REPO / "lab" / "compare" / "src").glob("*/main.py"))]
    items += [("stdlib/" + path.relative_to(REPO / "lab" / "stdlib").as_posix(), path)
              for path in sorted((REPO / "lab" / "stdlib").glob("*/*.py"))]
    items += [("examples/" + path.relative_to(REPO / "examples").as_posix(), path)
              for path in sorted((REPO / "examples").rglob("*.py"))]
    return items


def _limit_memory():
    resource.setrlimit(resource.RLIMIT_AS, (LIMIT, LIMIT))


def _slug(name):
    return re.sub(r"[^A-Za-z0-9_.-]+", "_", name)


def _environment(tmp, home, epoch, seed):
    env = {
        "PATH": os.environ.get("PATH", "/usr/bin:/bin"),
        "LANG": os.environ.get("LANG", "C.UTF-8"),
        "LC_ALL": os.environ.get("LC_ALL", "C.UTF-8"),
        "HOME": str(home),
        "TMPDIR": str(tmp),
        "SOURCE_DATE_EPOCH": epoch,
        "AIL_NO_CACHE": "1",
        "PYTHONUTF8": "1",
        "PYTHONDONTWRITEBYTECODE": "1",
        "PYTHONHASHSEED": seed,
    }
    if os.environ.get("PIPE_CC"):
        env["PIPE_CC"] = os.environ["PIPE_CC"]
    return env


def build(source, work, setup):
    tmp, home, epoch, seed = setup
    work.mkdir(parents=True, exist_ok=True)
    local = work / source.name
    shutil.copyfile(source, local)
    out = work / "prog"
    debug = work / "dbg"
    try:
        done = subprocess.run(
            [sys.executable, "-B", str(COMPILER), "compile", str(local), "-o", str(out),
             "--debug-dir", str(debug)],
            cwd=str(work), env=_environment(tmp, home, epoch, seed),
            capture_output=True, text=True, encoding="utf-8", errors="replace",
            timeout=900, preexec_fn=_limit_memory)
    except subprocess.TimeoutExpired:
        return {"returncode": "timeout", "stderr": "", "binary": None, "program_c": None}
    program_c = debug / "program.c"
    return {
        "returncode": done.returncode,
        "stderr": done.stderr,
        "binary": out.read_bytes() if out.is_file() else None,
        "program_c": program_c.read_bytes() if program_c.is_file() else None,
    }


def first_difference(left, right):
    a = left.decode("utf-8", "replace").splitlines()
    b = right.decode("utf-8", "replace").splitlines()
    for index, (x, y) in enumerate(zip(a, b), 1):
        if x != y:
            return index, x, y
    if len(a) != len(b):
        index = min(len(a), len(b)) + 1
        return (index, a[index - 1] if index <= len(a) else "<eof>",
                b[index - 1] if index <= len(b) else "<eof>")
    return None


TIME = re.compile(r"\b\d{1,2}:\d{2}:\d{2}\b|\b\d{4}-\d{2}-\d{2}\b|\b20\d\d\b.*\b(GMT|UTC)\b")
TEMP = re.compile(r"\b(tmp|temp)[a-z0-9_]{4,}\b|[A-Za-z0-9_]+\.tmp\b")
ARRAY = re.compile(r"\{\s*([0-9][0-9,\s]*)\}")
PATH = re.compile(r"/(?:[^/\s\x00]+/)+[^/\s\x00]+")


def decoded_arrays(line):
    """The text of integer arrays on a C line, e.g. a `uint16_t d[]` string literal.

    The source path is stored as one decimal code unit per character, so the literal
    `/tmp/a/x` appears as `47, 116, 109, 112, ...` and is invisible to a text search.
    """
    parts = []
    for match in ARRAY.finditer(line):
        numbers = [int(token) for token in re.findall(r"\d+", match.group(1))]
        if not numbers or max(numbers) > 0x10FFFF:
            continue
        text = "".join(chr(number) for number in numbers if number)
        if text:
            parts.append(text)
    return "\n".join(parts)


def classify_c(left, right, line_left, line_right):
    if sorted(left.decode("utf-8", "replace").splitlines()) == \
            sorted(right.decode("utf-8", "replace").splitlines()):
        return "hash order"
    decoded = decoded_arrays(line_left) + "\n" + decoded_arrays(line_right)
    hay = line_left + "\n" + line_right
    if "/tmp/" in hay or re.search(r"[A-Za-z]:\\\\", hay) or \
            "/tmp/" in decoded or PATH.search(decoded):
        return "absolute path"
    if TIME.search(hay):
        return "time"
    if TEMP.search(hay):
        return "temporary name"
    if re.sub(r"\d+", "#", line_left) == re.sub(r"\d+", "#", line_right):
        return "counter"
    return "other"


def elf_sections(data):
    """[(name, offset, size, bytes)] for an ELF file, or None when it is not ELF."""
    if len(data) < 0x34 or data[:4] != b"\x7fELF":
        return None
    try:
        cls, encoding = data[4], data[5]
        endian = "<" if encoding == 1 else ">"
        if cls == 2:
            shoff = struct.unpack_from(endian + "Q", data, 0x28)[0]
            shentsize, shnum, shstrndx = struct.unpack_from(endian + "HHH", data, 0x3A)
            fmt = endian + "IIQQQQIIQQ"
        elif cls == 1:
            shoff = struct.unpack_from(endian + "I", data, 0x20)[0]
            shentsize, shnum, shstrndx = struct.unpack_from(endian + "HHH", data, 0x2E)
            fmt = endian + "IIIIIIIIII"
        else:
            return None
        if not shoff or not shnum or shoff + shnum * shentsize > len(data):
            return None
        rows = []
        for index in range(shnum):
            fields = struct.unpack_from(fmt, data, shoff + index * shentsize)
            name, kind = fields[0], fields[1]
            offset, size = fields[4], fields[5]
            rows.append(((name, kind), offset, size))
        names = b""
        if shstrndx < len(rows):
            _, noff, nsize = rows[shstrndx]
            names = data[noff:noff + nsize]
        sections = []
        for (name, kind), offset, size in rows:
            end = names.find(b"\0", name)
            text = names[name:end if end >= 0 else len(names)].decode("utf-8", "replace")
            if kind == 8 or offset + size > len(data):
                sections.append((text or "<unnamed>", offset, size, b""))
            else:
                sections.append((text or "<unnamed>", offset, size, data[offset:offset + size]))
        return sections
    except (struct.error, IndexError, ValueError):
        return None


def first_elf_difference(left, right):
    """(section, first_byte_offset) for the first differing ELF section, or None."""
    sections_a = elf_sections(left)
    sections_b = elf_sections(right)
    if sections_a is None or sections_b is None:
        return None
    names_a = [row[0] for row in sections_a]
    names_b = [row[0] for row in sections_b]
    for name in names_a + [n for n in names_b if n not in names_a]:
        a = next((row for row in sections_a if row[0] == name), None)
        b = next((row for row in sections_b if row[0] == name), None)
        if a is None or b is None:
            return name, 0
        if a[3] != b[3]:
            offset = 0
            for index, (x, y) in enumerate(zip(a[3], b[3])):
                if x != y:
                    offset = index
                    break
            else:
                offset = min(len(a[3]), len(b[3]))
            return name, offset
    return None


def run_binary(result, work):
    if result["binary"] is None:
        return None
    try:
        done = subprocess.run([str(work / "prog")], cwd=str(work),
                              env={"PATH": os.environ.get("PATH", "/usr/bin:/bin"),
                                   "PYTHONUTF8": "1"},
                              input=b"", capture_output=True, timeout=120,
                              preexec_fn=_limit_memory)
    except (subprocess.TimeoutExpired, OSError):
        return None
    return done.returncode, done.stdout


def one(name, source, root_a, root_b):
    slug = _slug(name)
    work_a = root_a / slug
    work_b = root_b / slug
    setups = [(TMP_A, HOME_A, EPOCH_A, SEED_A), (TMP_B, HOME_B, EPOCH_B, SEED_B)]
    try:
        a = build(source, work_a, setups[0])
        b = build(source, work_b, setups[1])
    except Exception as error:  # a crash is a finding, not a reason to lose the run
        return {"program": name, "status": "error", "error": repr(error)}

    record = {"program": name, "source": str(source.relative_to(REPO)),
              "rc_a": a["returncode"], "rc_b": b["returncode"],
              "c_identical": None, "binary_identical": None, "status": None,
              "class": None, "first_c_line": None, "c_a": None, "c_b": None,
              "elf_section": None, "elf_offset": None, "one_sided": False}
    built_a = a["binary"] is not None
    built_b = b["binary"] is not None
    if not built_a and not built_b:
        record["status"] = "refused"
        record["stderr_a"] = (a["stderr"] or "")[-500:]
        record["stderr_b"] = (b["stderr"] or "")[-500:]
        return record
    if not built_a or not built_b:
        # One setup produced an executable and the other did not.  That is exactly the
        # nondeterministic failure this tool looks for, never a two-sided refusal.
        record["status"] = "diff"
        record["one_sided"] = True
        record["class"] = "one-sided build failure"
        record["built_a"] = built_a
        record["built_b"] = built_b
        record["stderr_a"] = (a["stderr"] or "")[-500:]
        record["stderr_b"] = (b["stderr"] or "")[-500:]
        return record

    c_same = a["program_c"] == b["program_c"]
    bin_same = hashlib.sha256(a["binary"]).digest() == hashlib.sha256(b["binary"]).digest()
    record["c_identical"] = c_same
    record["binary_identical"] = bin_same
    record["sha_a"] = hashlib.sha256(a["binary"]).hexdigest()
    record["sha_b"] = hashlib.sha256(b["binary"]).hexdigest()

    if not c_same and a["program_c"] is not None and b["program_c"] is not None:
        found = first_difference(a["program_c"], b["program_c"])
        if found:
            line, left, right = found
            record["first_c_line"] = line
            record["c_a"] = left.strip()[:200]
            record["c_b"] = right.strip()[:200]
            record["class"] = classify_c(a["program_c"], b["program_c"], left, right)
    if not bin_same:
        found = first_elf_difference(a["binary"], b["binary"])
        if found:
            record["elf_section"], record["elf_offset"] = found

    record["status"] = "identical" if (c_same and bin_same) else "diff"

    ran_a = run_binary(a, work_a)
    ran_b = run_binary(b, work_b)
    if ran_a is not None and ran_b is not None and ran_a != ran_b:
        record["wrong_output"] = True
    return record


def summarize(results):
    total = len(results)
    identical = sum(1 for r in results if r["status"] == "identical")
    diff = [r for r in results if r["status"] == "diff"]
    refused = [r for r in results if r["status"] == "refused"]
    errors = [r for r in results if r["status"] == "error"]
    c_diff = [r for r in diff if r.get("c_identical") is False]
    bin_only = [r for r in diff if r.get("c_identical") is True]
    classes = {}
    one_sided = [r for r in diff if r.get("one_sided")]
    for row in c_diff:
        key = row.get("class") or "other"
        classes[key] = classes.get(key, 0) + 1
    print()
    print("programs: %d" % total)
    print("identical: %d" % identical)
    print("different: %d  (C differs: %d, only executable differs: %d, "
          "one-sided build failure: %d)" %
          (len(diff), len(c_diff), len(bin_only), len(one_sided)))
    print("not built in both setups: %d" % len(refused))
    if errors:
        print("errors: %d" % len(errors))
    for key in sorted(classes):
        row = next(r for r in c_diff if (r.get("class") or "other") == key)
        print("  C class %-14s %d  e.g. %s line %s" %
              (key, classes[key], row["program"], row.get("first_c_line")))
    for row in bin_only:
        print("  ELF %s section %s at +%s" %
              (row["program"], row.get("elf_section"), row.get("elf_offset")))
    for row in one_sided:
        print("  build failed only in setup %s: %s" %
              ("B" if row.get("built_a") else "A", row["program"]))
    wrong = [r for r in results if r.get("wrong_output")]
    if wrong:
        print("WRONG OUTPUT: " + ", ".join(r["program"] for r in wrong))
    return 2 if wrong else 0 if not diff and not errors else 1


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--json", help="write the full result as JSON here")
    parser.add_argument("-j", "--jobs", type=int, default=2)
    parser.add_argument("--filter", default=None, help="only programs whose name contains this")
    args = parser.parse_args()

    items = programs()
    if args.filter:
        items = [(name, path) for name, path in items if args.filter in name]

    for root in (ROOT_A, ROOT_B, TMP_A, TMP_B, HOME_A, HOME_B):
        if root.exists():
            shutil.rmtree(root)
        root.mkdir(parents=True, exist_ok=True)

    results = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=max(1, args.jobs)) as pool:
        futures = {pool.submit(one, name, source, ROOT_A, ROOT_B): name
                   for name, source in items}
        for future in concurrent.futures.as_completed(futures):
            name = futures[future]
            try:
                record = future.result()
            except Exception as error:
                record = {"program": name, "status": "error", "error": repr(error)}
            results.append(record)
            verdict = {"identical": "identical", "diff": "DIFF", "refused": "not built",
                       "error": "ERROR"}[record["status"]]
            print("%-60s %s" % (name, verdict), flush=True)
            if args.json:  # incremental: a run stopped by the clock still leaves its rows
                Path(args.json).write_text(
                    json.dumps(sorted(results, key=lambda r: r["program"]), indent=1) + "\n")

    results.sort(key=lambda r: r["program"])
    if args.json:
        Path(args.json).write_text(json.dumps(results, indent=1) + "\n")
    status = summarize(results)
    for row in results:
        if row["status"] == "diff":
            if row.get("one_sided"):
                print("%s: built only in setup %s\n  A: %s\n  B: %s" %
                      (row["program"], "A" if row.get("built_a") else "B",
                       (row.get("stderr_a") or "").strip()[-300:],
                       (row.get("stderr_b") or "").strip()[-300:]))
            if row.get("c_identical") is False:
                print("%s: C differs at line %s\n  A: %s\n  B: %s" %
                      (row["program"], row.get("first_c_line"), row.get("c_a"), row.get("c_b")))
            if row.get("binary_identical") is False:
                print("%s: executable differs; first ELF section %s at +%s" %
                      (row["program"], row.get("elf_section"), row.get("elf_offset")))
    return status


if __name__ == "__main__":
    sys.exit(main())

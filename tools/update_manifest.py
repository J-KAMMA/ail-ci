"""Refresh AIL_CURRENT/MANIFEST.json pins for git-tracked files whose bytes changed.

Run after editing pinned files:  python3 tools/update_manifest.py [--check]
--check exits 1 (and changes nothing) when any pin is stale; CI and quick_test use it.
"""
import hashlib, json, re, subprocess, sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
SRC = REPO / "AIL_CURRENT"

def main():
    check = "--check" in sys.argv[1:]
    path = SRC / "MANIFEST.json"
    raw = path.read_bytes()
    manifest = json.loads(raw)
    tracked = subprocess.run(["git", "ls-files", "-z", "AIL_CURRENT"], cwd=REPO, capture_output=True,
                             check=True).stdout.decode().split("\0")
    names = {name[len("AIL_CURRENT/"):] for name in tracked if name} - {"MANIFEST.json"}
    stale = {}
    for name in sorted(names & manifest["sha256"].keys()):
        digest = hashlib.sha256((SRC / name).read_bytes()).hexdigest()
        if manifest["sha256"][name] != digest:
            stale[name] = digest
    # A file named in sdk_files must have a pin: ail_check fails with "hash mismatch" otherwise
    # (a MANIFEST merge once dropped the pins of a new module while keeping its sdk_files entry).
    # Compiler sources and the test modules ail_check runs must be pinned too (a merge resolution
    # once dropped the pins of four new ir/ modules that were in neither list).
    registered = set(re.findall(r"'(test_[a-z0-9_]+)'", (SRC / "ail_check.py").read_text(encoding="utf-8")))
    must = set(manifest.get("sdk_files", []))
    must |= {n for n in names if n.endswith(".py") and (n.startswith("python/pkg-v12/") or n[:-3] in registered)}
    unpinned = sorted(n for n in must if n in names and n not in manifest["sha256"])
    for name in unpinned:
        digest = hashlib.sha256((SRC / name).read_bytes()).hexdigest()
        print(("unpinned " if check else "pinned ") + name)
        if not check:
            manifest["sha256"][name] = digest
            manifest["files"][name] = digest
    for name, digest in stale.items():
        print(("stale " if check else "updated ") + name)
        if not check:
            manifest["sha256"][name] = digest
            if name in manifest["files"]:
                manifest["files"][name] = digest
    if (stale or unpinned) and not check:
        path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + ("\n" if raw.endswith(b"\n") else ""),
                        encoding="utf-8")
    return 1 if check and (stale or unpinned) else 0

if __name__ == "__main__":
    raise SystemExit(main())

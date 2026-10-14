"""Refresh AIL_CURRENT/MANIFEST.json pins for git-tracked files whose bytes changed.

Run after editing pinned files:  python3 tools/update_manifest.py [--check]
--check exits 1 (and changes nothing) when any pin is stale; CI and quick_test use it.
"""
import hashlib, json, subprocess, sys
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
    for name, digest in stale.items():
        print(("stale " if check else "updated ") + name)
        if not check:
            manifest["sha256"][name] = digest
            if name in manifest["files"]:
                manifest["files"][name] = digest
    if stale and not check:
        path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + ("\n" if raw.endswith(b"\n") else ""),
                        encoding="utf-8")
    return 1 if check and stale else 0

if __name__ == "__main__":
    raise SystemExit(main())

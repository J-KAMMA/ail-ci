"""Refresh the SHA-256 pins of git-tracked files whose bytes changed.

Run after editing pinned files:  python3 tools/update_manifest.py [--check]
--check exits 1 (and changes nothing) when any pin is stale or the layout is not canonical; CI and
quick_test use it.

The pins live one per line in AIL_CURRENT/manifest.d/<xx>.txt (see AIL_CURRENT/ail_manifest.py), not in
MANIFEST.json, so pull requests that touch different files edit different lines and merge cleanly.
Resolving a merge: take either side of any manifest.d conflict (or leave the markers in), then run
this script without --check; it tolerates conflict markers in the shards and recomputes every pin from
the files, so the result is the same whichever side was kept.  A legacy MANIFEST.json that still holds
the sha256/files/sdk_files maps is converted to the shard layout on the first write.
"""
import hashlib, json, re, subprocess, sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
SRC = REPO / "AIL_CURRENT"
sys.path.insert(0, str(SRC))
import ail_manifest  # noqa: E402

LEGACY_KEYS = ("sha256", "files", "sdk_files")


def sha(name):
    return hashlib.sha256((SRC / name).read_bytes()).hexdigest()


def main():
    check = "--check" in sys.argv[1:]
    path = SRC / "MANIFEST.json"
    raw = path.read_bytes()
    static = json.loads(raw)
    legacy = [key for key in LEGACY_KEYS if key in static]
    problems = []
    try:
        pins = ail_manifest.read_pins(SRC, repair=not check)
    except ValueError as error:
        print(f"manifest layout: {error}")
        return 1
    if legacy:
        # Pre-shard layout: fold its three maps in (a shard line, if both exist, is newer and wins).
        folded = {}
        for name, digest in static.get("sha256", {}).items():
            folded[name] = [digest, ""]
        for name in static.get("files", {}):
            folded.setdefault(name, [static.get("sha256", {}).get(name, ""), ""])[1] += "f"
        for name in dict.fromkeys(static.get("sdk_files", [])):
            folded.setdefault(name, ["", ""])[1] += "s"
        for name, (digest, flags) in folded.items():
            if name not in pins:
                pins[name] = (digest, flags)
        problems.append("legacy MANIFEST.json holds the pins (run tools/update_manifest.py to move them to manifest.d)")
    tracked = subprocess.run(["git", "ls-files", "-z", "AIL_CURRENT"], cwd=REPO, capture_output=True,
                             check=True).stdout.decode().split("\0")
    names = {name[len("AIL_CURRENT/"):] for name in tracked if name} - {"MANIFEST.json"}
    names = {n for n in names if not n.startswith(ail_manifest.SHARD_DIR + "/")}
    stale = {}
    for name in sorted(names & pins.keys()):
        digest = sha(name)
        if pins[name][0] and pins[name][0] != digest:
            stale[name] = digest
    # A file named in sdk_files must have a pin: ail_check fails with "hash mismatch" otherwise
    # (a MANIFEST merge once dropped the pins of a new module while keeping its sdk_files entry).
    # Compiler sources and the test modules ail_check runs must be pinned too (a merge resolution
    # once dropped the pins of four new ir/ modules that were in neither list).  A test module is
    # registered either in ail_check.py's LISTED_MODULES or by a tests.d/<module>.txt file; both the
    # modules and the registration files are pinned.
    registered = set(re.findall(r"'(test_[a-z0-9_]+)'", (SRC / "ail_check.py").read_text(encoding="utf-8")))
    registered |= {n[len("tests.d/"):-len(".txt")] for n in names if n.startswith("tests.d/") and n.endswith(".txt")}
    must = {name for name, (_, flags) in pins.items() if "s" in flags}
    must |= {n for n in names if n.startswith("tests.d/") and n.endswith(".txt")}
    must |= {n for n in names if n.endswith(".py") and (n.startswith("python/pkg-v12/") or n[:-3] in registered)}
    unpinned = sorted(n for n in must if n in names and not pins.get(n, ("",))[0])
    for name in unpinned:
        print(("unpinned " if check else "pinned ") + name)
        pins[name] = (sha(name), pins.get(name, ("", ""))[1])
    for name, digest in stale.items():
        print(("stale " if check else "updated ") + name)
        pins[name] = (digest, pins[name][1])
    # An sdk_files entry with no digest and no tracked file cannot be pinned: ail_check would refuse it.
    unpinnable = sorted(n for n, (digest, _) in pins.items() if not digest)
    for name in unpinnable:
        print(f"no file to pin: {name}")
        del pins[name]
    texts = ail_manifest.render(pins)
    directory = SRC / ail_manifest.SHARD_DIR
    on_disk = {p.name: p.read_bytes() for p in directory.glob("*") if p.is_file()} if directory.is_dir() else {}
    if not (stale or unpinned or unpinnable) and on_disk != {file: text.encode("utf-8") for file, text in texts.items()}:
        problems.append("manifest.d is not in canonical form (sorted, one pin per line, one shard per name bucket)")
    for problem in problems:
        print(problem)
    changed = bool(stale or unpinned or unpinnable or problems)
    if changed and not check:
        ail_manifest.write_pins(SRC, pins)
        if legacy:
            path.write_text(json.dumps({k: v for k, v in static.items() if k not in LEGACY_KEYS},
                                       ensure_ascii=False, indent=2) + ("\n" if raw.endswith(b"\n") else ""),
                            encoding="utf-8")
    return 1 if check and changed else 0

if __name__ == "__main__":
    raise SystemExit(main())

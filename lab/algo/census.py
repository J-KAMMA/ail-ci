"""Lint the comparison, corpus and vibe programs and print the per-rule census.

    python3 lab/algo/census.py            # markdown tables on stdout
    python3 lab/algo/census.py --json     # one JSON object with every set and hit

The required sets are the ten lab/compare/src/*/main.py programs, the first 50 corpus/gdev programs
(the ones lab/rundiff uses) and the lab/vibe programs present.  The larger corpus sets are also
shown so a hit outside the required 50 is not hidden.
"""
import argparse
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
sys.path.insert(0, str(REPO / "packaging"))
from ail_lang import perflint  # noqa: E402


def files(pattern):
    return sorted(REPO.glob(pattern))


SETS = (
    ("compare (10)", files("lab/compare/src/*/main.py")),
    ("corpus (50, rundiff1)", files("corpus/gdev/*.py")[:50]),
    ("corpus gdev (all)", files("corpus/gdev/*.py")),
    ("lab/corpus (all)", files("lab/corpus/programs/*/*.py")),
    ("lab/vibe (all .py)", files("lab/vibe/programs/*/*.py")),
)


def census(files_):
    rows = []
    for path in files_:
        try:
            hits = perflint.lint_file(path)
        except (OSError, UnicodeError, SyntaxError) as error:
            rows.append({"file": str(path.relative_to(REPO)), "error": str(error)})
            continue
        for hit in hits:
            one = dict(hit)
            one["file"] = str((REPO / hit["file"]).resolve().relative_to(REPO))
            rows.append(one)
    return rows


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    report = []
    for label, selected in SETS:
        rows = census(selected)
        hits = [one for one in rows if "rule" in one]
        counts = {rule: sum(1 for one in hits if one["rule"] == rule) for rule in sorted(perflint.RULES)}
        report.append({"set": label, "files": len(selected), "hits": len(hits), "counts": counts,
                       "rows": hits, "errors": [one for one in rows if "error" in one]})
    if args.json:
        print(json.dumps(report, indent=1))
        return 0
    for one in report:
        print("### %s\n" % one["set"])
        print("| files | hits | %s |" % " | ".join(sorted(perflint.RULES)))
        print("| --- | --- | %s |" % " | ".join("---" for _ in perflint.RULES))
        print("| %d | %d | %s |\n" % (one["files"], one["hits"],
                                      " | ".join(str(one["counts"][rule]) for rule in sorted(perflint.RULES))))
        for hit in one["rows"]:
            print("- `%s:%d:%d` %s: %s" % (hit["file"], hit["line"], hit["col"], hit["rule"], hit["message"]))
        for error in one["errors"]:
            print("- could not parse `%s`: %s" % (error["file"], error["error"]))
        print()
    return 0


if __name__ == "__main__":
    sys.exit(main())

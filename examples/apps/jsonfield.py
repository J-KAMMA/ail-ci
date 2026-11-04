"""Print one JSON field of every JSON Lines object on standard input."""

import json
import sys


def main() -> None:
    key = sys.argv[1]
    for line in sys.stdin:
        stripped = line.strip()
        if not stripped:
            continue
        obj = json.loads(stripped)
        if key in obj:
            print(json.dumps(obj[key]))
        else:
            print("-")


main()

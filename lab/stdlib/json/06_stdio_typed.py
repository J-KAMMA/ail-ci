import json
import sys


def main() -> int:
    data: list[int] = json.load(sys.stdin)
    total = 0
    for value in data:
        total += value
    json.dump(data, sys.stdout, indent=2)
    print()
    json.dump({"count": len(data), "total": total}, sys.stdout, sort_keys=True)
    print()
    return 0


main()

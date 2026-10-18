import json
import sys


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")
    records: list[dict] = json.load(sys.stdin)

    for name in sorted(r["name"] for r in records if r["active"]):
        print(name)

    scores = [r["score"] for r in records]
    avg = sum(scores) / len(scores) if scores else 0.0
    print(f"{avg:.2f}")


if __name__ == "__main__":
    main()

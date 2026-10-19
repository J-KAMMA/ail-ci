import json
import sys


def main() -> None:
    data = sys.stdin.read()
    records: list[dict] = json.loads(data)

    active_names: list[str] = sorted(
        str(rec["name"]) for rec in records if rec.get("active") is True
    )

    scores: list[float] = [float(rec["score"]) for rec in records]
    average: float = sum(scores) / len(scores) if scores else 0.0

    for name in active_names:
        print(name)
    print(f"{average:.2f}")


if __name__ == "__main__":
    main()

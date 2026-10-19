import sys


def main() -> None:
    data: list[str] = sys.stdin.read().split()
    if not data:
        return
    n: int = int(data[0])
    records: list[tuple[str, float, str]] = []
    idx: int = 1
    for _ in range(n):
        name: str = data[idx]
        # grade = data[idx + 1]  (not needed for ranking)
        # age = data[idx + 2]    (not needed for ranking)
        raw_score: str = data[idx + 3]
        idx += 4
        records.append((name, float(raw_score), raw_score))

    records.sort(key=lambda r: (-r[1], r[0]))

    prev_value: float | None = None
    rank: int = 0
    for position, (name, value, raw) in enumerate(records, start=1):
        if prev_value is None or value != prev_value:
            rank = position
            prev_value = value
        print(f"{rank} {name} {raw}")


if __name__ == "__main__":
    main()

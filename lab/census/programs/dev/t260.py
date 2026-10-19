import sys
from typing import Iterable


def classify(x: int, y: int) -> str:
    """Return the group label for a point: I, II, III, IV, or axis."""
    if x == 0 or y == 0:
        return "axis"
    if x > 0 and y > 0:
        return "I"
    if x < 0 and y > 0:
        return "II"
    if x < 0 and y < 0:
        return "III"
    return "IV"


def read_points(tokens: Iterable[str]) -> list[tuple[int, int]]:
    it = iter(tokens)
    try:
        n = int(next(it))
    except StopIteration:
        return []
    points: list[tuple[int, int]] = []
    for _ in range(n):
        try:
            x = int(next(it))
            y = int(next(it))
        except StopIteration:
            break
        points.append((x, y))
    return points


def main() -> None:
    data = sys.stdin.read().split()
    points = read_points(data)

    groups: dict[str, list[tuple[int, int]]] = {
        "I": [],
        "II": [],
        "III": [],
        "IV": [],
        "axis": [],
    }
    for x, y in points:
        groups[classify(x, y)].append((x, y))

    lines: list[str] = []
    for name in ("I", "II", "III", "IV", "axis"):
        members = groups[name]
        lines.append(f"{name}: {len(members)}")
        for x, y in members:
            lines.append(f"{x} {y}")

    sys.stdout.write("\n".join(lines) + "\n")


if __name__ == "__main__":
    main()

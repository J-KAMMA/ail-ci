import sys
from collections import defaultdict


def main() -> None:
    data = sys.stdin.read().split()
    if not data:
        return
    n = int(data[0])
    positions: dict[str, list[int]] = defaultdict(list)
    idx = 1
    for i in range(1, n + 1):
        if idx + 1 >= len(data) + 1 or idx >= len(data):
            break
        name = data[idx]
        idx += 2  # skip name and score
        positions[name].append(i)
    for name in sorted(positions):
        print(f"{name}: " + " ".join(str(p) for p in positions[name]))


if __name__ == "__main__":
    main()

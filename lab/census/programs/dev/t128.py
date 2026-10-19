import sys
from collections import defaultdict


def main() -> None:
    data = sys.stdin.read().split()
    if not data:
        return

    n = int(data[0])
    totals: defaultdict[str, float] = defaultdict(float)

    idx = 1
    for _ in range(n):
        if idx + 1 >= len(data) + 1:
            break
        name = data[idx]
        value = float(data[idx + 1])
        totals[name] += value
        idx += 2

    grand_total = 0.0
    for name in sorted(totals):
        amount = totals[name]
        grand_total += amount
        print(f"{name} {amount:.2f}")

    print(f"total {grand_total:.2f}")


if __name__ == "__main__":
    main()

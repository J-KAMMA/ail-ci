import heapq
import sys


def main() -> None:
    data = sys.stdin.read().split()
    if not data:
        return
    n = int(data[0])
    totals: dict[str, float] = {}
    idx = 1
    for _ in range(n):
        name = data[idx]
        value = float(data[idx + 1])
        idx += 2
        totals[name] = totals.get(name, 0.0) + value

    items = list(totals.items())
    top = heapq.nlargest(3, items, key=lambda kv: kv[1])
    bottom = heapq.nsmallest(3, items, key=lambda kv: kv[1])

    out = [f"{name} {value:.2f}" for name, value in top]
    out += [f"{name} {value:.2f}" for name, value in bottom]
    sys.stdout.write("\n".join(out) + "\n")


if __name__ == "__main__":
    main()

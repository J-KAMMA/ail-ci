import heapq
import sys

def main() -> None:
    totals: dict[str, float] = {}
    for name in sys.stdin.read().split():
        totals[name] = totals.get(name, 0.0) + 1.5
    items = list(totals.items())
    top = heapq.nlargest(1, items, key=lambda kv: kv[1])
    print(top)

main()

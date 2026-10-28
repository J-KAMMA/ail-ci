from collections import Counter, defaultdict
from collections import Counter as C

def main() -> int:
    a: Counter[str] = Counter()
    a["x"] += 1
    a["x"] += 2
    print(a["x"])
    b: defaultdict[str, int] = defaultdict(int)
    b["y"] += 2
    print(b["y"])
    c: C[str] = C()
    c["q"] += 7
    print(c["q"])
    return 0

main()

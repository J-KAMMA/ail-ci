import sys
from typing import Dict, List, Tuple


def main() -> None:
    lines = sys.stdin.read().splitlines()
    pos = 0

    while pos < len(lines) and lines[pos].strip() == "":
        pos += 1
    if pos >= len(lines):
        return

    n = int(lines[pos].split()[0])
    pos += 1

    best: Dict[str, Tuple[int, List[str]]] = {}
    order: List[str] = []

    for _ in range(n):
        while pos < len(lines) and lines[pos].strip() == "":
            pos += 1
        if pos >= len(lines):
            break
        parts = lines[pos].split()
        pos += 1

        name = parts[0]
        duration = int(parts[1])
        deps = parts[2:]

        total = duration
        path = [name]
        for dep in deps:
            if dep in best:
                dep_total, dep_path = best[dep]
                if dep_total + duration > total:
                    total = dep_total + duration
                    path = dep_path + [name]

        best[name] = (total, path)
        order.append(name)

    if not order:
        return

    end = max(order, key=lambda nm: best[nm][0])
    total, path = best[end]

    print("->".join(path))
    print(total)


if __name__ == "__main__":
    main()

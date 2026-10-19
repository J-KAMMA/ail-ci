import sys


def parse_number(text: str) -> int | float:
    try:
        return int(text)
    except ValueError:
        return float(text)


def main() -> None:
    lines = [line for line in sys.stdin.read().splitlines() if line.strip()]
    if not lines:
        return
    n = int(lines[0].strip())

    names: list[str] = []
    duration: dict[str, int | float] = {}
    deps: dict[str, list[str]] = {}

    for i in range(1, 1 + n):
        parts = lines[i].split()
        name = parts[0]
        names.append(name)
        duration[name] = parse_number(parts[1])
        deps[name] = parts[2:]

    finish: dict[str, int | float] = {}
    pred: dict[str, str | None] = {}

    for name in names:
        best: int | float | None = None
        best_pred: str | None = None
        for d in deps[name]:
            if d not in finish:
                continue
            if best is None or finish[d] > best:
                best = finish[d]
                best_pred = d
        start = best if best is not None else 0
        finish[name] = start + duration[name]
        pred[name] = best_pred

    if not names:
        return

    end_name = names[0]
    for name in names:
        if finish[name] > finish[end_name]:
            end_name = name

    path: list[str] = []
    current: str | None = end_name
    while current is not None:
        path.append(current)
        current = pred[current]
    path.reverse()

    print(f"{'->'.join(path)} {finish[end_name]}")


if __name__ == "__main__":
    main()

import sys
from fractions import Fraction
from collections import defaultdict


def main() -> None:
    data = sys.stdin.read().split()
    if not data:
        return
    n = int(data[0])
    totals: dict[str, int] = defaultdict(int)
    counts: dict[str, int] = defaultdict(int)
    idx = 1
    for _ in range(n):
        if idx + 1 >= len(data) + 1:
            break
        name = data[idx]
        score = int(data[idx + 1])
        idx += 2
        totals[name] += score
        counts[name] += 1

    averages: list[tuple[Fraction, str]] = []
    for name in totals:
        avg = Fraction(totals[name], counts[name])
        averages.append((avg, name))

    # Sort by average descending, then name ascending
    averages.sort(key=lambda item: (-item[0], item[1]))

    rank = 0
    prev_avg: Fraction | None = None
    lines: list[str] = []
    for avg, name in averages:
        if prev_avg is None or avg != prev_avg:
            rank += 1
            prev_avg = avg
        # Round half up to one decimal place using exact arithmetic
        scaled = avg * 10
        rounded = (scaled + Fraction(1, 2)).__floor__()
        text = f"{rounded // 10}.{rounded % 10}"
        lines.append(f"{rank} {name} {text}")

    if lines:
        sys.stdout.write("\n".join(lines) + "\n")


if __name__ == "__main__":
    main()

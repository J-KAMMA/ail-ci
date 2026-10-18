import sys
from collections.abc import Iterable


def read_numbers(lines: Iterable[str]) -> tuple[int, list[str]]:
    it = iter(lines)
    n = int(next(it))
    tokens = next(it, "").split()
    return n, tokens[:n]


def parse_ints(tokens: Iterable[str], into: list[int] | None = None) -> list[int]:
    out = [] if into is None else into
    out.extend(int(token) for token in tokens)
    return out


def compute_stats(*values: int, ndigits: int = 2, **extra: int | float) -> dict[str, int | float]:
    stats: dict[str, int | float] = {"n": len(values)}
    if values:
        stats["min"] = min(values)
        stats["max"] = max(values)
        stats["sum"] = sum(values)
        stats["mean"] = round(sum(values) / len(values), ndigits)
    stats.update(extra)
    return stats


def main() -> None:
    n, tokens = read_numbers(sys.stdin)
    numbers = parse_ints(tokens)
    options: dict[str, int] = {"ndigits": 2}
    stats = compute_stats(*numbers, **options)
    print(dict(sorted(stats.items())))


if __name__ == "__main__":
    main()

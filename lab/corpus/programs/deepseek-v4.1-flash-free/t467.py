import sys


def merge_values(base: list[int] | None = None, *more: int, **extra: int) -> list[int]:
    merged: list[int] = list(base) if base is not None else []
    merged.extend(more)
    merged.extend(extra.values())
    return merged


def summarize(*numbers: int, precision: int = 6, **options: int) -> dict[str, object]:
    values = merge_values(None, *numbers, **options)
    if not values:
        raise ValueError("no numbers provided")
    total = sum(values)
    count = len(values)
    mean = round(total / count, precision)
    return {
        "count": count,
        "sum": total,
        "min": min(values),
        "max": max(values),
        "mean": mean,
    }


def render(stats: dict[str, object]) -> str:
    parts = [f"{key}={stats[key]!r}" for key in sorted(stats)]
    return "{" + ", ".join(parts) + "}"


def main() -> None:
    data = sys.stdin.read().split()
    if not data:
        return
    n = int(data[0])
    numbers = [int(token) for token in data[1 : 1 + n]]
    stats = summarize(*numbers, precision=6)
    print(render(stats))


if __name__ == "__main__":
    main()

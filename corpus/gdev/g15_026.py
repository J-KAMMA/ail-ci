# task: Process pairs of numbers through a safe division function and produce a report that counts errors by exception class name.
from collections import Counter
from typing import Final


PAIRS: Final[list[tuple[object, object]]] = [
    (10, 2),
    (7, 0),
    (None, 3),
    ("abc", 2),
    ("9", "3"),
    (1.5, 0.5),
    (0, 0),
    (5, "x"),
    (2**1000, 2**999),
    (-8, 4),
    (1, 0.0),
    ("2.5", 0.5),
    (3, None),
    ("1e3", 10),
    (float("inf"), 2),
    ([1, 2], 4),
]


def safe_divide(numerator: object, denominator: object) -> float:
    """Divide two values after converting them to float.

    Raises the underlying exception (TypeError, ValueError,
    ZeroDivisionError, ...) when the division cannot be performed.
    """
    num: float = float(numerator)  # type: ignore[arg-type]
    den: float = float(denominator)  # type: ignore[arg-type]
    return num / den


def process_pairs(
    pairs: list[tuple[object, object]],
) -> tuple[list[tuple[int, float]], Counter[str]]:
    """Run every pair through safe_divide.

    Returns the successful results as (index, quotient) tuples and a
    Counter mapping exception class names to how often they occurred.
    """
    results: list[tuple[int, float]] = []
    errors: Counter[str] = Counter()
    for index, (numerator, denominator) in enumerate(pairs):
        try:
            quotient = safe_divide(numerator, denominator)
        except Exception as exc:  # noqa: BLE001 - we want to count every failure
            errors[type(exc).__name__] += 1
        else:
            results.append((index, quotient))
    return results, errors


def format_quotient(value: float) -> str:
    if value != value:
        return "nan"
    if value in (float("inf"), float("-inf")):
        return "inf" if value > 0 else "-inf"
    return f"{value:.4f}"


def build_report(
    pairs: list[tuple[object, object]],
    results: list[tuple[int, float]],
    errors: Counter[str],
) -> str:
    lines: list[str] = []
    total = len(pairs)
    failed = sum(errors.values())
    lines.append("Safe Division Report")
    lines.append("=" * 40)
    lines.append(f"Total pairs processed : {total}")
    lines.append(f"Successful divisions  : {len(results)}")
    lines.append(f"Failed divisions      : {failed}")
    lines.append("")
    lines.append("Successful results:")
    for index, quotient in results:
        numerator, denominator = pairs[index]
        lines.append(
            f"  [{index:02d}] {numerator!r} / {denominator!r} = {format_quotient(quotient)}"
        )
    lines.append("")
    lines.append("Errors by exception class:")
    if not errors:
        lines.append("  (none)")
    else:
        # Sort by descending count, then by class name for stable output.
        for name, count in sorted(errors.items(), key=lambda item: (-item[1], item[0])):
            lines.append(f"  {name}: {count}")
    return "\n".join(lines)


def main() -> None:
    results, errors = process_pairs(PAIRS)
    print(build_report(PAIRS, results, errors))


if __name__ == "__main__":
    main()

import sys
from collections import defaultdict


def main() -> None:
    quarters = ("q1", "q2", "q3", "q4")
    data: dict[str, dict[str, int]] = defaultdict(lambda: dict.fromkeys(quarters, 0))

    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        region, quarter, amount = (part.strip() for part in line.split(","))
        data[region][quarter] += int(amount)

    regions = sorted(data)

    print(f"{'region':<7}" + "".join(f"{q:>7}" for q in quarters) + f"{'total':>7}")
    for region in regions:
        row_total = sum(data[region][q] for q in quarters)
        print(f"{region:<7}" + "".join(f"{data[region][q]:>7}" for q in quarters) + f"{row_total:>7}")

    grand = sum(data[r][q] for r in regions for q in quarters)
    print(f"{'TOTAL':<7}" + "".join(f"{sum(data[r][q] for r in regions):>7}" for q in quarters) + f"{grand:>7}")


if __name__ == "__main__":
    main()

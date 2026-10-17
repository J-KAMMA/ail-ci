import sys
from collections import defaultdict


def main() -> None:
    region_totals: dict[str, int] = defaultdict(int)
    quarter_totals: dict[str, int] = defaultdict(int)

    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        region, quarter, amount = line.split(",")
        value = int(amount)
        region_totals[region.strip()] += value
        quarter_totals[quarter.strip()] += value

    if not region_totals:
        return

    grand_total = sum(region_totals.values())

    top_region, top_region_total = max(
        region_totals.items(), key=lambda item: (item[1], item[0])
    )
    top_quarter, top_quarter_total = max(
        quarter_totals.items(), key=lambda item: (item[1], item[0])
    )

    print(f"Region with the highest total: {top_region} ({top_region_total})")
    print(f"Quarter with the highest total: {top_quarter} ({top_quarter_total})")

    for region in sorted(region_totals, key=lambda r: (-region_totals[r], r)):
        share = region_totals[region] / grand_total * 100
        print(f"{region}: {share:.1f}%")


if __name__ == "__main__":
    main()

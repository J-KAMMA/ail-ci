import sys
from collections import defaultdict


def main() -> None:
    region_totals: dict[str, int] = defaultdict(int)
    quarter_totals: dict[str, int] = defaultdict(int)

    for raw_line in sys.stdin:
        line = raw_line.strip()
        if not line:
            continue
        region, quarter, amount_text = line.split(",")
        amount = int(amount_text)
        region_totals[region] += amount
        quarter_totals[quarter] += amount

    grand_total = sum(region_totals.values())

    top_region = max(region_totals, key=lambda r: region_totals[r])
    top_quarter = max(quarter_totals, key=lambda q: quarter_totals[q])

    print(top_region)
    print(top_quarter)
    for region, total in region_totals.items():
        share = total / grand_total * 100
        print(f"{region}: {share:.1f}%")


if __name__ == "__main__":
    main()

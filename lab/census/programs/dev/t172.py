import sys


QUARTERS: list[str] = ["q1", "q2", "q3", "q4"]
WIDTH: int = 7


def main() -> None:
    table: dict[str, dict[str, int]] = {}

    for raw in sys.stdin:
        line = raw.strip()
        if not line:
            continue
        parts = [p.strip() for p in line.split(",")]
        if len(parts) != 3:
            continue
        region, quarter, amount_text = parts
        quarter = quarter.lower()
        if quarter not in QUARTERS:
            continue
        try:
            amount = int(amount_text)
        except ValueError:
            continue
        row = table.setdefault(region, {q: 0 for q in QUARTERS})
        row[quarter] += amount

    regions = sorted(table)
    name_width = max([len("region"), len("total")] + [len(r) for r in regions])

    col_totals: dict[str, int] = {q: 0 for q in QUARTERS}
    grand_total = 0

    header = f"{'region':<{name_width}}" + "".join(
        f"{q:>{WIDTH}}" for q in QUARTERS
    ) + f"{'total':>{WIDTH}}"
    print(header)

    for region in regions:
        values = table[region]
        row_total = 0
        cells = []
        for q in QUARTERS:
            v = values[q]
            cells.append(f"{v:>{WIDTH}}")
            col_totals[q] += v
            row_total += v
        grand_total += row_total
        print(f"{region:<{name_width}}" + "".join(cells) + f"{row_total:>{WIDTH}}")

    footer = f"{'total':<{name_width}}" + "".join(
        f"{col_totals[q]:>{WIDTH}}" for q in QUARTERS
    ) + f"{grand_total:>{WIDTH}}"
    print(footer)


if __name__ == "__main__":
    main()

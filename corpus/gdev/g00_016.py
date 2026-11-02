# task: Write a script that formats a hardcoded list of product names and prices into a right-aligned table using str.format.
from typing import Sequence


PRODUCTS: list[tuple[str, float]] = [
    ("Wireless Mouse", 24.99),
    ("Mechanical Keyboard", 89.50),
    ("27-inch Monitor", 219.00),
    ("USB-C Hub", 39.95),
    ("Laptop Stand", 45.00),
    ("Noise-Cancelling Headphones", 199.99),
    ("HDMI Cable (2m)", 9.49),
    ("External SSD 1TB", 109.00),
]


def build_table(rows: Sequence[tuple[str, float]]) -> list[str]:
    name_width = max(len("Product"), *(len(name) for name, _ in rows))
    price_width = max(len("Price"), *(len(f"{price:.2f}") for _, price in rows))
    total_width = name_width + price_width + 3

    header = "{:>{nw}} | {:>{pw}}".format("Product", "Price", nw=name_width, pw=price_width)
    separator = "-" * total_width

    lines: list[str] = [header, separator]
    for name, price in rows:
        lines.append(
            "{:>{nw}} | {:>{pw}}".format(
                name, f"{price:.2f}", nw=name_width, pw=price_width
            )
        )
    total = sum(price for _, price in rows)
    lines.append(separator)
    lines.append(
        "{:>{nw}} | {:>{pw}}".format(
            "Total", f"{total:.2f}", nw=name_width, pw=price_width
        )
    )
    return lines


def main() -> None:
    for line in build_table(PRODUCTS):
        print(line)


if __name__ == "__main__":
    main()

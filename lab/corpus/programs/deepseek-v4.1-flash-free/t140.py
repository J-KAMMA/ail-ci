import sys
from typing import Dict


def main() -> None:
    stock: Dict[str, int] = {}
    out: list[str] = []

    for line in sys.stdin:
        parts = line.split()
        if not parts:
            continue
        command = parts[0]

        if command == "add":
            item, qty = parts[1], int(parts[2])
            stock[item] = stock.get(item, 0) + qty
        elif command == "remove":
            item, qty = parts[1], int(parts[2])
            current = stock.get(item, 0)
            if qty > current:
                out.append(f"short by {qty - current}")
                stock[item] = 0
            else:
                stock[item] = current - qty
        elif command == "report":
            for name in sorted(stock):
                out.append(f"{name} {stock[name]}")

    sys.stdout.write("\n".join(out))
    if out:
        sys.stdout.write("\n")


if __name__ == "__main__":
    main()

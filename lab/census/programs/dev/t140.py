import sys


def main() -> None:
    stock: dict[str, int] = {}

    for raw_line in sys.stdin:
        parts = raw_line.split()
        if not parts:
            continue

        command = parts[0].lower()

        if command == "add" and len(parts) == 3:
            item = parts[1]
            qty = int(parts[2])
            stock[item] = stock.get(item, 0) + qty

        elif command == "remove" and len(parts) == 3:
            item = parts[1]
            qty = int(parts[2])
            current = stock.get(item, 0)
            if qty > current:
                print(f"short by {qty - current}")
                current = 0
            else:
                current -= qty
            if item in stock or current > 0:
                stock[item] = current

        elif command == "report" and len(parts) == 1:
            for item in sorted(stock):
                print(f"{item} {stock[item]}")


if __name__ == "__main__":
    main()

import sys


def main() -> None:
    stock: dict[str, int] = {}
    total_added = 0

    for line in sys.stdin:
        parts = line.split()
        if not parts:
            continue

        command = parts[0]

        if command == "add":
            item, qty = parts[1], int(parts[2])
            stock[item] = stock.get(item, 0) + qty
            total_added += qty
        elif command == "remove":
            item, qty = parts[1], int(parts[2])
            stock[item] = stock.get(item, 0) - qty
        elif command == "report":
            if stock:
                top_item = max(stock, key=lambda name: stock[name])
                print(top_item)

    print(total_added)


if __name__ == "__main__":
    main()

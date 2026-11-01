from operator import itemgetter


def main() -> int:
    rows = [
        ("widget", 12, 3.5),
        ("gadget", 7, 9.25),
        ("doohickey", 12, 1.0),
        ("sprocket", 7, 4.5),
    ]
    print("by name")
    for name, qty, price in sorted(rows, key=itemgetter(0)):
        print(name, qty, price)
    print("by quantity, then price")
    for name, qty, price in sorted(rows, key=itemgetter(1, 2)):
        print(name, qty, price)
    top = max(rows, key=itemgetter(2))
    print("priciest", top[0], top[2])
    cheap = min(rows, key=itemgetter(2))
    print("cheapest", cheap[0], cheap[2])
    name_qty = itemgetter(0, 1)
    for row in rows:
        print(name_qty(row))
    first = itemgetter(0)
    print([first(row) for row in rows])
    return 0


main()

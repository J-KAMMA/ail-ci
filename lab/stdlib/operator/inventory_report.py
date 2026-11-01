import functools
import operator


def main() -> int:
    stock = [
        {"name": "bolts", "qty": 40, "price": 0.25},
        {"name": "nuts", "qty": 25, "price": 0.10},
        {"name": "washers", "qty": 60, "price": 0.05},
        {"name": "screws", "qty": 15, "price": 0.15},
    ]
    by_qty = sorted(stock, key=operator.itemgetter("qty"))
    for item in by_qty:
        print(item["name"], operator.getitem(item, "qty"), item["price"])
    total_qty = functools.reduce(operator.add, [item["qty"] for item in stock])
    print("total", total_qty)
    total_value = 0.0
    for item in stock:
        total_value = operator.add(total_value, operator.mul(item["qty"], item["price"]))
    print("value", total_value)
    most = max(stock, key=operator.itemgetter("qty"))
    print("most", most["name"], most["qty"])
    names = [item["name"] for item in stock]
    print("names", sorted(names))
    print("has nuts", operator.contains(names, "nuts"))
    print("index screws", operator.indexOf(names, "screws"))
    return 0


main()

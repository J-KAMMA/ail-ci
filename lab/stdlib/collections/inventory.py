from collections import Counter


def main() -> int:
    stock = Counter({"apple": 4, "pear": 2, "plum": 0})
    stock.update({"apple": 3, "kiwi": 5})
    stock.update(["pear", "pear", "fig"])
    print(stock["apple"], stock["pear"], stock["kiwi"], stock["fig"])
    sold = Counter(["apple", "apple", "kiwi", "plum", "ghost"])
    remaining = stock - sold
    print(sorted(remaining.items()))
    print(remaining["plum"], remaining["ghost"])
    needs = Counter({"apple": 10, "pear": 1})
    restock = needs - remaining
    print(sorted(restock.items()))
    print(remaining + needs)
    print(remaining & needs)
    print(remaining | needs)
    for name in sorted(stock):
        if stock[name] == 0:
            print("empty", name)
    del stock["plum"]
    del stock["missing"]
    print(sorted(stock.items()), len(stock))
    empty: Counter[str] = Counter()
    print(empty == Counter(), empty.most_common(0), empty.most_common(-1))
    print(Counter([1, 1, 2, 3, 3, 3]).most_common(1))
    print(Counter(range(4)).total())
    return 0


main()

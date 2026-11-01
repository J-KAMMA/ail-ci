import copy

class Item:
    def __init__(self, name: str, price: int) -> None:
        self.name = name
        self.price = price
        self.tags = ["sale"]

def main() -> None:
    basket = [Item("apple", 3), Item("pear", 5)]
    shallow = copy.copy(basket)
    shallow.append(Item("fig", 7))
    shallow[0].price = 10
    print(len(basket), len(shallow))
    print(basket[0].price, shallow[0].price)
    print(basket[0].tags is shallow[0].tags)

    snap = copy.deepcopy(basket)
    snap[0].price = 99
    snap[0].tags.append("frozen")
    print(basket[0].price, snap[0].price)
    print(basket[0].tags, snap[0].tags)
    print(basket[0] is snap[0])
    print([item.name for item in snap])

main()

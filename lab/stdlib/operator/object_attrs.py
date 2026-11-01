from operator import attrgetter


class Product:
    def __init__(self, name: str, price: float, stock: int):
        self.name = name
        self.price = price
        self.stock = stock


class Order:
    def __init__(self, product: Product, qty: int):
        self.product = product
        self.qty = qty


def main() -> int:
    items = [
        Product("hammer", 12.5, 4),
        Product("saw", 8.0, 11),
        Product("drill", 45.0, 2),
        Product("level", 8.0, 7),
    ]
    print("by name")
    for item in sorted(items, key=attrgetter("name")):
        print(item.name, item.price, item.stock)
    print("by price, then name")
    for item in sorted(items, key=attrgetter("price", "name")):
        print(item.name, item.price, item.stock)
    stock_of = attrgetter("stock")
    for item in items:
        print(item.name, stock_of(item))
    orders = [Order(items[0], 2), Order(items[2], 1)]
    print("orders")
    for order in sorted(orders, key=attrgetter("product.price")):
        print(order.product.name, order.qty, order.product.price)
    cheapest = min(items, key=attrgetter("price"))
    print("cheapest", cheapest.name, cheapest.price)
    return 0


main()

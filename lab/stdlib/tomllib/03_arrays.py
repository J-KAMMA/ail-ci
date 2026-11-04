import tomllib

DOC = '''
empty = []
numbers = [1, 2, 3, 4]
nested = [[1, 2], [3, 4, 5], []]
mixed = ["a", 2, true, 3.5]
trailing = [
  1,
  2,
  3,
]

[[products]]
name = "Hammer"
sku = 738594937

[[products]]
name = "Nail"
sku = 284758393
color = "gray"

[[products.tags]]
name = "metal"
[[products.tags]]
name = "tool"
'''


def main():
    data = tomllib.loads(DOC)
    print("empty", data["empty"])
    print("numbers", data["numbers"], sum(data["numbers"]))
    print("nested", len(data["nested"]), data["nested"][1][2])
    print("mixed", data["mixed"])
    print("trailing", data["trailing"])
    print("products", len(data["products"]))
    for product in data["products"]:
        print("product", product["name"], product["sku"], product.get("color", "none"))
    print("tags", [tag["name"] for tag in data["products"][1]["tags"]])


main()

# task: Create a dataclass with field(compare=False) on one attribute and show how equality ignores that field.
from dataclasses import dataclass, field


@dataclass
class Product:
    sku: str
    price: float
    # Excluded from __eq__ (and __hash__ when hashing is used), so it is
    # ignored when comparing two Product instances.
    last_viewed_by: str = field(default="", compare=False)


def main() -> None:
    a = Product(sku="A-100", price=9.99, last_viewed_by="alice")
    b = Product(sku="A-100", price=9.99, last_viewed_by="bob")
    c = Product(sku="A-100", price=12.50, last_viewed_by="alice")
    d = Product(sku="B-200", price=9.99, last_viewed_by="alice")

    print("Instances:")
    print(f"  a = {a}")
    print(f"  b = {b}")
    print(f"  c = {c}")
    print(f"  d = {d}")
    print()

    print("Equality results:")
    print(f"  a == b (differs only in compare=False field): {a == b}")
    print(f"  a == c (differs in price, compared field):    {a == c}")
    print(f"  a == d (differs in sku, compared field):      {a == d}")
    print()

    print("Field comparison metadata:")
    for f in Product.__dataclass_fields__.values():
        print(f"  {f.name}: compare={f.compare}")
    print()

    # Demonstrate that the ignored field is still stored and accessible.
    print("Ignored field is still stored:")
    print(f"  a.last_viewed_by = {a.last_viewed_by!r}")
    print(f"  b.last_viewed_by = {b.last_viewed_by!r}")
    print()

    # Equality inside containers follows the same rule.
    catalog = [a, c, d]
    print("Membership checks:")
    print(f"  b in [a, c, d]: {b in catalog}")
    print(f"  Product('A-100', 12.5) in [a, c, d]: "
          f"{Product('A-100', 12.5) in catalog}")


if __name__ == "__main__":
    main()

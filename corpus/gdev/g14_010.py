# task: Use dataclasses.fields() to list the name and type of each field in a Product dataclass.
from dataclasses import dataclass, fields


@dataclass
class Product:
    name: str
    price: float
    quantity: int
    in_stock: bool = True
    tags: list[str] | None = None


def main() -> None:
    for f in fields(Product):
        type_name = f.type if isinstance(f.type, str) else getattr(f.type, "__name__", repr(f.type))
        print(f"{f.name}: {type_name}")


if __name__ == "__main__":
    main()

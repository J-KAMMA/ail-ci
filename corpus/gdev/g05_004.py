# task: Merge three dictionaries of inventory counts by summing values for shared keys and print the combined result sorted by key.
from collections import Counter


def merge_inventories(*inventories: dict[str, int]) -> dict[str, int]:
    """Merge inventory dictionaries by summing counts for shared keys."""
    total: Counter[str] = Counter()
    for inventory in inventories:
        total.update(inventory)
    return dict(total)


def main() -> None:
    warehouse_a: dict[str, int] = {"apples": 10, "bananas": 5, "cherries": 7}
    warehouse_b: dict[str, int] = {"bananas": 3, "dates": 12, "apples": 4}
    warehouse_c: dict[str, int] = {"cherries": 2, "elderberries": 9, "dates": 1}

    combined = merge_inventories(warehouse_a, warehouse_b, warehouse_c)

    for key in sorted(combined):
        print(f"{key}: {combined[key]}")


if __name__ == "__main__":
    main()

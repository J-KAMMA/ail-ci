# task: Merge a list of dictionaries with functools.reduce, summing values for keys that appear in multiple dictionaries.
from functools import reduce
from typing import Dict, List


def merge_sum(acc: Dict[str, int], item: Dict[str, int]) -> Dict[str, int]:
    """Return a new dictionary with values summed for shared keys."""
    result = dict(acc)
    for key, value in item.items():
        result[key] = result.get(key, 0) + value
    return result


def merge_all(dicts: List[Dict[str, int]]) -> Dict[str, int]:
    """Merge a list of dictionaries, summing values for duplicate keys."""
    return reduce(merge_sum, dicts, {})


def main() -> None:
    data: List[Dict[str, int]] = [
        {"apples": 3, "bananas": 2, "cherries": 5},
        {"bananas": 4, "dates": 1},
        {"apples": 7, "cherries": 1, "elderberries": 6},
        {},
        {"dates": 9, "figs": 2},
    ]

    merged = merge_all(data)

    print("Merged totals:")
    for key in sorted(merged):
        print(f"  {key}: {merged[key]}")

    grand_total = sum(merged.values())
    print(f"Grand total: {grand_total}")


if __name__ == "__main__":
    main()

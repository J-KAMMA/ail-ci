from typing import Dict, List, get_type_hints


def greet(name: str, times: int = 1) -> str:
    return ("hi " + name + " ") * times


def totals(values: List[int], weights: Dict[str, int]) -> int:
    total = sum(values)
    total += sum(weights.values())
    return total


def main() -> None:
    gh = get_type_hints(greet)
    print(sorted(gh))
    print(gh["name"], gh["times"], gh["return"])
    th = get_type_hints(totals)
    print(sorted(th))
    print(th["values"], th["weights"], th["return"])
    print(greet("ada", 2))
    print(totals([1, 2, 3], {"a": 4}))


main()

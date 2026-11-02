from typing import Callable, Dict, List, Optional, Union

Number = Union[int, float]


def clamp(value: Number, low: Number, high: Number) -> Number:
    if value < low:
        return low
    if value > high:
        return high
    return value


def apply_all(values: List[int], fn: Callable[[int], int]) -> List[int]:
    out: List[int] = []
    for v in values:
        out.append(fn(v))
    return out


def lookup(table: Dict[str, int], key: str) -> Optional[int]:
    if key in table:
        return table[key]
    return None


def main() -> None:
    print(clamp(15, 0, 10))
    print(clamp(-5, 0, 10))
    print(clamp(2.5, 0.0, 10.0))
    print(apply_all([1, 2, 3], lambda n: n * n))
    scores: Dict[str, int] = {"ada": 10, "bob": 7}
    print(lookup(scores, "ada"))
    print(lookup(scores, "zoe"))
    print(scores.get("bob", 0), scores.get("zoe", -1))


main()

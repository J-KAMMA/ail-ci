from typing import Sequence

def inverses(base: int, moduli: Sequence[int]) -> list[tuple[int, int]]:
    return [(m, pow(base, -1, m)) for m in moduli]

print(inverses(3, [11, 17]))

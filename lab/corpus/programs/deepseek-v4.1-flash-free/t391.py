import random
from typing import List


def main() -> None:
    data = input().split()
    seed = int(data[0])
    n = int(data[1])

    rng = random.Random(seed)
    numbers: List[int] = [rng.randint(1, 100) for _ in range(n)]
    print(*numbers)

    sample_rng = random.Random(seed)
    print(sum(sample_rng.sample(range(100), 5)))


if __name__ == "__main__":
    main()

import statistics
import sys
from typing import List


def main() -> None:
    tokens: List[str] = sys.stdin.read().split()
    if not tokens:
        return
    n: int = int(tokens[0])
    nums: List[int] = [int(x) for x in tokens[1:1 + n]]

    print(statistics.mean(nums))
    print(statistics.median(nums))

    modes: List[int] = statistics.multimode(nums)
    print(modes[0] if len(modes) == 1 else "multi")

    if n < 2:
        print("n/a")
        print("n/a")
    else:
        print(f"{statistics.pstdev(nums):.3f}")
        print(f"{statistics.stdev(nums):.3f}")


if __name__ == "__main__":
    main()

# task: Compute the minimum number of coins needed to make amount 987 using coins [1, 5, 10, 25, 50] and print the result.
from typing import Sequence


def min_coins(amount: int, coins: Sequence[int]) -> int:
    """Return the minimum number of coins needed to make `amount`.

    Uses bottom-up dynamic programming. Returns -1 if the amount cannot be made.
    """
    INF = float("inf")
    best: list[float] = [0] + [INF] * amount
    for value in range(1, amount + 1):
        for coin in coins:
            if coin <= value and best[value - coin] + 1 < best[value]:
                best[value] = best[value - coin] + 1
    result = best[amount]
    return -1 if result == INF else int(result)


def main() -> None:
    amount: int = 987
    coins: list[int] = [1, 5, 10, 25, 50]
    result: int = min_coins(amount, coins)
    print(f"Minimum number of coins to make {amount}: {result}")


if __name__ == "__main__":
    main()

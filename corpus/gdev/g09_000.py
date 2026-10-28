# task: Compute the 90th Fibonacci number modulo 1000000007 using bottom-up dynamic programming and print the result.
from typing import List


MOD: int = 1_000_000_007
TARGET_INDEX: int = 90


def fibonacci_mod(n: int, mod: int) -> int:
    """Return the n-th Fibonacci number (F(0)=0, F(1)=1) modulo mod,
    computed bottom-up with dynamic programming."""
    if n < 0:
        raise ValueError("n must be non-negative")
    if n == 0:
        return 0
    dp: List[int] = [0] * (n + 1)
    dp[1] = 1 % mod
    for i in range(2, n + 1):
        dp[i] = (dp[i - 1] + dp[i - 2]) % mod
    return dp[n]


def main() -> None:
    result: int = fibonacci_mod(TARGET_INDEX, MOD)
    print(result)


if __name__ == "__main__":
    main()

import math
import sys


def main() -> None:
    tokens: list[str] = sys.stdin.read().split()
    if not tokens:
        return

    n: int = int(tokens[0])
    numbers: list[int] = [int(tok) for tok in tokens[1:1 + n]]

    count: int = min(n, 8)
    scaled: list[int] = [abs(value) + 1 for value in numbers[:count]]

    for value in scaled:
        sqrt_part: str = f"{math.sqrt(value):.3f}"
        log_part: str = f"{math.log2(value):.3f}" if value > 0 else "nan"
        sin_part: str = f"{math.sin(value):.3f}"
        cos_part: str = f"{math.cos(value):.3f}"
        print(f"{sqrt_part} {log_part} {sin_part} {cos_part}")

    if count >= 2:
        hypot_part: str = f"{math.hypot(scaled[0], scaled[1]):.3f}"
        gcd_part: str = str(math.gcd(numbers[0], numbers[1]))
        isqrt_part: str = str(math.isqrt(abs(numbers[0])))
        print(f"{hypot_part} {gcd_part} {isqrt_part}")


if __name__ == "__main__":
    main()

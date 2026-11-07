import sys
import math


def is_digits(s: str) -> bool:
    if len(s) == 0:
        return False
    i: int = 0
    while i < len(s):
        ch: str = s[i]
        if ch < "0" or ch > "9":
            return False
        i += 1
    return True


def strip_leading_zeros(s: str) -> str:
    i: int = 0
    while i < len(s) - 1 and s[i] == "0":
        i += 1
    return s[i:]


def at_most(s: str, limit: str) -> bool:
    text: str = strip_leading_zeros(s)
    if len(text) < len(limit):
        return True
    if len(text) > len(limit):
        return False
    return text <= limit


def parse_seed(s: str) -> tuple[int, int, int, int]:
    x0: int = 0
    x1: int = 0
    x2: int = 0
    x3: int = 0
    i: int = 0
    while i < len(s):
        digit: int = int(s[i])
        part: int = x0 * 10 + digit
        x0 = part & 65535
        carry: int = part >> 16
        part = x1 * 10 + carry
        x1 = part & 65535
        carry = part >> 16
        part = x2 * 10 + carry
        x2 = part & 65535
        carry = part >> 16
        part = x3 * 10 + carry
        x3 = part & 65535
        i += 1
    return x0, x1, x2, x3


def format_value(value: float) -> str:
    text: str = format(value, ".9f")
    if text == "-0.000000000":
        text = "0.000000000"
    return text


def main() -> int:
    if len(sys.argv) != 4:
        return 1

    arg_n: str = sys.argv[1]
    arg_t: str = sys.argv[2]
    arg_seed: str = sys.argv[3]

    if not is_digits(arg_n) or not is_digits(arg_t) or not is_digits(arg_seed):
        return 1
    if not at_most(arg_n, "10000000"):
        return 1
    if not at_most(arg_t, "1000000"):
        return 1
    if not at_most(arg_seed, "18446744073709551615"):
        return 1

    n: int = int(strip_leading_zeros(arg_n))
    if n < 1:
        return 1
    sweep_count: int = int(strip_leading_zeros(arg_t))

    x0, x1, x2, x3 = parse_seed(strip_leading_zeros(arg_seed))

    heights: list[float] = [0.0] * n

    a0: int = 32557
    a1: int = 19605
    a2: int = 62509
    a3: int = 22609
    c0: int = 33103
    c1: int = 63335
    c2: int = 31614
    c3: int = 5125

    i: int = 0
    while i < n:
        p0: int = x0 * a0
        p1: int = x0 * a1 + x1 * a0
        p2: int = x0 * a2 + x1 * a1 + x2 * a0
        p3: int = x0 * a3 + x1 * a2 + x2 * a1 + x3 * a0

        acc: int = p0 + c0
        x0 = acc & 65535
        carry: int = acc >> 16

        acc = p1 + c1 + carry
        x1 = acc & 65535
        carry = acc >> 16

        acc = p2 + c2 + carry
        x2 = acc & 65535
        carry = acc >> 16

        acc = p3 + c3 + carry
        x3 = acc & 65535

        shifted: int = (x3 << 15) + (x2 >> 1)
        value: int = shifted % 2001
        heights[i] = (value - 1000) / 64.0
        i += 1

    left: float = 0.0
    right: float = 0.0
    center: float = 0.0
    diff: float = 0.0
    grad: float = 0.0

    sweep: int = 1
    while sweep <= sweep_count:
        if (sweep & 1) == 1:
            i = 0
            while i < n:
                left = heights[(i + n - 1) % n]
                right = heights[(i + 1) % n]
                center = heights[i]
                diff = (left + right) - (center + center)
                grad = diff / (1.0 + math.sqrt(diff * diff + 0.0625))
                heights[i] = center + 0.375 * grad
                i += 1
        else:
            i = n - 1
            while i >= 0:
                left = heights[(i + n - 1) % n]
                right = heights[(i + 1) % n]
                center = heights[i]
                diff = (left + right) - (center + center)
                grad = diff / (1.0 + math.sqrt(diff * diff + 0.0625))
                heights[i] = center + 0.375 * grad
                i -= 1
        sweep += 1

    total: float = 0.0
    energy: float = 0.0
    minv: float = heights[0]
    maxv: float = heights[0]
    current: float = 0.0
    next_value: float = 0.0
    delta: float = 0.0

    i = 0
    while i < n:
        current = heights[i]
        total = total + current
        next_value = heights[(i + 1) % n]
        delta = next_value - current
        energy = energy + delta * delta
        if current < minv:
            minv = current
        if current > maxv:
            maxv = current
        i += 1

    print("sum " + format_value(total))
    print("energy " + format_value(energy))
    print("min " + format_value(minv))
    print("max " + format_value(maxv))
    print("first " + format_value(heights[0]))
    print("middle " + format_value(heights[n // 2]))
    print("last " + format_value(heights[n - 1]))

    return 0


if __name__ == "__main__":
    sys.exit(main())

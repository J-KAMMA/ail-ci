"""Example 1: integer exports, including the int64 overflow boundary."""

__ail_name__ = "fib"
__ail_export__ = ["fib", "gcd", "sum_line"]


def fib(n: int) -> int:
    if n < 2:
        return n
    a = 0
    b = 1
    i = 2
    while i <= n:
        c = a + b
        a = b
        b = c
        i += 1
    return b


def gcd(a: int, b: int) -> int:
    while b != 0:
        t = a % b
        a = b
        b = t
    return a


def sum_line(line: str) -> int:
    total = 0
    cur = 0
    seen = False
    for ch in line:
        if ch >= "0" and ch <= "9":
            cur = cur * 10 + (ord(ch) - 48)
            seen = True
        else:
            if seen:
                total += cur
                cur = 0
                seen = False
    if seen:
        total += cur
    return total


if __name__ == "__main__":
    print("fib(0) = %d" % fib(0))
    print("fib(1) = %d" % fib(1))
    print("fib(10) = %d" % fib(10))
    print("fib(92) = %d" % fib(92))
    print("gcd(48, 18) = %d" % gcd(48, 18))
    print("gcd(-48, 18) = %d" % gcd(-48, 18))
    print('sum_line("a12 b34 c5") = %d' % sum_line("a12 b34 c5"))
    print('sum_line("no digits") = %d' % sum_line("no digits"))

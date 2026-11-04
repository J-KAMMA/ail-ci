"""Total Collatz step count of 2**300 + k for k = 0..199.

Every starting value is a 301-bit exact integer.  The even branch uses a
right shift-sized division and the odd branch 3*x+1; the sum of the stopping
times is printed.
"""


def main() -> None:
    total = 0
    k = 0
    while k < 200:
        x = 2 ** 300 + k
        steps = 0
        while x != 1:
            if x % 2 == 0:
                x = x // 2
            else:
                x = 3 * x + 1
            steps = steps + 1
        total = total + steps
        k = k + 1
    print(total)


main()

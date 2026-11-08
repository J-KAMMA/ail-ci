from ail import read_stdin_bytes, write_stdout_bytes
from concurrent.futures import ThreadPoolExecutor
import sys


def steps(n: int) -> int:
    c = 0
    while n != 1:
        if n % 2 == 0:
            n = n // 2
        else:
            n = 3 * n + 1
        c += 1
    return c


def term(n: int) -> int:
    return steps(n) * (n % 7 - 3)


def main() -> int:
    data = read_stdin_bytes(1 << 20)
    ln = len(data)
    pos = 0
    while pos < ln and (data[pos] < 48 or data[pos] > 57):
        pos += 1
    n = 0
    while pos < ln and data[pos] >= 48 and data[pos] <= 57:
        n = n * 10 + data[pos] - 48
        pos += 1
    with ThreadPoolExecutor(max_workers=4) as ex:
        total = sum(ex.map(term, range(1, n + 1)))
    out = f'{total}\n'
    write_stdout_bytes(out.encode())
    return 0


if __name__ == "__main__":
    sys.exit(main())

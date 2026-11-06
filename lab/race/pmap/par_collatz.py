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
    while pos < ln and (data[pos] < 48 or data[pos] > 57):
        pos += 1
    w = 0
    while pos < ln and data[pos] >= 48 and data[pos] <= 57:
        w = w * 10 + data[pos] - 48
        pos += 1
    with ThreadPoolExecutor(max_workers=w) as ex:
        res = list(ex.map(steps, range(1, n + 1)))
    best = -1
    bestn = 0
    total = 0
    for i in range(n):
        v = res[i]
        total += v
        if v > best:
            best = v
            bestn = i + 1
    out = f'{best} {bestn} {total}\n'
    write_stdout_bytes(out.encode())
    return 0


if __name__ == "__main__":
    sys.exit(main())

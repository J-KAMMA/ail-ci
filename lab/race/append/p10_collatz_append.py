"""D3 speed/RSS load: the par_collatz body, but the result is appended (keep n whose step count is
odd) instead of written into r[i]. Read n and w from stdin exactly as lab/race/pmap/par_collatz.py."""
from ail import read_stdin_bytes, write_stdout_bytes
import sys


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
    out = []
    for i in par_range(1, n + 1):
        c = 0
        x = i
        while x != 1:
            if x % 2 == 0:
                x = x // 2
            else:
                x = 3 * x + 1
            c += 1
        if c % 2 == 1:
            out.append(i)
    total = 0
    for v in out:
        total += v
    write_stdout_bytes(('%d %d\n' % (len(out), total)).encode())
    return 0


if __name__ == "__main__":
    sys.exit(main())

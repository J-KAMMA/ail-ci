import sys


def main() -> None:
    data = sys.stdin.buffer.read().split()
    if not data:
        return

    n = int(data[0])
    q = int(data[1])
    arr = [int(x) for x in data[2:2 + n]]
    pos = 2 + n

    # Prefix sums for range sums.
    prefix: list[int] = [0] * (n + 1)
    for i, value in enumerate(arr):
        prefix[i + 1] = prefix[i] + value

    # Sparse tables for range minimum and maximum.
    mn_table: list[list[int]] = [arr[:]]
    mx_table: list[list[int]] = [arr[:]]
    k = 1
    while (1 << k) <= n:
        half = 1 << (k - 1)
        prev_mn = mn_table[-1]
        prev_mx = mx_table[-1]
        length = n - (1 << k) + 1
        cur_mn = [min(prev_mn[i], prev_mn[i + half]) for i in range(length)]
        cur_mx = [max(prev_mx[i], prev_mx[i + half]) for i in range(length)]
        mn_table.append(cur_mn)
        mx_table.append(cur_mx)
        k += 1

    out: list[str] = []
    for _ in range(q):
        l = int(data[pos])
        r = int(data[pos + 1])
        pos += 2

        total = prefix[r + 1] - prefix[l]
        length = r - l + 1
        j = length.bit_length() - 1
        lo = min(mn_table[j][l], mn_table[j][r - (1 << j) + 1])
        hi = max(mx_table[j][l], mx_table[j][r - (1 << j) + 1])
        out.append(f"{total} {lo} {hi}")

    sys.stdout.write("\n".join(out) + ("\n" if out else ""))


if __name__ == "__main__":
    main()

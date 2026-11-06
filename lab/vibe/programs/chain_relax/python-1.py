import sys
import math


def main():
    if len(sys.argv) != 4:
        sys.exit(1)

    nums = []
    for a in sys.argv[1:]:
        if not a:
            sys.exit(1)
        for ch in a:
            if ch < '0' or ch > '9':
                sys.exit(1)
        nums.append(int(a))

    N, T, SEED = nums
    if N < 1 or N > 10000000:
        sys.exit(1)
    if T < 0 or T > 1000000:
        sys.exit(1)
    if SEED < 0 or SEED > 18446744073709551615:
        sys.exit(1)

    mask = (1 << 64) - 1
    mul = 6364136223846793005
    inc = 1442695040888963407

    x = SEED
    h = [0.0] * N
    for i in range(N):
        x = (x * mul + inc) & mask
        h[i] = (((x >> 33) % 2001) - 1000) / 64.0

    sqrt = math.sqrt

    for s in range(1, T + 1):
        if s & 1:
            prev = h[N - 1]
            for i in range(N):
                c = h[i]
                nxt = h[i + 1] if i + 1 < N else h[0]
                d = (prev + nxt) - (c + c)
                g = d / (1.0 + sqrt(d * d + 0.0625))
                nh = c + 0.375 * g
                h[i] = nh
                prev = nh
        else:
            nxt = h[0]
            for i in range(N - 1, -1, -1):
                c = h[i]
                prev = h[i - 1] if i > 0 else h[N - 1]
                d = (prev + nxt) - (c + c)
                g = d / (1.0 + sqrt(d * d + 0.0625))
                nh = c + 0.375 * g
                h[i] = nh
                nxt = nh

    total = 0.0
    energy = 0.0
    for i in range(N - 1):
        hi = h[i]
        total = total + hi
        t = h[i + 1] - hi
        energy = energy + t * t
    hi = h[N - 1]
    total = total + hi
    t = h[0] - hi
    energy = energy + t * t

    mn = min(h)
    mx = max(h)

    def fmt(v):
        s = format(v, '.9f')
        if s[0] == '-':
            if s[1:].replace('.', '').strip('0') == '':
                return '0.000000000'
        return s

    out = []
    out.append('sum ' + fmt(total) + '\n')
    out.append('energy ' + fmt(energy) + '\n')
    out.append('min ' + fmt(mn) + '\n')
    out.append('max ' + fmt(mx) + '\n')
    out.append('first ' + fmt(h[0]) + '\n')
    out.append('middle ' + fmt(h[N // 2]) + '\n')
    out.append('last ' + fmt(h[N - 1]) + '\n')
    sys.stdout.write(''.join(out))


if __name__ == '__main__':
    main()

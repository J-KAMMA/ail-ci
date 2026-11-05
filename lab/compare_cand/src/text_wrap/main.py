import sys

MOD = 1000000007


def main():
    data = sys.stdin.buffer.read()
    n = len(data)
    e = 0
    while e < n and data[e] != 10:
        e += 1
    if e < 1 or e > 3:
        return 2
    w = 0
    for k in range(e):
        c = data[k]
        if c < 48 or c > 57:
            return 2
        w = w * 10 + c - 48
    if w < 10 or w > 200:
        return 2

    pos = e + 1 if e < n else n
    paragraphs = 0
    lines = 0
    words = 0
    longest = 0
    h = 0
    emitted_any = False
    in_para = False
    first_line = False
    cur_len = 0

    while True:
        e = pos
        while e < n and data[e] != 10:
            e += 1
        a = pos
        blank = True
        k = a
        while k < e:
            if data[k] != 32:
                blank = False
                break
            k += 1
        if blank:
            if in_para:
                in_para = False
                cur_len = 0
        else:
            k = a
            while k < e:
                c = data[k]
                if c == 32 or c == 9:
                    k += 1
                    continue
                ws = k
                while k < e:
                    c = data[k]
                    if c == 32 or c == 9:
                        break
                    k += 1
                wl = k - ws
                words += 1
                if not in_para:
                    in_para = True
                    first_line = True
                    paragraphs += 1
                if cur_len == 0:
                    if first_line:
                        if emitted_any:
                            h = (h * 131 + 10) % MOD
                            h = (h * 131 + 10) % MOD
                        emitted_any = True
                        first_line = False
                    else:
                        h = (h * 131 + 10) % MOD
                    lines += 1
                    cur_len = wl
                elif cur_len + 1 + wl <= w:
                    h = (h * 131 + 32) % MOD
                    cur_len += 1 + wl
                else:
                    h = (h * 131 + 10) % MOD
                    lines += 1
                    cur_len = wl
                p = ws
                while p < k:
                    h = (h * 131 + data[p]) % MOD
                    p += 1
                if cur_len > longest:
                    longest = cur_len
        if e >= n:
            break
        pos = e + 1

    sys.stdout.write("paragraphs %d lines %d words %d longest %d hash %d\n"
                     % (paragraphs, lines, words, longest, h))
    return 0


sys.exit(main())

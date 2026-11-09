import sys

LEVEL_NAMES = ["TRACE", "DEBUG", "INFO", "WARN", "ERROR", "FATAL"]
LEVEL_B = [b"TRACE", b"DEBUG", b"INFO", b"WARN", b"ERROR", b"FATAL"]


def cp_count(b):
    # Count code points in a byte string. Valid UTF-8 sequences count as one
    # code point each; every invalid byte counts as one code point (mirrors
    # surrogateescape behaviour).
    n = 0
    i = 0
    L = len(b)
    while i < L:
        n += 1
        c = b[i]
        if c < 0x80:
            i += 1
            continue
        k = 0
        lo = 0x80
        hi = 0xBF
        if 0xC2 <= c <= 0xDF:
            k = 1
        elif c == 0xE0:
            k = 2
            lo = 0xA0
        elif 0xE1 <= c <= 0xEC or 0xEE <= c <= 0xEF:
            k = 2
        elif c == 0xED:
            k = 2
            hi = 0x9F
        elif c == 0xF0:
            k = 3
            lo = 0x90
        elif 0xF1 <= c <= 0xF3:
            k = 3
        elif c == 0xF4:
            k = 3
            hi = 0x8F
        ok = False
        if k > 0 and i + k < L:
            b1 = b[i + 1]
            if lo <= b1 <= hi:
                ok = True
                j = 2
                while j <= k:
                    cj = b[i + j]
                    if cj < 0x80 or cj > 0xBF:
                        ok = False
                        break
                    j += 1
        if ok:
            i += k + 1
        else:
            i += 1
    return n


def main():
    data = sys.stdin.buffer.read()

    counts = [0] * 6
    chars = [0] * 6
    longest = [0] * 6

    good = 0
    bad = 0

    for line in data.split(b"\n"):
        if line.endswith(b"\r"):
            line = line[:-1]
        if len(line) == 0:
            continue

        if not line.startswith(b"["):
            bad += 1
            continue

        idx = line.find(b"]")
        if idx < 0:
            bad += 1
            continue

        lv = line[1:idx]
        li = -1
        for k in range(6):
            if LEVEL_B[k] == lv:
                li = k
                break
        if li < 0:
            bad += 1
            continue

        rest = line[idx + 1:]
        if len(rest) == 0:
            msg = b""
        elif rest.startswith(b" "):
            msg = rest[1:]
        else:
            bad += 1
            continue

        n = cp_count(msg)
        good += 1
        counts[li] += 1
        chars[li] += n
        if n > longest[li]:
            longest[li] = n

    out = []
    out.append("lines " + str(good) + " bad " + str(bad) + "\n")
    for k in range(6):
        out.append(
            "level " + LEVEL_NAMES[k]
            + " count " + str(counts[k])
            + " chars " + str(chars[k])
            + " longest " + str(longest[k])
            + "\n"
        )
    sys.stdout.write("".join(out))
    sys.exit(0)


main()

import sys

LEVELS = [b"TRACE", b"DEBUG", b"INFO", b"WARN", b"ERROR", b"FATAL"]


def cp_len(msg):
    # Count Unicode code points in UTF-8 bytes: every byte that is not
    # a continuation byte (10xxxxxx) starts a new code point.
    n = 0
    for b in msg:
        if (b & 0xC0) != 0x80:
            n += 1
    return n


def main():
    data = sys.stdin.buffer.read()
    lines = data.split(b"\n")

    count = [0] * 6
    chars = [0] * 6
    longest = [0] * 6

    good = 0
    bad = 0

    for line in lines:
        if line.endswith(b"\r"):
            line = line[:-1]
        if len(line) == 0:
            continue
        if line[0:1] != b"[":
            bad += 1
            continue
        idx = line.find(b"]")
        if idx < 0:
            bad += 1
            continue
        lv = line[1:idx]
        if lv not in LEVELS:
            bad += 1
            continue
        li = LEVELS.index(lv)
        rest = line[idx + 1:]
        if len(rest) == 0:
            msg = b""
        elif rest[0:1] == b" ":
            msg = rest[1:]
        else:
            bad += 1
            continue

        ml = cp_len(msg)
        good += 1
        count[li] += 1
        chars[li] += ml
        if ml > longest[li]:
            longest[li] = ml

    out = []
    out.append("lines " + str(good) + " bad " + str(bad) + "\n")
    for i in range(6):
        out.append(
            "level " + LEVELS[i].decode("ascii")
            + " count " + str(count[i])
            + " chars " + str(chars[i])
            + " longest " + str(longest[i])
            + "\n"
        )
    sys.stdout.write("".join(out))


if __name__ == "__main__":
    main()
    sys.exit(0)

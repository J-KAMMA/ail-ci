import sys

LEVELS = ["TRACE", "DEBUG", "INFO", "WARN", "ERROR", "FATAL"]
LEVEL_BYTES = [b"TRACE", b"DEBUG", b"INFO", b"WARN", b"ERROR", b"FATAL"]


def main():
    data = sys.stdin.buffer.read()
    lines = data.split(b"\n")

    by_level = {}
    for i in range(6):
        by_level[LEVEL_BYTES[i]] = i

    counts = [0, 0, 0, 0, 0, 0]
    totals = [0, 0, 0, 0, 0, 0]
    longest = [0, 0, 0, 0, 0, 0]

    good = 0
    bad = 0

    for raw in lines:
        if raw.endswith(b"\r"):
            raw = raw[:-1]
        if len(raw) == 0:
            continue

        if not raw.startswith(b"["):
            bad += 1
            continue

        idx = raw.find(b"]")
        if idx < 0:
            bad += 1
            continue

        lv = raw[1:idx]
        if lv not in by_level:
            bad += 1
            continue
        k = by_level[lv]

        rest = raw[idx + 1:]
        if len(rest) == 0:
            msg = b""
        elif rest.startswith(b" "):
            msg = rest[1:]
        else:
            bad += 1
            continue

        n = 0
        i = 0
        m = len(msg)
        while i < m:
            b = msg[i]
            if (b & 192) != 128:
                n += 1
            i += 1

        good += 1
        counts[k] += 1
        totals[k] += n
        if n > longest[k]:
            longest[k] = n

    out = ["lines %d bad %d\n" % (good, bad)]
    for i in range(6):
        out.append("level %s count %d chars %d longest %d\n"
                   % (LEVELS[i], counts[i], totals[i], longest[i]))
    sys.stdout.write("".join(out))


main()

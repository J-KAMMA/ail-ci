import sys

LEVELS = ["TRACE", "DEBUG", "INFO", "WARN", "ERROR", "FATAL"]


def main():
    data = sys.stdin.buffer.read().decode("utf-8", errors="replace")
    counts = {lv: 0 for lv in LEVELS}
    chars = {lv: 0 for lv in LEVELS}
    longest = {lv: 0 for lv in LEVELS}
    good = 0
    bad = 0

    for line in data.split("\n"):
        if line.endswith("\r"):
            line = line[:-1]
        if line == "":
            continue

        if not line.startswith("["):
            bad += 1
            continue
        idx = line.find("]")
        if idx == -1:
            bad += 1
            continue
        level = line[1:idx]
        if level not in counts:
            bad += 1
            continue
        rest = line[idx + 1:]
        if rest == "":
            message = ""
        elif rest[0] == " ":
            message = rest[1:]
        else:
            bad += 1
            continue

        mlen = len(message)
        good += 1
        counts[level] += 1
        chars[level] += mlen
        if mlen > longest[level]:
            longest[level] = mlen

    out = [f"lines {good} bad {bad}\n"]
    for lv in LEVELS:
        out.append(
            f"level {lv} count {counts[lv]} chars {chars[lv]} longest {longest[lv]}\n"
        )
    sys.stdout.write("".join(out))
    sys.stdout.flush()


if __name__ == "__main__":
    main()
    sys.exit(0)

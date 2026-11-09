import sys


LEVELS = ["TRACE", "DEBUG", "INFO", "WARN", "ERROR", "FATAL"]


def main():
    data = sys.stdin.buffer.read().decode("utf-8", errors="surrogateescape")
    counts = {lvl: 0 for lvl in LEVELS}
    chars = {lvl: 0 for lvl in LEVELS}
    longest = {lvl: 0 for lvl in LEVELS}
    good = 0
    bad = 0

    for raw in data.split("\n"):
        line = raw[:-1] if raw.endswith("\r") else raw
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

        length = len(message)
        good += 1
        counts[level] += 1
        chars[level] += length
        if length > longest[level]:
            longest[level] = length

    out = [f"lines {good} bad {bad}\n"]
    for lvl in LEVELS:
        out.append(
            f"level {lvl} count {counts[lvl]} chars {chars[lvl]} longest {longest[lvl]}\n"
        )
    sys.stdout.write("".join(out))
    sys.stdout.flush()


if __name__ == "__main__":
    main()

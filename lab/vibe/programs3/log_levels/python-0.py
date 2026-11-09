import sys


def main() -> None:
    data = sys.stdin.buffer.read().decode("utf-8", errors="replace")

    levels = ["TRACE", "DEBUG", "INFO", "WARN", "ERROR", "FATAL"]
    valid = set(levels)

    counts = {lvl: 0 for lvl in levels}
    chars = {lvl: 0 for lvl in levels}
    longest = {lvl: 0 for lvl in levels}

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
        if level not in valid:
            bad += 1
            continue

        rest = line[idx + 1:]
        if rest:
            if rest[0] != " ":
                bad += 1
                continue
            message = rest[1:]
        else:
            message = ""

        good += 1
        counts[level] += 1
        length = len(message)
        chars[level] += length
        if length > longest[level]:
            longest[level] = length

    out = [f"lines {good} bad {bad}"]
    for lvl in levels:
        out.append(
            f"level {lvl} count {counts[lvl]} chars {chars[lvl]} longest {longest[lvl]}"
        )

    sys.stdout.write("\n".join(out) + "\n")


main()

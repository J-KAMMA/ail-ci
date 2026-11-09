import sys

LIMIT = 1000000000000


def main():
    data = sys.stdin.buffer.read().decode("utf-8", "replace")

    counts: dict[str, int] = {}
    totals: dict[str, int] = {}
    bad = 0

    for line in data.split("\n"):
        if not line.strip():
            continue

        parts = line.split()
        if len(parts) != 3:
            bad += 1
            continue

        name = parts[0]
        score_token = parts[2]

        valid_digits = len(score_token) > 0
        if valid_digits:
            for ch in score_token:
                if ch < "0" or ch > "9":
                    valid_digits = False
                    break

        if not valid_digits:
            bad += 1
            continue

        digits = score_token.lstrip("0")
        if not digits:
            score = 0
        elif len(digits) > 13:
            bad += 1
            continue
        else:
            score = int(digits)
            if score > LIMIT:
                bad += 1
                continue

        if name in counts:
            counts[name] = counts[name] + 1
            totals[name] = totals[name] + score
        else:
            counts[name] = 1
            totals[name] = score

    rows: list[tuple[str, int, int, int]] = []
    for name in counts:
        c = counts[name]
        s = totals[name]
        rows.append((name, c, s, s // c))

    rows.sort(key=lambda row: (-row[3], row[0].encode("utf-8")))

    out: list[str] = ["bad " + str(bad) + "\n"]
    for name, c, s, a in rows:
        out.append(name + " count " + str(c) + " sum " + str(s) + " avg " + str(a) + "\n")

    sys.stdout.write("".join(out))
    return 0


if __name__ == "__main__":
    sys.exit(main())

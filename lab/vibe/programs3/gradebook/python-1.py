import sys

MAX_SCORE = 10**12


def parse_score(token):
    if not token:
        return None
    for ch in token:
        if ch < '0' or ch > '9':
            return None
    digits = token.lstrip('0')
    if not digits:
        return 0
    if len(digits) > 13:
        return None
    value = int(digits)
    if value > MAX_SCORE:
        return None
    return value


def main():
    counts = {}
    sums = {}

    bad = 0

    for line in sys.stdin:
        parts = line.split()
        if not parts:
            continue
        if len(parts) != 3:
            bad += 1
            continue

        name, _assignment, score_token = parts
        score = parse_score(score_token)
        if score is None:
            bad += 1
            continue

        counts[name] = counts.get(name, 0) + 1
        sums[name] = sums.get(name, 0) + score

    rows = []
    for name, count in counts.items():
        total = sums[name]
        avg = total // count
        rows.append((-avg, name.encode('utf-8', 'surrogateescape'), name, count, total, avg))

    rows.sort(key=lambda row: (row[0], row[1]))

    out = ["bad %d" % bad]
    for _neg_avg, _sort_name, name, count, total, avg in rows:
        out.append("%s count %d sum %d avg %d" % (name, count, total, avg))

    sys.stdout.write("\n".join(out) + "\n")


if __name__ == "__main__":
    main()

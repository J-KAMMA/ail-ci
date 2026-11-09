import sys

LIMIT = 10**12


def parse_score(token):
    if not token.isdigit():
        return None

    value = token.lstrip(b"0")
    if not value:
        return 0

    if len(value) > 13:
        return None
    if len(value) == 13 and value > b"1000000000000":
        return None

    return int(value)


def main():
    bad = 0
    stats = {}

    for line in sys.stdin.buffer:
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

        if name in stats:
            count, total = stats[name]
            stats[name] = (count + 1, total + score)
        else:
            stats[name] = (1, score)

    output = [b"bad %d\n" % bad]

    ordered = sorted(
        stats.items(),
        key=lambda item: (-(item[1][1] // item[1][0]), item[0]),
    )

    for name, (count, total) in ordered:
        output.append(
            name + b" count %d sum %d avg %d\n" % (count, total, total // count)
        )

    sys.stdout.buffer.write(b"".join(output))


if __name__ == "__main__":
    main()

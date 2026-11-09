import sys


def main():
    data = sys.stdin.buffer.read()
    bad = 0
    stats = {}  # name(bytes) -> [count, sum]
    limit = 10 ** 12

    for line in data.split(b'\n'):
        toks = line.split()  # ASCII whitespace split on bytes
        if not toks:
            continue
        if len(toks) != 3:
            bad += 1
            continue
        name, _assignment, score = toks
        if not score.isdigit():  # bytes.isdigit is ASCII-only
            bad += 1
            continue
        value = int(score)
        if value > limit:
            bad += 1
            continue
        entry = stats.get(name)
        if entry is None:
            stats[name] = [1, value]
        else:
            entry[0] += 1
            entry[1] += value

    rows = []
    for name, (count, total) in stats.items():
        avg = total // count
        rows.append((avg, name, count, total))
    rows.sort(key=lambda r: (-r[0], r[1]))

    out = [b"bad %d\n" % bad]
    for avg, name, count, total in rows:
        out.append(name + b" count %d sum %d avg %d\n" % (count, total, avg))

    sys.stdout.buffer.write(b"".join(out))
    sys.stdout.buffer.flush()
    return 0


if __name__ == "__main__":
    sys.exit(main())

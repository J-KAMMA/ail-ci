import sys


def main():
    data = sys.stdin.buffer.read().decode("utf-8", "surrogateescape")
    limit = 10 ** 12
    bad = 0
    stats = {}  # name -> [count, sum]

    for line in data.split("\n"):
        if not line.strip():
            continue
        toks = line.split()
        if len(toks) != 3:
            bad += 1
            continue
        name, _asg, sc = toks
        if not sc or not all("0" <= c <= "9" for c in sc):
            bad += 1
            continue
        digits = sc.lstrip("0")
        if len(digits) > 13:
            bad += 1
            continue
        value = int(digits) if digits else 0
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

    rows.sort(key=lambda r: (-r[0], r[1].encode("utf-8", "surrogateescape")))

    out = bytearray()
    out += ("bad %d\n" % bad).encode("ascii")
    for avg, name, count, total in rows:
        out += name.encode("utf-8", "surrogateescape")
        out += (" count %d sum %d avg %d\n" % (count, total, avg)).encode("ascii")

    sys.stdout.buffer.write(bytes(out))
    sys.stdout.buffer.flush()
    sys.exit(0)


if __name__ == "__main__":
    main()

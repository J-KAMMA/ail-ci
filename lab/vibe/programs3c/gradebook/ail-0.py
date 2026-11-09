import sys


MAX_SCORE = 1000000000000


def parse_score(s):
    if len(s) == 0:
        return -1
    v = 0
    for ch in s:
        if ch < 48 or ch > 57:
            return -1
        v = v * 10 + (ch - 48)
        if v > MAX_SCORE:
            return -1
    return v


def main():
    data = sys.stdin.buffer.read()
    bad = 0
    counts = {}
    sums = {}
    for line in data.split(b'\n'):
        parts = line.split()
        if len(parts) == 0:
            continue
        if len(parts) != 3:
            bad += 1
            continue
        name = parts[0]
        score = parse_score(parts[2])
        if score < 0:
            bad += 1
            continue
        if name in counts:
            counts[name] = counts[name] + 1
            sums[name] = sums[name] + score
        else:
            counts[name] = 1
            sums[name] = score

    names = list(counts.keys())
    names.sort(key=lambda n: (-(sums[n] // counts[n]), n))

    out = [b'bad ' + str(bad).encode('ascii') + b'\n']
    for n in names:
        c = counts[n]
        s = sums[n]
        out.append(
            n + b' count ' + str(c).encode('ascii')
            + b' sum ' + str(s).encode('ascii')
            + b' avg ' + str(s // c).encode('ascii')
            + b'\n'
        )
    sys.stdout.buffer.write(b''.join(out))
    sys.stdout.flush()


main()

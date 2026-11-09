import sys


def is_valid(score):
    if len(score) == 0:
        return False
    for c in score:
        if c < '0' or c > '9':
            return False
    return True


def main():
    data = sys.stdin.buffer.read().decode('utf-8', 'replace')
    limit = 10 ** 12
    bad = 0
    counts = {}
    sums = {}

    for line in data.split('\n'):
        parts = line.split()
        if len(parts) == 0:
            continue
        if len(parts) != 3:
            bad += 1
            continue
        name = parts[0]
        score = parts[2]
        if not is_valid(score):
            bad += 1
            continue
        v = int(score)
        if v > limit:
            bad += 1
            continue
        if name in counts:
            counts[name] += 1
            sums[name] += v
        else:
            counts[name] = 1
            sums[name] = v

    names = list(counts.keys())
    names.sort()
    avgs = {}
    for n in names:
        avgs[n] = sums[n] // counts[n]
    names.sort(key=lambda n: -avgs[n])

    out = ["bad %d\n" % bad]
    for n in names:
        out.append("%s count %d sum %d avg %d\n" % (n, counts[n], sums[n], avgs[n]))
    sys.stdout.write("".join(out))
    sys.stdout.flush()
    sys.exit(0)


main()

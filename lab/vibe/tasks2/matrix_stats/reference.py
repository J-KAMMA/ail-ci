"""Reference implementation of matrix_stats (see spec.md): reference.py < matrix"""
import sys

MINI = -(1 << 63)
MAXI = (1 << 63) - 1


def uint(s):
    if not s or any(c < '0' or c > '9' for c in s):
        return None
    return int(s)


def sint(s):
    body = s[1:] if s[:1] == '-' else s
    if not body or any(c < '0' or c > '9' for c in body):
        return None
    v = int(s)
    return v if MINI <= v <= MAXI else None


def fail():
    sys.stdout.write('error\n')
    return 2


def main():
    data = sys.stdin.buffer.read().decode('utf8')
    if data == '':
        return fail()
    lines = data.split('\n')
    if lines and lines[-1] == '':
        lines.pop()
    head = lines[0].split()
    if len(head) != 2:
        return fail()
    r, c = uint(head[0]), uint(head[1])
    if r is None or c is None or r > 10000 or c > 10000 or r * c > 1000000:
        return fail()
    if len(lines) - 1 != r:
        return fail()
    rowsum = []
    colsum = [0] * c
    best = None
    for i in range(r):
        raw = lines[i + 1]
        if raw.endswith('\r'):
            raw = raw[:-1]
        toks = raw.split()
        if len(toks) != c:
            return fail()
        total = 0
        for j, t in enumerate(toks):
            v = sint(t)
            if v is None:
                return fail()
            total += v
            colsum[j] += v
            if best is None or v > best[0]:
                best = (v, i, j)
        rowsum.append(total)
    out = ['row %d %d' % (i, rowsum[i]) for i in range(r)]
    out += ['col %d %d' % (j, colsum[j]) for j in range(c)]
    if best is None:
        out.append('max none')
    else:
        out.append('max %d at %d %d' % best)
    sys.stdout.write('\n'.join(out) + '\n')
    return 0


if __name__ == '__main__':
    sys.exit(main())

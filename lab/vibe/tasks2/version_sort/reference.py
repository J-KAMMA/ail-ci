"""Reference implementation of version_sort (see spec.md): reference.py < versions"""
import functools
import re
import sys

MAXI = (1 << 63) - 1
NUM = re.compile(r'^(0|[0-9]+)$')
VER = re.compile(r'^([0-9]+)\.([0-9]+)\.([0-9]+)(?:-([0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*))?'
                 r'(?:\+([0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*))?$')


def num(s):
    v = int(s)
    return v if v <= MAXI else None


def parse(line):
    m = VER.match(line)
    if not m:
        return None
    maj, mi, pa, pre, _build = m.groups()
    a, b, c = num(maj), num(mi), num(pa)
    if a is None or b is None or c is None:
        return None
    ids = None
    if pre is not None:
        ids = []
        for part in pre.split('.'):
            if part.isdigit():
                v = num(part)
                if v is None:
                    return None
                ids.append((0, v, ''))
            else:
                ids.append((1, 0, part))
    return a, b, c, ids


def cmp_pre(x, y):
    if x is None and y is None:
        return 0
    if x is None:
        return 1
    if y is None:
        return -1
    for a, b in zip(x, y):
        if a != b:
            return -1 if a < b else 1
    return (len(x) > len(y)) - (len(x) < len(y))


def cmp_ver(p, q):
    for i in range(3):
        if p[i] != q[i]:
            return -1 if p[i] < q[i] else 1
    c = cmp_pre(p[3], q[3])
    if c:
        return c
    return 0


def main():
    text = sys.stdin.buffer.read().decode('utf8')
    lines = text.split('\n')
    if lines and lines[-1] == '':
        lines.pop()
    bad = 0
    rows = []
    for raw in lines:
        line = raw[:-1] if raw.endswith('\r') else raw
        if line == '':
            continue
        key = parse(line)
        if key is None:
            bad += 1
            continue
        rows.append((key, line))

    def compare(x, y):
        c = cmp_ver(x[0], y[0])
        if c:
            return c
        return (x[1] > y[1]) - (x[1] < y[1])

    rows.sort(key=functools.cmp_to_key(compare))
    out = ['bad %d sorted %d' % (bad, len(rows))]
    out.extend(line for _key, line in rows)
    sys.stdout.write('\n'.join(out) + '\n')
    return 0


if __name__ == '__main__':
    sys.exit(main())

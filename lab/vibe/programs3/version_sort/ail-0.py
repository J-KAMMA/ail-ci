import sys
from functools import cmp_to_key

MAXS = b'9223372036854775807'


def parse_num(d):
    if not d:
        return None
    for c in d:
        if c < 48 or c > 57:
            return None
    t = d.lstrip(b'0')
    if t == b'':
        return 0
    if len(t) > 19:
        return None
    if len(t) == 19 and t > MAXS:
        return None
    return int(t)


def is_id(b):
    if not b:
        return False
    for c in b:
        if 48 <= c <= 57:
            continue
        if 65 <= c <= 90:
            continue
        if 97 <= c <= 122:
            continue
        if c == 45:
            continue
        return False
    return True


def parse_line(line):
    i = line.find(b'+')
    if i >= 0:
        core = line[:i]
        build = line[i + 1:]
        for seg in build.split(b'.'):
            if not is_id(seg):
                return None
    else:
        core = line

    j = core.find(b'-')
    if j >= 0:
        ver = core[:j]
        pre = core[j + 1:]
        pre_parts = pre.split(b'.')
        for seg in pre_parts:
            if not is_id(seg):
                return None
    else:
        ver = core
        pre_parts = None

    parts = ver.split(b'.')
    if len(parts) != 3:
        return None

    nums = []
    for p in parts:
        v = parse_num(p)
        if v is None:
            return None
        nums.append(v)

    if pre_parts is not None:
        ids = []
        for seg in pre_parts:
            if seg.isdigit():
                v = parse_num(seg)
                if v is None:
                    return None
                ids.append((0, v))
            else:
                ids.append((1, seg))
    else:
        ids = None

    return (nums[0], nums[1], nums[2], ids, line)


def cmp_rec(a, b):
    for k in range(3):
        if a[k] != b[k]:
            return -1 if a[k] < b[k] else 1

    pa = a[3]
    pb = b[3]

    if pa is None and pb is None:
        pass
    elif pa is None:
        return 1
    elif pb is None:
        return -1
    else:
        n = len(pa)
        if len(pb) < n:
            n = len(pb)
        for k in range(n):
            x = pa[k]
            y = pb[k]
            if x[0] != y[0]:
                return -1 if x[0] < y[0] else 1
            if x[1] != y[1]:
                return -1 if x[1] < y[1] else 1
        if len(pa) != len(pb):
            return -1 if len(pa) < len(pb) else 1

    if a[4] != b[4]:
        return -1 if a[4] < b[4] else 1
    return 0


def main():
    data = sys.stdin.buffer.read()
    lines = data.split(b'\n')

    recs = []
    bad = 0

    for raw in lines:
        if raw.endswith(b'\r'):
            raw = raw[:-1]
        if raw == b'':
            continue
        r = parse_line(raw)
        if r is None:
            bad += 1
        else:
            recs.append(r)

    recs.sort(key=cmp_to_key(cmp_rec))

    out = sys.stdout.buffer
    out.write(b'bad %d sorted %d\n' % (bad, len(recs)))
    for r in recs:
        out.write(r[4])
        out.write(b'\n')
    sys.exit(0)


main()

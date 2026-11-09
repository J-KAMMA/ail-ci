import sys

DIGITS = '0123456789'
IDCH = '0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz-'
MAXS = '9223372036854775807'


def all_in(s, allowed):
    for c in s:
        if c not in allowed:
            return False
    return True


def strip_zeros(s):
    t = s.lstrip('0')
    if t == '':
        t = '0'
    return t


def in_range(t):
    return len(t) < 19 or (len(t) == 19 and t <= MAXS)


def numkey(s):
    t = strip_zeros(s)
    return (len(t), t)


def parse_idents(s):
    res = []
    for ident in s.split('.'):
        if ident == '' or not all_in(ident, IDCH):
            return None
        if all_in(ident, DIGITS):
            if not in_range(strip_zeros(ident)):
                return None
            res.append((0, numkey(ident)))
        else:
            res.append((1, ident))
    return res


def parse(line):
    nplus = line.count('+')
    if nplus > 1:
        return None
    build = None
    if nplus == 1:
        i = line.index('+')
        build = line[i + 1:]
        line = line[:i]
    pre = None
    if '-' in line:
        i = line.index('-')
        pre = line[i + 1:]
        line = line[:i]
    parts = line.split('.')
    if len(parts) != 3:
        return None
    nums = []
    for p in parts:
        if p == '' or not all_in(p, DIGITS):
            return None
        if not in_range(strip_zeros(p)):
            return None
        nums.append(numkey(p))
    ids = ()
    if pre is not None:
        r = parse_idents(pre)
        if r is None:
            return None
        ids = tuple(r)
    if build is not None:
        if parse_idents(build) is None:
            return None
    flag = 0 if pre is not None else 1
    return (nums[0], nums[1], nums[2], flag, ids)


def main():
    data = sys.stdin.buffer.read().decode('latin-1')
    lines = data.split('\n')
    bad = 0
    items = []
    for raw in lines:
        line = raw
        if line.endswith('\r'):
            line = line[:-1]
        if line == '':
            continue
        key = parse(line)
        if key is None:
            bad += 1
            continue
        items.append(key + (line,))
    items.sort()
    out = ['bad %d sorted %d\n' % (bad, len(items))]
    for key in items:
        out.append(key[5] + '\n')
    sys.stdout.write(''.join(out))


main()

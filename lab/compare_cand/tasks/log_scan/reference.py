"""Reference implementation of log_scan (see spec.md): reference.py < access.log"""
import sys

MONTHS = frozenset((b'Jan', b'Feb', b'Mar', b'Apr', b'May', b'Jun',
                    b'Jul', b'Aug', b'Sep', b'Oct', b'Nov', b'Dec'))
METHODS = frozenset((b'GET', b'POST', b'PUT', b'DELETE'))
EMPTY = b'lines 0 bad 0\nstatus 2xx 0 3xx 0 4xx 0 5xx 0\nbytes 0\nips 0\n'


def two(line, i, lo, hi):
    if i + 2 > len(line):
        return None
    a = line[i] - 48
    b = line[i + 1] - 48
    if a < 0 or a > 9 or b < 0 or b > 9:
        return None
    v = a * 10 + b
    if v < lo or v > hi:
        return None
    return v


def four(line, i):
    if i + 4 > len(line):
        return None
    v = 0
    for k in range(4):
        c = line[i + k] - 48
        if c < 0 or c > 9:
            return None
        v = v * 10 + c
    return v


def octet(line, i):
    n = len(line)
    start = i
    v = 0
    while i < n and i - start < 3 and 48 <= line[i] <= 57:
        v = v * 10 + line[i] - 48
        i += 1
    if i == start or v > 255:
        return None
    return v, i


def path_ok(p):
    n = len(p)
    if n < 1 or n > 64 or p[0] != 47:
        return False
    for c in p:
        if 65 <= c <= 90 or 97 <= c <= 122 or 48 <= c <= 57:
            continue
        if c == 47 or c == 46 or c == 95 or c == 45:
            continue
        return False
    return True


def parse(line):
    n = len(line)
    i = 0
    ip = 0
    for k in range(4):
        if k:
            if i >= n or line[i] != 46:
                return None
            i += 1
        r = octet(line, i)
        if r is None:
            return None
        v, i = r
        ip = (ip << 8) | v
    if line[i:i + 6] != b' - - [':
        return None
    i += 6
    if two(line, i, 1, 31) is None:
        return None
    i += 2
    if i >= n or line[i] != 47:
        return None
    i += 1
    if line[i:i + 3] not in MONTHS:
        return None
    i += 3
    if i >= n or line[i] != 47:
        return None
    i += 1
    if four(line, i) is None:
        return None
    i += 4
    if i >= n or line[i] != 58:
        return None
    i += 1
    hh = two(line, i, 0, 23)
    if hh is None:
        return None
    i += 2
    if i >= n or line[i] != 58:
        return None
    i += 1
    if two(line, i, 0, 59) is None:
        return None
    i += 2
    if i >= n or line[i] != 58:
        return None
    i += 1
    if two(line, i, 0, 59) is None:
        return None
    i += 2
    if line[i:i + 7] != b' +0000]':
        return None
    i += 7
    if i >= n or line[i] != 32:
        return None
    i += 1
    if i >= n or line[i] != 34:
        return None
    i += 1
    ms = i
    while i < n and line[i] != 32:
        i += 1
    if i >= n or line[ms:i] not in METHODS:
        return None
    i += 1
    ps = i
    while i < n and line[i] != 32:
        i += 1
    if i >= n:
        return None
    path = line[ps:i]
    if not path_ok(path):
        return None
    i += 1
    if line[i:i + 8] != b'HTTP/1.1':
        return None
    i += 8
    if i >= n or line[i] != 34:
        return None
    i += 1
    if i >= n or line[i] != 32:
        return None
    i += 1
    if i + 3 > n:
        return None
    s0 = line[i] - 48
    s1 = line[i + 1] - 48
    s2 = line[i + 2] - 48
    if s0 < 0 or s0 > 9 or s1 < 0 or s1 > 9 or s2 < 0 or s2 > 9:
        return None
    status = s0 * 100 + s1 * 10 + s2
    if status < 100 or status > 599:
        return None
    i += 3
    if i >= n or line[i] != 32:
        return None
    i += 1
    if i >= n:
        return None
    if line[i] == 45:
        if i + 1 != n:
            return None
        nb = 0
    else:
        if line[i] < 48 or line[i] > 57:
            return None
        nb = 0
        while i < n:
            c = line[i]
            if c < 48 or c > 57:
                return None
            nb = nb * 10 + c - 48
            if nb > 1000000000000:
                return None
            i += 1
    return ip, hh, status, nb, path


def main():
    data = sys.stdin.buffer.read()
    if not data:
        sys.stdout.buffer.write(EMPTY)
        return 0
    lines = data.split(b'\n')
    if lines[-1] == b'':
        lines.pop()
    good = 0
    bad = 0
    status_count = [0, 0, 0, 0, 0, 0]
    total_bytes = 0
    hour_count = [0] * 24
    hour_bytes = [0] * 24
    paths = {}
    ips = set()
    for line in lines:
        r = parse(line)
        if r is None:
            bad += 1
            continue
        ip, hh, status, nb, path = r
        good += 1
        total_bytes += nb
        cls = status // 100
        if 2 <= cls <= 5:
            status_count[cls] += 1
        hour_count[hh] += 1
        hour_bytes[hh] += nb
        e = paths.get(path)
        if e is None:
            paths[path] = [1, nb]
        else:
            e[0] += 1
            e[1] += nb
        ips.add(ip)
    out = ['lines %d bad %d' % (good, bad),
           'status 2xx %d 3xx %d 4xx %d 5xx %d'
           % (status_count[2], status_count[3], status_count[4], status_count[5]),
           'bytes %d' % total_bytes]
    for h in range(24):
        if hour_count[h]:
            out.append('hour %02d %d %d' % (h, hour_count[h], hour_bytes[h]))
    order = sorted(paths.items(), key=lambda kv: (-kv[1][0], kv[0]))
    for p, (c, b) in order[:10]:
        out.append('path %s %d %d' % (p.decode(), c, b))
    out.append('ips %d' % len(ips))
    sys.stdout.buffer.write(('\n'.join(out) + '\n').encode())
    return 0


if __name__ == '__main__':
    sys.exit(main())

import sys

MONTHS = frozenset(('Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun',
                    'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'))
METHODS = frozenset(('GET', 'POST', 'PUT', 'DELETE'))
EMPTY = "lines 0 bad 0\nstatus 2xx 0 3xx 0 4xx 0 5xx 0\nbytes 0\nips 0\n"


def two_digits(s):
    if len(s) != 2:
        return None
    a = s[0]
    b = s[1]
    if a < '0' or a > '9' or b < '0' or b > '9':
        return None
    return (ord(a) - 48) * 10 + (ord(b) - 48)


def three_digits(s):
    if len(s) != 3:
        return None
    v = 0
    for c in s:
        if c < '0' or c > '9':
            return None
        v = v * 10 + ord(c) - 48
    return v


def all_digits(s):
    for c in s:
        if c < '0' or c > '9':
            return False
    return True


def ip_value(s):
    parts = s.split('.')
    if len(parts) != 4:
        return -1
    v = 0
    for p in parts:
        if len(p) < 1 or len(p) > 3:
            return -1
        x = 0
        for c in p:
            if c < '0' or c > '9':
                return -1
            x = x * 10 + ord(c) - 48
        if x > 255:
            return -1
        v = (v << 8) | x
    return v


def path_ok(p):
    if len(p) < 1 or len(p) > 64 or p[0] != '/':
        return False
    for c in p:
        if 'A' <= c <= 'Z' or 'a' <= c <= 'z' or '0' <= c <= '9':
            continue
        if c == '/' or c == '.' or c == '_' or c == '-':
            continue
        return False
    return True


def parse_bytes(s):
    if s == '-':
        return 0
    if len(s) < 1:
        return -1
    v = 0
    for c in s:
        if c < '0' or c > '9':
            return -1
        v = v * 10 + ord(c) - 48
        if v > 1000000000000:
            return -1
    return v


def parse(line):
    parts = line.split(' ')
    if len(parts) != 10:
        return None
    ip_s, d1, d2, ts, tz, req, path, proto, status_s, bytes_s = parts
    if d1 != '-' or d2 != '-':
        return None
    if not ts.startswith('[') or tz != '+0000]':
        return None
    date, sep1, clock = ts[1:].partition(':')
    if not sep1:
        return None
    day_s, sep2, rest = date.partition('/')
    if not sep2:
        return None
    mon, sep3, year_s = rest.partition('/')
    if not sep3:
        return None
    hh_s, sep4, rest2 = clock.partition(':')
    if not sep4:
        return None
    mm_s, sep5, ss_s = rest2.partition(':')
    if not sep5:
        return None
    if mon not in MONTHS:
        return None
    day = two_digits(day_s)
    if day is None or day < 1 or day > 31:
        return None
    if len(year_s) != 4 or not all_digits(year_s):
        return None
    hh = two_digits(hh_s)
    if hh is None or hh > 23:
        return None
    mm = two_digits(mm_s)
    if mm is None or mm > 59:
        return None
    ss = two_digits(ss_s)
    if ss is None or ss > 59:
        return None
    if not req.startswith('"') or req[1:] not in METHODS:
        return None
    if proto != 'HTTP/1.1"':
        return None
    if not path_ok(path):
        return None
    status = three_digits(status_s)
    if status is None or status < 100 or status > 599:
        return None
    nb = parse_bytes(bytes_s)
    if nb < 0:
        return None
    ip = ip_value(ip_s)
    if ip < 0:
        return None
    return ip, hh, status, nb, path


def main():
    data = sys.stdin.read()
    if data == '':
        sys.stdout.write(EMPTY)
        return
    lines = data.split('\n')
    if lines[-1] == '':
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
        if cls >= 2 and cls <= 5:
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
    out = ["lines %d bad %d" % (good, bad),
           "status 2xx %d 3xx %d 4xx %d 5xx %d"
           % (status_count[2], status_count[3], status_count[4], status_count[5]),
           "bytes %d" % total_bytes]
    for h in range(24):
        if hour_count[h]:
            out.append("hour %02d %d %d" % (h, hour_count[h], hour_bytes[h]))
    order = sorted(paths.items(), key=lambda kv: (-kv[1][0], kv[0]))
    for p, (c, b) in order[:10]:
        out.append("path %s %d %d" % (p, c, b))
    out.append("ips %d" % len(ips))
    sys.stdout.write("\n".join(out) + "\n")


main()

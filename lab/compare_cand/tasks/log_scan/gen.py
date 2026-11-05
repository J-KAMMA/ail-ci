"""Cases for log_scan (see spec.md). cases(rng) -> (public, hidden, perf). Access log on stdin."""

STDIN = True

MONTHS = ('Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec')
METHODS = ('GET', 'POST', 'PUT', 'DELETE')
PATH_CHARS = 'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789/._-'


def rec(ip, day, mon, year, hh, mm, ss, method, path, status, nbytes):
    return ('%s - - [%02d/%s/%04d:%02d:%02d:%02d +0000] "%s %s HTTP/1.1" %s %s\n'
            % (ip, day, mon, year, hh, mm, ss, method, path, status, nbytes)).encode()


def public_cases():
    basic = b''.join([
        rec('10.0.0.1', 1, 'Jan', 2026, 0, 0, 1, 'GET', '/', 200, 123),
        rec('10.0.0.1', 1, 'Jan', 2026, 0, 5, 9, 'GET', '/index.html', 200, 4567),
        rec('10.0.0.2', 1, 'Jan', 2026, 1, 2, 3, 'POST', '/api/v1/items', 201, 89),
        rec('192.168.1.9', 2, 'Feb', 2026, 1, 59, 59, 'DELETE', '/api/v1/items/7', 204, 0),
        rec('8.8.8.8', 2, 'Feb', 2026, 12, 30, 0, 'PUT', '/x_y.z-1', 404, '-'),
        rec('10.0.0.2', 2, 'Feb', 2026, 23, 59, 59, 'GET', '/index.html', 500, 1000000000000),
        rec('10.0.0.3', 3, 'Mar', 2026, 23, 0, 0, 'GET', '/index.html', 101, 5),
        rec('10.0.0.3', 3, 'Mar', 2026, 23, 0, 0, 'GET', '/index.html', 304, 0),
    ])
    ties_bad = b''.join([
        rec('1.1.1.1', 10, 'Apr', 2020, 5, 6, 7, 'GET', '/a', 200, 10),
        rec('1.1.1.2', 10, 'Apr', 2020, 5, 6, 8, 'GET', '/b', 200, 20),
        rec('1.1.1.3', 10, 'Apr', 2020, 5, 6, 9, 'GET', '/c', 200, 30),
        rec('1.1.1.1', 10, 'Apr', 2020, 5, 7, 7, 'GET', '/a', 301, 10),
        rec('1.1.1.2', 10, 'Apr', 2020, 5, 7, 8, 'GET', '/b', 302, 20),
        rec('1.1.1.3', 10, 'Apr', 2020, 5, 7, 9, 'GET', '/c', 403, 30),
        b'256.1.1.1 - - [10/Apr/2020:05:06:07 +0000] "GET /x HTTP/1.1" 200 1\n',
        b'1.1.1.1 - - [10/Apr/2020:05:06:07 +0000] "GET /' + b'a' * 64 + b' HTTP/1.1" 200 1\n',
        b'1.1.1.1 - - [10/Apr/2020:05:06:07 +0000] "GET /x HTTP/1.1" 600 1\n',
        b'1.1.1.1  - - [10/Apr/2020:05:06:07 +0000] "GET /x HTTP/1.1" 200 1\n',
        b'1.1.1.1 - - [10/Apr/2020:05:06:07 +0000] "get /x HTTP/1.1" 200 1\n',
        b'1.1.1.1 -  - [10/Apr/2020:05:06:07 +0000] "GET /x HTTP/1.1" 200 1\n',
        b'1.1.1.1 - - [10/Apr/2020:05:06:07 +0000] "GET x HTTP/1.1" 200 1\n',
        b'1.1.1.1 - - [10/Apr/2020:05:06:07 +0000] "GET /x HTTP/1.0" 200 1\n',
        b'1.1.1.1 - - [10/Apr/2020:05:06:07 +0000] "GET /x HTTP/1.1" 200 1000000000001\n',
        b'1.1.1.1 - - [10/Apr/2020:05:06:07 +0000] "GET /x HTTP/1.1" 200 -5\n',
    ])
    dash_no_newline = b''.join([
        rec('4.3.2.1', 31, 'Dec', 2025, 9, 8, 7, 'GET', '/dash', 200, '-'),
        rec('4.3.2.2', 31, 'Dec', 2025, 9, 8, 8, 'GET', '/dash', 200, 42),
        b'4.3.2.3 - - [31/Dec/2025:09:08:09 +0000] "GET /tail HTTP/1.1" 200 7',
    ])
    return [
        ('basic', basic, []),
        ('ties_bad', ties_bad, []),
        ('dash_no_newline', dash_no_newline, []),
    ]


def edge_bad():
    good = b''.join([
        rec('001.002.003.004', 1, 'Jan', 2026, 0, 0, 0, 'GET', '/ok', 200, '0000000000007'),
        rec('1.2.3.4', 1, 'Jan', 2026, 0, 0, 0, 'GET', '/ok', 200, 3),
        rec('255.255.255.255', 31, 'Dec', 9999, 23, 59, 59, 'DELETE', '/a-b_c.d', 599, 1000000000000),
    ])
    bad = b''.join([
        b'256.1.1.1 - - [01/Jan/2026:00:00:00 +0000] "GET /bad HTTP/1.1" 200 1\n',
        b'1.2.3.4 - - [01/Jan/2026:00:00:00 +0000] "GET /' + b'a' * 64 + b' HTTP/1.1" 200 1\n',
        b'1.2.3.4 - - [01/Jan/2026:00:00:00 +0000] "GET /bad HTTP/1.1" 600 1\n',
        b'1.2.3.4  - - [01/Jan/2026:00:00:00 +0000] "GET /bad HTTP/1.1" 200 1\n',
        b'1.2.3.4 - - [01/Jan/2026:00:00:00 +0000] "get /bad HTTP/1.1" 200 1\n',
        b'1.2.3.4 - - [01/jan/2026:00:00:00 +0000] "GET /bad HTTP/1.1" 200 1\n',
        b'1.2.3.4 - - [32/Jan/2026:00:00:00 +0000] "GET /bad HTTP/1.1" 200 1\n',
        b'1.2.3.4 - - [01/Jan/2026:24:00:00 +0000] "GET /bad HTTP/1.1" 200 1\n',
        b'1.2.3.4 - - [01/Jan/2026:00:60:00 +0000] "GET /bad HTTP/1.1" 200 1\n',
        b'1.2.3.4 - - [01/Jan/2026:00:00:60 +0000] "GET /bad HTTP/1.1" 200 1\n',
        b'1.2.3.4 - - [01/Jan/2026:00:00:00 +0100] "GET /bad HTTP/1.1" 200 1\n',
        b'1.2.3.4 - - [01/Jan/2026:00:00:00 +0000] "GET /bad HTTP/1.1" 99 1\n',
        b'1.2.3.4 - - [01/Jan/2026:00:00:00 +0000] "GET /bad HTTP/1.1" 1000 1\n',
        b'1.2.3.4 - - [01/Jan/2026:00:00:00 +0000] "GET /bad HTTP/1.1" 200 +1\n',
        b'1.2.3.4 - - [01/Jan/2026:00:00:00 +0000] "GET /bad HTTP/1.1" 200 1\r\n',
        b'1.2.3.4 - - [01/Jan/2026:00:00:00 +0000] "GET /bad HTTP/1.1" 200 1 extra\n',
        b'1.2.3.4 - - [01/Jan/2026:00:00:00 +0000] "POST /bad HTTP/1.1" 200\n',
        b'\n',
    ])
    return good + bad


def all_hours():
    out = []
    for h in range(24):
        out.append(rec('10.1.%d.%d' % (h // 256, h % 256), 1, 'Jun', 2026, h, 0, 0, 'GET',
                       '/h/%02d' % h, 200, h * 1000))
    out.append(rec('10.1.0.0', 1, 'Jun', 2026, 0, 0, 1, 'GET', '/h/00', 101, 7))
    return b''.join(out)


def leading_zeros():
    return b''.join([
        rec('001.002.003.004', 1, 'Feb', 2024, 0, 0, 0, 'GET', '/p', 200, '000'),
        rec('1.2.3.4', 1, 'Feb', 2024, 0, 0, 1, 'GET', '/p', 200, '00042'),
        rec('000.000.000.000', 1, 'Feb', 2024, 0, 0, 2, 'GET', '/p', 200, '000000000001'),
        rec('255.000.255.001', 1, 'Feb', 2024, 0, 0, 3, 'GET', '/q', 200, 5),
    ])


def ties_paths():
    out = []
    for p in ('/a', '/A', '/a-b', '/a_b', '/a.b', '/aa', '/a0', '/a/', '/a//', '/a1'):
        for k in range(3):
            out.append(rec('9.9.9.9', 1, 'May', 2026, k, 0, 0, 'GET', p, 200, k + 1))
    out.append(b'9.9.9.9 - - [01/May/2026:00:00:00 +0000] "GET /a HTTP/1.1" 600 1\n')
    return b''.join(out)


def random_case(rng, nlines):
    nips = 200
    ips = ['%d.%d.%d.%d' % (rng.randrange(256), rng.randrange(256), rng.randrange(256),
                            rng.randrange(256)) for _ in range(nips)]
    paths = []
    for i in range(120):
        r = rng.randrange(100)
        if r < 20:
            p = '/'
        elif r < 40:
            p = '/api/%d' % rng.randrange(50)
        elif r < 60:
            n = rng.randrange(1, 21)
            p = '/static/' + ''.join(PATH_CHARS[rng.randrange(len(PATH_CHARS))] for _ in range(n))
        else:
            p = '/p%03d' % i
        paths.append(p)
    statuses = (100, 101, 200, 201, 204, 301, 302, 304, 400, 401, 403, 404, 418, 500, 502, 503, 599)
    out = []
    for _ in range(nlines):
        r = rng.randrange(100)
        if r < 7:
            bad = rng.randrange(10)
            if bad == 0:
                out.append(b'256.1.1.1 - - [01/Jan/2026:00:00:00 +0000] "GET /x HTTP/1.1" 200 1\n')
            elif bad == 1:
                out.append(b'1.2.3.4  - - [01/Jan/2026:00:00:00 +0000] "GET /x HTTP/1.1" 200 1\n')
            elif bad == 2:
                out.append(b'1.2.3.4 - - [01/Jan/2026:00:00:00 +0000] "get /x HTTP/1.1" 200 1\n')
            elif bad == 3:
                out.append(b'1.2.3.4 - - [01/Jan/2026:00:00:00 +0000] "GET /x HTTP/1.1" 600 1\n')
            elif bad == 4:
                out.append(b'1.2.3.4 - - [01/Jan/2026:00:00:00 +0000] "GET /' + b'a' * 64
                           + b' HTTP/1.1" 200 1\n')
            elif bad == 5:
                out.append(b'1.2.3.4 - - [01/Jan/2026:00:00:00 +0000] "GET /x HTTP/1.1" 200 1000000000001\n')
            elif bad == 6:
                out.append(b'1.2.3.4 - - [01/Jan/2026:00:00:00 +0000] "GET /x HTTP/1.1" 200\n')
            elif bad == 7:
                out.append(b'1.2.3.4 - - [01/Foo/2026:00:00:00 +0000] "GET /x HTTP/1.1" 200 1\n')
            elif bad == 8:
                out.append(b'1.2.3.4 - - [01/Jan/2026:24:00:00 +0000] "GET /x HTTP/1.1" 200 1\n')
            else:
                out.append(b'1.2.3.4 - - [01/Jan/2026:00:00:00 +0000] "GET /x HTTP/1.1"  200 1\n')
            continue
        ip = ips[rng.randrange(nips)]
        path = paths[rng.randrange(len(paths))]
        hh = rng.randrange(24)
        mm = rng.randrange(60)
        ss = rng.randrange(60)
        day = rng.randrange(1, 32)
        mon = MONTHS[rng.randrange(12)]
        year = rng.randrange(1990, 2030)
        method = METHODS[rng.randrange(len(METHODS))]
        status = statuses[rng.randrange(len(statuses))]
        if rng.randrange(20) == 0:
            nb = '-'
        else:
            nb = rng.randrange(0, 1000000001)
        out.append(rec(ip, day, mon, year, hh, mm, ss, method, path, status, nb))
    return b''.join(out)


def perf_case(rng):
    nips = 2000
    ips = ['%d.%d.%d.%d' % (rng.randrange(256), rng.randrange(256), rng.randrange(256),
                            rng.randrange(256)) for _ in range(nips)]
    paths = ['/p%04d' % i for i in range(5000)]
    statuses = (100, 200, 200, 200, 201, 204, 301, 302, 304, 400, 403, 404, 418, 500, 502, 503, 599)
    parts = []
    for _ in range(1500000):
        ip = ips[rng.randrange(nips)]
        path = paths[rng.randrange(5000)]
        hh = rng.randrange(24)
        mm = rng.randrange(60)
        ss = rng.randrange(60)
        day = rng.randrange(1, 29)
        mon = MONTHS[rng.randrange(12)]
        year = rng.randrange(2000, 2027)
        method = METHODS[rng.randrange(len(METHODS))]
        status = statuses[rng.randrange(len(statuses))]
        if rng.randrange(25) == 0:
            nb = '-'
        else:
            nb = str(rng.randrange(0, 1000000001))
        parts.append('%s - - [%02d/%s/%04d:%02d:%02d:%02d +0000] "%s %s HTTP/1.1" %d %s\n'
                     % (ip, day, mon, year, hh, mm, ss, method, path, status, nb))
    return ''.join(parts).encode()


def cases(rng):
    public = public_cases()
    hidden = [
        ('empty', b'', []),
        ('edge_bad', edge_bad(), []),
        ('all_hours', all_hours(), []),
        ('leading_zeros', leading_zeros(), []),
        ('ties_paths', ties_paths(), []),
        ('random_mixed', random_case(rng, 900), []),
    ]
    perf = ('perf', perf_case(rng), [])
    return public, hidden, perf

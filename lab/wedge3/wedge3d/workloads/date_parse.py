#!/usr/bin/env python3
"""Date-parsing workload: python-dateutil.parser.parse vs a native ISO parser.

W3D_IMPL=python (default) imports dateutil.parser.parse; W3D_IMPL=native imports ciso8601.
W3D_N sets the number of strings (default 20000).
The program prints a fixed digest of every parsed value, never a time.
"""
import os
import sys
from datetime import timezone


def make_strings(n):
    out = []
    for i in range(n):
        y = 1970 + (i * 7) % 70
        mo = 1 + (i * 11) % 12
        d = 1 + (i * 17) % 28
        h = (i * 13) % 24
        mi = (i * 29) % 60
        s = (i * 37) % 60
        us = (i * 99991) % 1000000
        base = '%04d-%02d-%02d' % (y, mo, d)
        stamp = '%02d:%02d:%02d' % (h, mi, s)
        off = (i * 37) % 1440 - 720
        sign = '+' if off >= 0 else '-'
        off = abs(off)
        v = i % 8
        if v == 0:
            out.append(base)
        elif v == 1:
            out.append(base + 'T' + stamp)
        elif v == 2:
            out.append(base + 'T' + stamp + '.%06d' % us)
        elif v == 3:
            out.append(base + 'T' + stamp + 'Z')
        elif v == 4:
            out.append(base + 'T' + stamp + '%s%02d:%02d' % (sign, off // 60, off % 60))
        elif v == 5:
            out.append(base + ' ' + stamp)
        elif v == 6:
            out.append(base + 'T%02d:%02d' % (h, mi))
        else:
            out.append(base + 'T' + stamp + '.%06d%s%02d:%02d'
                       % (us, sign, off // 60, off % 60))
    return out


def canonical(dt):
    if dt.tzinfo is not None:
        dt = dt.astimezone(timezone.utc).replace(tzinfo=None)
        return 'A' + dt.isoformat()
    return 'N' + dt.isoformat()


def fnv(s):
    h = 0xcbf29ce484222325
    for b in s.encode('utf-8'):
        h ^= b
        h = (h * 0x100000001b3) & 0xFFFFFFFFFFFFFFFF
    return h


def main():
    n = int(os.environ.get('W3D_N', '20000'))
    impl = os.environ.get('W3D_IMPL', 'python')
    if impl == 'native':
        import ciso8601
        parse = ciso8601.parse_datetime
    else:
        from dateutil.parser import parse
    h = 0xcbf29ce484222325
    first = last = None
    for text in make_strings(n):
        value = canonical(parse(text))
        if first is None:
            first = value
        last = value
        h ^= fnv(value)
        h = (h * 0x100000001b3) & 0xFFFFFFFFFFFFFFFF
    print('count=%d hash=%016x first=%s last=%s' % (n, h, first, last))


if __name__ == '__main__':
    main()

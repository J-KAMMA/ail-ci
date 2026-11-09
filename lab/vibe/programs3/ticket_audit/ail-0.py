import sys


def digits_ok(s, lo, hi):
    n = len(s)
    if n < lo or n > hi:
        return False
    i = 0
    while i < n:
        c = s[i]
        if c < 48 or c > 57:
            return False
        i = i + 1
    return True


def to_int(s):
    v = 0
    i = 0
    n = len(s)
    while i < n:
        v = v * 10 + (s[i] - 48)
        i = i + 1
    return v


def bstr(s):
    r = []
    i = 0
    n = len(s)
    while i < n:
        r.append(chr(s[i]))
        i = i + 1
    return "".join(r)


def venue_ok(s):
    if len(s) != 3:
        return False
    i = 0
    while i < 3:
        c = s[i]
        if c < 65 or c > 90:
            return False
        i = i + 1
    return True


def name_ok(s):
    n = len(s)
    if n < 1 or n > 40:
        return False
    if s[0] == 32 or s[n - 1] == 32:
        return False
    i = 0
    while i < n:
        c = s[i]
        if c < 32 or c > 126 or c == 124:
            return False
        i = i + 1
    return True


def date_syntax(s):
    if len(s) != 10:
        return False
    if s[4] != 45 or s[7] != 45:
        return False
    if not digits_ok(s[0:4], 4, 4):
        return False
    if not digits_ok(s[5:7], 2, 2):
        return False
    if not digits_ok(s[8:10], 2, 2):
        return False
    return True


def date_value_ok(s):
    y = to_int(s[0:4])
    if y < 2000 or y > 2099:
        return False
    mo = to_int(s[5:7])
    if mo < 1 or mo > 12:
        return False
    dims = [31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31]
    if y % 4 == 0:
        dims[1] = 29
    da = to_int(s[8:10])
    if da < 1 or da > dims[mo - 1]:
        return False
    return True


def time_syntax(s):
    if len(s) != 5:
        return False
    if s[2] != 58:
        return False
    if not digits_ok(s[0:2], 2, 2):
        return False
    if not digits_ok(s[3:5], 2, 2):
        return False
    return True


def time_value_ok(s):
    hh = to_int(s[0:2])
    mm = to_int(s[3:5])
    if hh > 23 or mm > 59:
        return False
    return True


def price_syntax(s):
    n = len(s)
    dot = -1
    i = 0
    while i < n:
        if s[i] == 46:
            if dot != -1:
                return False
            dot = i
        i = i + 1
    if dot < 1 or dot > 4:
        return False
    if n != dot + 3:
        return False
    if not digits_ok(s[0:dot], dot, dot):
        return False
    if not digits_ok(s[dot + 1:n], 2, 2):
        return False
    return True


def price_cents(s):
    n = len(s)
    dot = 0
    while dot < n:
        if s[dot] == 46:
            break
        dot = dot + 1
    dollars = s[0:dot]
    if len(dollars) > 1 and dollars[0] == 48:
        return -1
    total = to_int(dollars) * 100 + to_int(s[dot + 1:n])
    if total % 5 != 0:
        return -1
    return total


def seat_syntax(s):
    n = len(s)
    if n < 2 or n > 4:
        return False
    c = s[0]
    if c < 65 or c > 90:
        return False
    return digits_ok(s[1:n], 1, 3)


def seat_num(s):
    n = len(s)
    ds = s[1:n]
    if len(ds) > 1 and ds[0] == 48:
        return -1
    v = to_int(ds)
    if v < 1 or v > 999:
        return -1
    return v


def buyer_syntax(s):
    n = len(s)
    if n < 4 or n > 12:
        return False
    c = s[0]
    if c < 97 or c > 122:
        return False
    i = 1
    while i < n:
        c = s[i]
        if not ((c >= 97 and c <= 122) or (c >= 48 and c <= 57)):
            return False
        i = i + 1
    return True


def checksum_ok(ev):
    total = (3 * (ev[0] - 48) + (ev[1] - 48) + 3 * (ev[2] - 48)
             + (ev[3] - 48) + 3 * (ev[4] - 48) + (ev[5] - 48))
    return total % 10 == 0


def money(c):
    return "%d.%02d" % (c // 100, c % 100)


def main():
    if len(sys.argv) != 2:
        return 1
    try:
        f = open(sys.argv[1], "rb")
        data = f.read()
        f.close()
    except Exception:
        return 1

    lines = data.split(b"\n")
    if data.endswith(b"\n"):
        lines = lines[:len(lines) - 1]

    if len(lines) == 0 or lines[0] != b"TKT/1":
        sys.stdout.write("line 1: header\n")
        return 2

    venues = {}
    events = {}
    sold = {}
    nv = 0
    ne = 0
    ns = 0
    nr = 0
    revenue = 0
    recs = 0

    def fail(ln, cat, status):
        sys.stdout.write("line %d: %s\n" % (ln, cat))
        sys.exit(status)

    end_seen = False
    nlines = len(lines)
    idx = 1
    while idx < nlines:
        ln = idx + 1
        parts = lines[idx].split(b"|")
        typ = parts[0]

        if typ == b"V":
            if len(parts) != 4:
                fail(ln, "syntax", 3)
            code = parts[1]
            nm = parts[2]
            cap = parts[3]
            if not venue_ok(code) or not name_ok(nm) or not digits_ok(cap, 1, 6):
                fail(ln, "syntax", 3)
            if len(cap) > 1 and cap[0] == 48:
                fail(ln, "value", 4)
            capv = to_int(cap)
            if capv < 1 or capv > 100000:
                fail(ln, "value", 4)
            code_s = bstr(code)
            if code_s in venues:
                fail(ln, "duplicate", 6)
            venues[code_s] = capv
            nv = nv + 1
            recs = recs + 1

        elif typ == b"E":
            if len(parts) != 6:
                fail(ln, "syntax", 3)
            ev = parts[1]
            vc = parts[2]
            dt = parts[3]
            tm = parts[4]
            pr = parts[5]
            if (not digits_ok(ev, 6, 6) or not venue_ok(vc)
                    or not date_syntax(dt) or not time_syntax(tm)
                    or not price_syntax(pr)):
                fail(ln, "syntax", 3)
            if not checksum_ok(ev):
                fail(ln, "value", 4)
            if not date_value_ok(dt):
                fail(ln, "value", 4)
            if not time_value_ok(tm):
                fail(ln, "value", 4)
            pc = price_cents(pr)
            if pc < 0:
                fail(ln, "value", 4)
            ev_s = bstr(ev)
            vc_s = bstr(vc)
            if vc_s not in venues:
                fail(ln, "reference", 5)
            if ev_s in events:
                fail(ln, "duplicate", 6)
            events[ev_s] = [vc_s, pc]
            sold[ev_s] = set()
            ne = ne + 1
            recs = recs + 1

        elif typ == b"S":
            if len(parts) != 4:
                fail(ln, "syntax", 3)
            ev = parts[1]
            st = parts[2]
            by = parts[3]
            if not digits_ok(ev, 6, 6) or not seat_syntax(st) or not buyer_syntax(by):
                fail(ln, "syntax", 3)
            if not checksum_ok(ev):
                fail(ln, "value", 4)
            if seat_num(st) < 0:
                fail(ln, "value", 4)
            ev_s = bstr(ev)
            st_s = bstr(st)
            if ev_s not in events:
                fail(ln, "reference", 5)
            if st_s in sold[ev_s]:
                fail(ln, "duplicate", 6)
            capv = venues[events[ev_s][0]]
            if len(sold[ev_s]) >= capv:
                fail(ln, "capacity", 7)
            sold[ev_s].add(st_s)
            revenue = revenue + events[ev_s][1]
            ns = ns + 1
            recs = recs + 1

        elif typ == b"R":
            if len(parts) != 3:
                fail(ln, "syntax", 3)
            ev = parts[1]
            st = parts[2]
            if not digits_ok(ev, 6, 6) or not seat_syntax(st):
                fail(ln, "syntax", 3)
            if not checksum_ok(ev):
                fail(ln, "value", 4)
            if seat_num(st) < 0:
                fail(ln, "value", 4)
            ev_s = bstr(ev)
            st_s = bstr(st)
            if ev_s not in events or st_s not in sold[ev_s]:
                fail(ln, "reference", 5)
            sold[ev_s].discard(st_s)
            revenue = revenue - events[ev_s][1]
            nr = nr + 1
            recs = recs + 1

        elif typ == b"END":
            if len(parts) != 3:
                fail(ln, "syntax", 3)
            cs = parts[1]
            ct = parts[2]
            if not digits_ok(cs, 1, 9) or not digits_ok(ct, 1, 12):
                fail(ln, "syntax", 3)
            if len(cs) > 1 and cs[0] == 48:
                fail(ln, "value", 4)
            if len(ct) > 1 and ct[0] == 48:
                fail(ln, "value", 4)
            if to_int(cs) != recs or to_int(ct) != revenue:
                fail(ln, "summary", 8)
            end_seen = True
            if idx + 1 < nlines:
                fail(idx + 2, "summary", 8)
            break

        else:
            fail(ln, "syntax", 3)

        idx = idx + 1

    if not end_seen:
        fail(nlines + 1, "summary", 8)

    out = []
    out.append("venues %d events %d sold %d refunds %d" % (nv, ne, ns, nr))
    out.append("revenue %s" % money(revenue))

    codes = []
    for c in venues:
        codes.append(c)
    codes.sort()
    for code in codes:
        nev = 0
        tick = 0
        rev = 0
        for e in events:
            info = events[e]
            if info[0] == code:
                nev = nev + 1
                cnt = len(sold[e])
                tick = tick + cnt
                rev = rev + cnt * info[1]
        out.append("%s events=%d tickets=%d revenue=%s" % (code, nev, tick, money(rev)))

    tl = []
    for e in events:
        tl.append((-len(sold[e]), e))
    tl.sort()
    k = 0
    while k < 3 and k < len(tl):
        out.append("top %s %d" % (tl[k][1], -tl[k][0]))
        k = k + 1

    sys.stdout.write("\n".join(out))
    sys.stdout.write("\n")
    return 0


sys.exit(main())

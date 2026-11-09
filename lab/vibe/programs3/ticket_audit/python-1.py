import sys


def fail(n, category, status):
    sys.stdout.write("line %d: %s\n" % (n, category))
    sys.exit(status)


def all_digits(b):
    if len(b) == 0:
        return False
    for c in b:
        if c < 0x30 or c > 0x39:
            return False
    return True


def valid_code(b):
    if len(b) != 3:
        return False
    for c in b:
        if c < 0x41 or c > 0x5A:
            return False
    return True


def valid_name(b):
    if len(b) < 1 or len(b) > 40:
        return False
    for c in b:
        if c < 0x20 or c > 0x7E or c == 0x7C:
            return False
    if b[0] == 0x20 or b[-1] == 0x20:
        return False
    return True


def cap_syntax(b):
    return 1 <= len(b) <= 6 and all_digits(b)


def cap_value(b):
    if len(b) > 1 and b[0] == 0x30:
        return False
    v = int(b)
    return 1 <= v <= 100000


def event_syntax(b):
    return len(b) == 6 and all_digits(b)


def event_value(b):
    d = [c - 0x30 for c in b]
    return (3 * d[0] + d[1] + 3 * d[2] + d[3] + 3 * d[4] + d[5]) % 10 == 0


def date_syntax(b):
    return (len(b) == 10 and all_digits(b[0:4]) and b[4] == 0x2D
            and all_digits(b[5:7]) and b[7] == 0x2D and all_digits(b[8:10]))


def date_value(b):
    y = int(b[0:4])
    m = int(b[5:7])
    d = int(b[8:10])
    if y < 2000 or y > 2099:
        return False
    if m < 1 or m > 12:
        return False
    if m == 2:
        last = 29 if y % 4 == 0 else 28
    elif m in (4, 6, 9, 11):
        last = 30
    else:
        last = 31
    return 1 <= d <= last


def time_syntax(b):
    return (len(b) == 5 and all_digits(b[0:2]) and b[2] == 0x3A
            and all_digits(b[3:5]))


def time_value(b):
    h = int(b[0:2])
    mi = int(b[3:5])
    return 0 <= h <= 23 and 0 <= mi <= 59


def price_syntax(b):
    if len(b) < 4 or len(b) > 7:
        return False
    if b[-3] != 0x2E:
        return False
    return all_digits(b[:-3]) and all_digits(b[-2:])


def price_value(b):
    ip = b[:-3]
    if len(ip) > 1 and ip[0] == 0x30:
        return False
    cents = int(ip) * 100 + int(b[-2:])
    return cents % 5 == 0


def price_cents(b):
    return int(b[:-3]) * 100 + int(b[-2:])


def seat_syntax(b):
    if len(b) < 2 or len(b) > 4:
        return False
    if b[0] < 0x41 or b[0] > 0x5A:
        return False
    return all_digits(b[1:])


def seat_value(b):
    num = b[1:]
    if len(num) > 1 and num[0] == 0x30:
        return False
    v = int(num)
    return 1 <= v <= 999


def buyer_syntax(b):
    if len(b) < 4 or len(b) > 12:
        return False
    if b[0] < 0x61 or b[0] > 0x7A:
        return False
    for c in b[1:]:
        if not ((0x61 <= c <= 0x7A) or (0x30 <= c <= 0x39)):
            return False
    return True


def no_leading_zero(b):
    return not (len(b) > 1 and b[0] == 0x30)


def count_syntax(b):
    return 1 <= len(b) <= 9 and all_digits(b)


def cents_syntax(b):
    return 1 <= len(b) <= 12 and all_digits(b)


def money(c):
    return "%d.%02d" % (c // 100, c % 100)


def main():
    if len(sys.argv) != 2:
        sys.exit(1)

    try:
        with open(sys.argv[1], "rb") as fh:
            data = fh.read()
    except OSError:
        sys.exit(1)

    if data == b"":
        lines = []
    else:
        parts = data.split(b"\n")
        if data.endswith(b"\n"):
            parts.pop()
        lines = parts

    if not lines or lines[0] != b"TKT/1":
        fail(1, "header", 2)

    venues = {}
    events = {}
    sold = {}
    revenue = 0
    s_count = 0
    r_count = 0
    records = 0
    end_index = None

    for i in range(1, len(lines)):
        line = lines[i]
        ln = i + 1
        f = line.split(b"|")
        typ = f[0]

        if typ == b"V":
            if len(f) != 4:
                fail(ln, "syntax", 3)
            code, name, cap = f[1], f[2], f[3]
            if not valid_code(code):
                fail(ln, "syntax", 3)
            if not valid_name(name):
                fail(ln, "syntax", 3)
            if not cap_syntax(cap):
                fail(ln, "syntax", 3)
            if not cap_value(cap):
                fail(ln, "value", 4)
            if code in venues:
                fail(ln, "duplicate", 6)
            venues[code] = int(cap)
            records += 1

        elif typ == b"E":
            if len(f) != 6:
                fail(ln, "syntax", 3)
            event, vcode, date, time, price = f[1], f[2], f[3], f[4], f[5]
            if not event_syntax(event):
                fail(ln, "syntax", 3)
            if not valid_code(vcode):
                fail(ln, "syntax", 3)
            if not date_syntax(date):
                fail(ln, "syntax", 3)
            if not time_syntax(time):
                fail(ln, "syntax", 3)
            if not price_syntax(price):
                fail(ln, "syntax", 3)
            if not event_value(event):
                fail(ln, "value", 4)
            if not date_value(date):
                fail(ln, "value", 4)
            if not time_value(time):
                fail(ln, "value", 4)
            if not price_value(price):
                fail(ln, "value", 4)
            if vcode not in venues:
                fail(ln, "reference", 5)
            if event in events:
                fail(ln, "duplicate", 6)
            events[event] = (vcode, price_cents(price))
            sold[event] = set()
            records += 1

        elif typ == b"S":
            if len(f) != 4:
                fail(ln, "syntax", 3)
            event, seat, buyer = f[1], f[2], f[3]
            if not event_syntax(event):
                fail(ln, "syntax", 3)
            if not seat_syntax(seat):
                fail(ln, "syntax", 3)
            if not buyer_syntax(buyer):
                fail(ln, "syntax", 3)
            if not event_value(event):
                fail(ln, "value", 4)
            if not seat_value(seat):
                fail(ln, "value", 4)
            if event not in events:
                fail(ln, "reference", 5)
            st = sold[event]
            if seat in st:
                fail(ln, "duplicate", 6)
            vc, pc = events[event]
            if len(st) >= venues[vc]:
                fail(ln, "capacity", 7)
            st.add(seat)
            revenue += pc
            s_count += 1
            records += 1

        elif typ == b"R":
            if len(f) != 3:
                fail(ln, "syntax", 3)
            event, seat = f[1], f[2]
            if not event_syntax(event):
                fail(ln, "syntax", 3)
            if not seat_syntax(seat):
                fail(ln, "syntax", 3)
            if not event_value(event):
                fail(ln, "value", 4)
            if not seat_value(seat):
                fail(ln, "value", 4)
            if event not in events:
                fail(ln, "reference", 5)
            st = sold[event]
            if seat not in st:
                fail(ln, "reference", 5)
            st.remove(seat)
            revenue -= events[event][1]
            r_count += 1
            records += 1

        elif typ == b"END":
            if len(f) != 3:
                fail(ln, "syntax", 3)
            cf, centsf = f[1], f[2]
            if not count_syntax(cf):
                fail(ln, "syntax", 3)
            if not cents_syntax(centsf):
                fail(ln, "syntax", 3)
            if not no_leading_zero(cf):
                fail(ln, "value", 4)
            if not no_leading_zero(centsf):
                fail(ln, "value", 4)
            if int(cf) != records or int(centsf) != revenue:
                fail(ln, "summary", 8)
            end_index = i
            break

        else:
            fail(ln, "syntax", 3)

    if end_index is None:
        fail(len(lines) + 1, "summary", 8)
    if end_index + 1 < len(lines):
        fail(end_index + 2, "summary", 8)

    out = []
    out.append("venues %d events %d sold %d refunds %d"
               % (len(venues), len(events), s_count, r_count))
    out.append("revenue %s" % money(revenue))

    ve_cnt = {c: 0 for c in venues}
    ve_tick = {c: 0 for c in venues}
    ve_rev = {c: 0 for c in venues}
    for ev, (vc, pc) in events.items():
        k = len(sold[ev])
        ve_cnt[vc] += 1
        ve_tick[vc] += k
        ve_rev[vc] += k * pc

    for c in sorted(venues):
        out.append("%s events=%d tickets=%d revenue=%s"
                   % (c.decode("ascii"), ve_cnt[c], ve_tick[c], money(ve_rev[c])))

    top = sorted(events.keys(), key=lambda e: (-len(sold[e]), e))[:3]
    for ev in top:
        out.append("top %s %d" % (ev.decode("ascii"), len(sold[ev])))

    sys.stdout.write("\n".join(out) + "\n")


main()

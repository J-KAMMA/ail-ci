import sys


def fail(line_no, cat, status):
    sys.stdout.write("line {}: {}\n".format(line_no, cat))
    sys.exit(status)


def to_int(b):
    n = 0
    for c in b:
        n = n * 10 + (c - 48)
    return n


def is_digits(b):
    for c in b:
        if c < 48 or c > 57:
            return False
    return True


def digits_len(b, lo, hi):
    if len(b) < lo or len(b) > hi:
        return False
    return is_digits(b)


def no_leading_zero(b):
    return len(b) == 1 or b[0] != 48


def syn_venue_code(f):
    if len(f) != 3:
        return False
    for c in f:
        if c < 65 or c > 90:
            return False
    return True


def syn_name(f):
    if len(f) < 1 or len(f) > 40:
        return False
    for c in f:
        if c < 0x20 or c > 0x7e or c == 0x7c:
            return False
    return f[0] != 0x20 and f[-1] != 0x20


def syn_capacity(f):
    return digits_len(f, 1, 6)


def val_capacity(f):
    if not no_leading_zero(f):
        return False
    v = to_int(f)
    return 1 <= v <= 100000


def syn_event(f):
    return digits_len(f, 6, 6)


def val_event(f):
    ds = [c - 48 for c in f]
    return (3 * ds[0] + ds[1] + 3 * ds[2] + ds[3] + 3 * ds[4] + ds[5]) % 10 == 0


def syn_date(f):
    if len(f) != 10:
        return False
    if f[4] != 45 or f[7] != 45:
        return False
    for i in (0, 1, 2, 3, 5, 6, 8, 9):
        c = f[i]
        if c < 48 or c > 57:
            return False
    return True


def val_date(f):
    y = to_int(f[0:4])
    m = to_int(f[5:7])
    d = to_int(f[8:10])
    if y < 2000 or y > 2099:
        return False
    if m < 1 or m > 12:
        return False
    if m == 2:
        if y % 4 == 0:
            last = 29
        else:
            last = 28
    elif m == 4 or m == 6 or m == 9 or m == 11:
        last = 30
    else:
        last = 31
    return 1 <= d <= last


def syn_time(f):
    if len(f) != 5:
        return False
    if f[2] != 58:
        return False
    for i in (0, 1, 3, 4):
        c = f[i]
        if c < 48 or c > 57:
            return False
    return True


def val_time(f):
    h = to_int(f[0:2])
    m = to_int(f[3:5])
    return 0 <= h <= 23 and 0 <= m <= 59


def syn_price(f):
    dot = f.find(b'.')
    if dot < 1 or dot > 4:
        return False
    if len(f) != dot + 3:
        return False
    for c in f[:dot]:
        if c < 48 or c > 57:
            return False
    for c in f[dot + 1:]:
        if c < 48 or c > 57:
            return False
    return True


def val_price(f):
    dot = f.find(b'.')
    p1 = f[:dot]
    if not no_leading_zero(p1):
        return False
    cents = to_int(p1) * 100 + to_int(f[dot + 1:])
    return cents % 5 == 0


def syn_seat(f):
    if len(f) < 2 or len(f) > 4:
        return False
    if f[0] < 65 or f[0] > 90:
        return False
    for c in f[1:]:
        if c < 48 or c > 57:
            return False
    return True


def val_seat(f):
    nums = f[1:]
    if not no_leading_zero(nums):
        return False
    return to_int(nums) >= 1


def syn_buyer(f):
    if len(f) < 4 or len(f) > 12:
        return False
    c = f[0]
    if c < 97 or c > 122:
        return False
    for c in f[1:]:
        if (c < 97 or c > 122) and (c < 48 or c > 57):
            return False
    return True


def syn_count(f):
    return digits_len(f, 1, 9)


def val_count(f):
    return no_leading_zero(f)


def syn_cents(f):
    return digits_len(f, 1, 12)


def val_cents(f):
    return no_leading_zero(f)


def money(cents):
    return "{}.{:02d}".format(cents // 100, cents % 100)


def main():
    if len(sys.argv) != 2:
        sys.exit(1)

    try:
        with open(sys.argv[1], 'rb') as fh:
            data = fh.read()
    except Exception:
        sys.exit(1)

    lines = data.split(b'\n')
    if lines and lines[-1] == b'':
        lines.pop()

    if len(lines) == 0 or lines[0] != b'TKT/1':
        fail(1, "header", 2)

    venues = {}
    events = {}
    sold = {}
    revenue = 0
    rec_count = 0
    s_count = 0
    r_count = 0
    nlines = len(lines)
    i = 1

    while i < nlines:
        line_no = i + 1
        parts = lines[i].split(b'|')
        typ = parts[0]

        if typ == b'V':
            if len(parts) != 4:
                fail(line_no, "syntax", 3)
            code = parts[1]
            name = parts[2]
            cap = parts[3]
            if not syn_venue_code(code) or not syn_name(name) or not syn_capacity(cap):
                fail(line_no, "syntax", 3)
            if not val_capacity(cap):
                fail(line_no, "value", 4)
            if code in venues:
                fail(line_no, "duplicate", 6)
            venues[code] = to_int(cap)
            rec_count += 1

        elif typ == b'E':
            if len(parts) != 6:
                fail(line_no, "syntax", 3)
            ev = parts[1]
            vc = parts[2]
            dt = parts[3]
            tm = parts[4]
            pr = parts[5]
            if not syn_event(ev) or not syn_venue_code(vc) or not syn_date(dt) or not syn_time(tm) or not syn_price(pr):
                fail(line_no, "syntax", 3)
            if not val_event(ev) or not val_date(dt) or not val_time(tm) or not val_price(pr):
                fail(line_no, "value", 4)
            if vc not in venues:
                fail(line_no, "reference", 5)
            if ev in events:
                fail(line_no, "duplicate", 6)
            dot = pr.find(b'.')
            cents = to_int(pr[:dot]) * 100 + to_int(pr[dot + 1:])
            events[ev] = (vc, cents)
            sold[ev] = set()
            rec_count += 1

        elif typ == b'S':
            if len(parts) != 4:
                fail(line_no, "syntax", 3)
            ev = parts[1]
            seat = parts[2]
            buyer = parts[3]
            if not syn_event(ev) or not syn_seat(seat) or not syn_buyer(buyer):
                fail(line_no, "syntax", 3)
            if not val_event(ev) or not val_seat(seat):
                fail(line_no, "value", 4)
            if ev not in events:
                fail(line_no, "reference", 5)
            if seat in sold[ev]:
                fail(line_no, "duplicate", 6)
            vc = events[ev][0]
            if len(sold[ev]) >= venues[vc]:
                fail(line_no, "capacity", 7)
            sold[ev].add(seat)
            revenue += events[ev][1]
            s_count += 1
            rec_count += 1

        elif typ == b'R':
            if len(parts) != 3:
                fail(line_no, "syntax", 3)
            ev = parts[1]
            seat = parts[2]
            if not syn_event(ev) or not syn_seat(seat):
                fail(line_no, "syntax", 3)
            if not val_event(ev) or not val_seat(seat):
                fail(line_no, "value", 4)
            if ev not in events or seat not in sold[ev]:
                fail(line_no, "reference", 5)
            sold[ev].remove(seat)
            revenue -= events[ev][1]
            r_count += 1
            rec_count += 1

        elif typ == b'END':
            if len(parts) != 3:
                fail(line_no, "syntax", 3)
            cnt = parts[1]
            cents_s = parts[2]
            if not syn_count(cnt) or not syn_cents(cents_s):
                fail(line_no, "syntax", 3)
            if not val_count(cnt) or not val_cents(cents_s):
                fail(line_no, "value", 4)
            if to_int(cnt) != rec_count or to_int(cents_s) != revenue:
                fail(line_no, "summary", 8)
            if i + 1 < nlines:
                fail(line_no + 1, "summary", 8)

            out = []
            out.append("venues {} events {} sold {} refunds {}".format(
                len(venues), len(events), s_count, r_count))
            out.append("revenue {}".format(money(revenue)))

            vn = {}
            vt = {}
            vr = {}
            for code in venues:
                vn[code] = 0
                vt[code] = 0
                vr[code] = 0

            for ev in events:
                vc = events[ev][0]
                pc = events[ev][1]
                c = len(sold[ev])
                vn[vc] += 1
                vt[vc] += c
                vr[vc] += c * pc

            for code in sorted(venues):
                out.append("{} events={} tickets={} revenue={}".format(
                    code.decode('ascii'), vn[code], vt[code], money(vr[code])))

            arr = []
            for ev in events:
                arr.append((-len(sold[ev]), ev))
            arr.sort()

            k = 0
            while k < len(arr) and k < 3:
                out.append("top {} {}".format(arr[k][1].decode('ascii'), -arr[k][0]))
                k += 1

            sys.stdout.write("\n".join(out) + "\n")
            sys.exit(0)

        else:
            fail(line_no, "syntax", 3)

        i += 1

    fail(nlines + 1, "summary", 8)


main()

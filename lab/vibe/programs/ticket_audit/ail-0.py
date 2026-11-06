import sys


def to_int(b):
    n = 0
    for c in b:
        n = n * 10 + (c - 48)
    return n


def all_digits(b):
    if len(b) == 0:
        return False
    for c in b:
        if c < 48 or c > 57:
            return False
    return True


def syn_venue_code(f):
    if len(f) != 3:
        return False
    for c in f:
        if c < 65 or c > 90:
            return False
    return True


def syn_name(f):
    n = len(f)
    if n < 1 or n > 40:
        return False
    if f[0] == 32 or f[n - 1] == 32:
        return False
    for c in f:
        if c < 32 or c > 126:
            return False
        if c == 124:
            return False
    return True


def syn_capacity(f):
    if len(f) < 1 or len(f) > 6:
        return False
    return all_digits(f)


def syn_event(f):
    if len(f) != 6:
        return False
    return all_digits(f)


def syn_date(f):
    if len(f) != 10:
        return False
    if f[4] != 45 or f[7] != 45:
        return False
    if not all_digits(f[0:4]):
        return False
    if not all_digits(f[5:7]):
        return False
    return all_digits(f[8:10])


def syn_time(f):
    if len(f) != 5:
        return False
    if f[2] != 58:
        return False
    if not all_digits(f[0:2]):
        return False
    return all_digits(f[3:5])


def syn_price(f):
    i = f.find(b".")
    if i < 0:
        return False
    if f.find(b".", i + 1) >= 0:
        return False
    left = f[:i]
    right = f[i + 1:]
    if len(left) < 1 or len(left) > 4:
        return False
    if len(right) != 2:
        return False
    if not all_digits(left):
        return False
    return all_digits(right)


def syn_seat(f):
    if len(f) < 2 or len(f) > 4:
        return False
    c = f[0]
    if c < 65 or c > 90:
        return False
    return all_digits(f[1:])


def syn_buyer(f):
    n = len(f)
    if n < 4 or n > 12:
        return False
    c = f[0]
    if c < 97 or c > 122:
        return False
    for c in f:
        if not ((c >= 97 and c <= 122) or (c >= 48 and c <= 57)):
            return False
    return True


def syn_count(f):
    if len(f) < 1 or len(f) > 9:
        return False
    return all_digits(f)


def syn_cents(f):
    if len(f) < 1 or len(f) > 12:
        return False
    return all_digits(f)


def val_capacity(f):
    if len(f) > 1 and f[0] == 48:
        return False
    n = to_int(f)
    return n >= 1 and n <= 100000


def val_event(f):
    total = 3 * (f[0] - 48) + (f[1] - 48) + 3 * (f[2] - 48)
    total = total + (f[3] - 48) + 3 * (f[4] - 48) + (f[5] - 48)
    return total % 10 == 0


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
    return d >= 1 and d <= last


def val_time(f):
    h = to_int(f[0:2])
    m = to_int(f[3:5])
    return h >= 0 and h <= 23 and m >= 0 and m <= 59


def val_price(f):
    i = f.find(b".")
    left = f[:i]
    if len(left) > 1 and left[0] == 48:
        return False
    amount = to_int(left) * 100 + to_int(f[i + 1:])
    return amount % 5 == 0


def price_amount(f):
    i = f.find(b".")
    return to_int(f[:i]) * 100 + to_int(f[i + 1:])


def val_seat(f):
    rest = f[1:]
    if len(rest) > 1 and rest[0] == 48:
        return False
    n = to_int(rest)
    return n >= 1 and n <= 999


def val_count(f):
    if len(f) > 1 and f[0] == 48:
        return False
    return True


def val_cents(f):
    if len(f) > 1 and f[0] == 48:
        return False
    return True


def money(cents):
    whole = cents // 100
    frac = cents % 100
    if frac < 10:
        return str(whole) + ".0" + str(frac)
    return str(whole) + "." + str(frac)


def fail(n, cat, status):
    sys.stdout.write("line " + str(n) + ": " + cat + "\n")
    sys.exit(status)


def main():
    if len(sys.argv) != 2:
        sys.exit(1)

    try:
        with open(sys.argv[1], "rb") as fh:
            data = fh.read()
    except OSError:
        sys.exit(1)

    lines = data.split(b"\n")
    if data.endswith(b"\n"):
        lines.pop()

    if lines[0] != b"TKT/1":
        fail(1, "header", 2)

    venues = {}
    events = {}
    revenue = 0
    sold_records = 0
    refund_records = 0
    record_count = 0
    nlines = len(lines)
    idx = 1

    while idx < nlines:
        line = lines[idx]
        lineno = idx + 1
        parts = line.split(b"|")
        t = parts[0]

        if t == b"V":
            if len(parts) != 4:
                fail(lineno, "syntax", 3)
            if not (syn_venue_code(parts[1]) and syn_name(parts[2]) and syn_capacity(parts[3])):
                fail(lineno, "syntax", 3)
            if not val_capacity(parts[3]):
                fail(lineno, "value", 4)
            if parts[1] in venues:
                fail(lineno, "duplicate", 6)
            venues[parts[1]] = to_int(parts[3])

        elif t == b"E":
            if len(parts) != 6:
                fail(lineno, "syntax", 3)
            if not (syn_event(parts[1]) and syn_venue_code(parts[2]) and syn_date(parts[3]) and syn_time(parts[4]) and syn_price(parts[5])):
                fail(lineno, "syntax", 3)
            if not (val_event(parts[1]) and val_date(parts[3]) and val_time(parts[4]) and val_price(parts[5])):
                fail(lineno, "value", 4)
            ev = parts[1]
            vcode = parts[2]
            if vcode not in venues:
                fail(lineno, "reference", 5)
            if ev in events:
                fail(lineno, "duplicate", 6)
            events[ev] = [vcode, price_amount(parts[5]), set()]

        elif t == b"S":
            if len(parts) != 4:
                fail(lineno, "syntax", 3)
            if not (syn_event(parts[1]) and syn_seat(parts[2]) and syn_buyer(parts[3])):
                fail(lineno, "syntax", 3)
            if not (val_event(parts[1]) and val_seat(parts[2])):
                fail(lineno, "value", 4)
            ev = parts[1]
            seat = parts[2]
            if ev not in events:
                fail(lineno, "reference", 5)
            info = events[ev]
            if seat in info[2]:
                fail(lineno, "duplicate", 6)
            if len(info[2]) >= venues[info[0]]:
                fail(lineno, "capacity", 7)
            info[2].add(seat)
            revenue = revenue + info[1]
            sold_records = sold_records + 1

        elif t == b"R":
            if len(parts) != 3:
                fail(lineno, "syntax", 3)
            if not (syn_event(parts[1]) and syn_seat(parts[2])):
                fail(lineno, "syntax", 3)
            if not (val_event(parts[1]) and val_seat(parts[2])):
                fail(lineno, "value", 4)
            ev = parts[1]
            seat = parts[2]
            if ev not in events:
                fail(lineno, "reference", 5)
            info = events[ev]
            if seat not in info[2]:
                fail(lineno, "reference", 5)
            info[2].remove(seat)
            revenue = revenue - info[1]
            refund_records = refund_records + 1

        elif t == b"END":
            if len(parts) != 3:
                fail(lineno, "syntax", 3)
            if not (syn_count(parts[1]) and syn_cents(parts[2])):
                fail(lineno, "syntax", 3)
            if not (val_count(parts[1]) and val_cents(parts[2])):
                fail(lineno, "value", 4)
            cnt = to_int(parts[1])
            amt = to_int(parts[2])
            if cnt != record_count or amt != revenue:
                fail(lineno, "summary", 8)
            if idx != nlines - 1:
                fail(lineno + 1, "summary", 8)
            break

        else:
            fail(lineno, "syntax", 3)

        record_count = record_count + 1
        idx = idx + 1

    else:
        fail(nlines + 1, "summary", 8)

    out = []
    out.append("venues " + str(len(venues)) + " events " + str(len(events)) + " sold " + str(sold_records) + " refunds " + str(refund_records))
    out.append("revenue " + money(revenue))

    venue_n = {}
    venue_t = {}
    venue_rev = {}
    for vc in venues:
        venue_n[vc] = 0
        venue_t[vc] = 0
        venue_rev[vc] = 0

    for ev in events:
        info = events[ev]
        vc = info[0]
        ns = len(info[2])
        venue_n[vc] = venue_n[vc] + 1
        venue_t[vc] = venue_t[vc] + ns
        venue_rev[vc] = venue_rev[vc] + info[1] * ns

    for vc in sorted(venues):
        out.append(vc.decode("ascii") + " events=" + str(venue_n[vc]) + " tickets=" + str(venue_t[vc]) + " revenue=" + money(venue_rev[vc]))

    ranked = []
    for ev in events:
        info = events[ev]
        ranked.append((-len(info[2]), ev))
    ranked.sort()

    limit = 3
    if len(ranked) < 3:
        limit = len(ranked)

    i = 0
    while i < limit:
        item = ranked[i]
        out.append("top " + item[1].decode("ascii") + " " + str(-item[0]))
        i = i + 1

    sys.stdout.write("\n".join(out) + "\n")


main()

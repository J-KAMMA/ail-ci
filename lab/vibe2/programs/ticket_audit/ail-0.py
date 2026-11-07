import sys


def fail(lineno, cat, status):
    sys.stdout.write("line " + str(lineno) + ": " + cat + "\n")
    sys.exit(status)


def is_digits(s):
    if not s:
        return False
    for c in s:
        if c < "0" or c > "9":
            return False
    return True


def is_letters(s):
    if not s:
        return False
    for c in s:
        if c < "A" or c > "Z":
            return False
    return True


def syn_name(s):
    n = len(s)
    if n < 1 or n > 40:
        return False
    for c in s:
        o = ord(c)
        if o < 0x20 or o > 0x7E:
            return False
        if c == "|":
            return False
    if s[0] == " " or s[-1] == " ":
        return False
    return True


def syn_date(s):
    if len(s) != 10:
        return False
    if s[4] != "-" or s[7] != "-":
        return False
    for i in (0, 1, 2, 3, 5, 6, 8, 9):
        c = s[i]
        if c < "0" or c > "9":
            return False
    return True


def syn_time(s):
    if len(s) != 5:
        return False
    if s[2] != ":":
        return False
    for i in (0, 1, 3, 4):
        c = s[i]
        if c < "0" or c > "9":
            return False
    return True


def syn_price(s):
    parts = s.split(".")
    if len(parts) != 2:
        return False
    a = parts[0]
    b = parts[1]
    if len(a) < 1 or len(a) > 4:
        return False
    if not is_digits(a):
        return False
    if len(b) != 2 or not is_digits(b):
        return False
    return True


def syn_seat(s):
    n = len(s)
    if n < 2 or n > 4:
        return False
    c = s[0]
    if c < "A" or c > "Z":
        return False
    return is_digits(s[1:])


def syn_buyer(s):
    n = len(s)
    if n < 4 or n > 12:
        return False
    c = s[0]
    if c < "a" or c > "z":
        return False
    for c in s:
        if (c >= "a" and c <= "z") or (c >= "0" and c <= "9"):
            continue
        return False
    return True


def event_value_ok(s):
    d0 = ord(s[0]) - 48
    d1 = ord(s[1]) - 48
    d2 = ord(s[2]) - 48
    d3 = ord(s[3]) - 48
    d4 = ord(s[4]) - 48
    d5 = ord(s[5]) - 48
    return (3 * d0 + d1 + 3 * d2 + d3 + 3 * d4 + d5) % 10 == 0


def seat_value_ok(s):
    rest = s[1:]
    if len(rest) > 1 and rest[0] == "0":
        return False
    return int(rest) >= 1


def fmt(cents):
    return str(cents // 100) + "." + ("%02d" % (cents % 100))


def main():
    if len(sys.argv) != 2:
        sys.exit(1)
    try:
        f = open(sys.argv[1], "rb")
        data = f.read()
        f.close()
    except OSError:
        sys.exit(1)

    text = data.decode("latin-1")
    lines = text.split("\n")
    if lines and lines[-1] == "" and text.endswith("\n"):
        lines.pop()

    if len(lines) == 0 or lines[0] != "TKT/1":
        fail(1, "header", 2)

    venues = {}
    events = {}
    sold = {}
    record_count = 0
    revenue = 0
    n_sold = 0
    n_refund = 0
    ended = False

    i = 1
    while i < len(lines):
        line = lines[i]
        lineno = i + 1
        parts = line.split("|")
        typ = parts[0]

        if typ == "V":
            if len(parts) != 4:
                fail(lineno, "syntax", 3)
            code = parts[1]
            name = parts[2]
            cap = parts[3]
            if not (len(code) == 3 and is_letters(code)):
                fail(lineno, "syntax", 3)
            if not syn_name(name):
                fail(lineno, "syntax", 3)
            if not (len(cap) >= 1 and len(cap) <= 6 and is_digits(cap)):
                fail(lineno, "syntax", 3)
            if len(cap) > 1 and cap[0] == "0":
                fail(lineno, "value", 4)
            capv = int(cap)
            if capv < 1 or capv > 100000:
                fail(lineno, "value", 4)
            if code in venues:
                fail(lineno, "duplicate", 6)
            venues[code] = capv
            record_count += 1

        elif typ == "E":
            if len(parts) != 6:
                fail(lineno, "syntax", 3)
            ev = parts[1]
            vc = parts[2]
            dt = parts[3]
            tm = parts[4]
            pr = parts[5]
            if not (len(ev) == 6 and is_digits(ev)):
                fail(lineno, "syntax", 3)
            if not (len(vc) == 3 and is_letters(vc)):
                fail(lineno, "syntax", 3)
            if not syn_date(dt):
                fail(lineno, "syntax", 3)
            if not syn_time(tm):
                fail(lineno, "syntax", 3)
            if not syn_price(pr):
                fail(lineno, "syntax", 3)

            if not event_value_ok(ev):
                fail(lineno, "value", 4)
            y = int(dt[0:4])
            m = int(dt[5:7])
            dd = int(dt[8:10])
            if y < 2000 or y > 2099:
                fail(lineno, "value", 4)
            if m < 1 or m > 12:
                fail(lineno, "value", 4)
            if m == 2:
                last = 29 if y % 4 == 0 else 28
            elif m == 4 or m == 6 or m == 9 or m == 11:
                last = 30
            else:
                last = 31
            if dd < 1 or dd > last:
                fail(lineno, "value", 4)
            hh = int(tm[0:2])
            mm = int(tm[3:5])
            if hh > 23 or mm > 59:
                fail(lineno, "value", 4)
            pp = pr.split(".")
            a = pp[0]
            b = pp[1]
            if len(a) > 1 and a[0] == "0":
                fail(lineno, "value", 4)
            frac = int(b)
            if frac % 5 != 0:
                fail(lineno, "value", 4)
            prc = int(a) * 100 + frac

            if vc not in venues:
                fail(lineno, "reference", 5)
            if ev in events:
                fail(lineno, "duplicate", 6)
            events[ev] = (vc, prc)
            sold[ev] = set()
            record_count += 1

        elif typ == "S":
            if len(parts) != 4:
                fail(lineno, "syntax", 3)
            ev = parts[1]
            seat = parts[2]
            buyer = parts[3]
            if not (len(ev) == 6 and is_digits(ev)):
                fail(lineno, "syntax", 3)
            if not syn_seat(seat):
                fail(lineno, "syntax", 3)
            if not syn_buyer(buyer):
                fail(lineno, "syntax", 3)

            if not event_value_ok(ev):
                fail(lineno, "value", 4)
            if not seat_value_ok(seat):
                fail(lineno, "value", 4)

            if ev not in events:
                fail(lineno, "reference", 5)
            st = sold[ev]
            if seat in st:
                fail(lineno, "duplicate", 6)
            vc = events[ev][0]
            if len(st) >= venues[vc]:
                fail(lineno, "capacity", 7)
            st.add(seat)
            revenue += events[ev][1]
            n_sold += 1
            record_count += 1

        elif typ == "R":
            if len(parts) != 3:
                fail(lineno, "syntax", 3)
            ev = parts[1]
            seat = parts[2]
            if not (len(ev) == 6 and is_digits(ev)):
                fail(lineno, "syntax", 3)
            if not syn_seat(seat):
                fail(lineno, "syntax", 3)

            if not event_value_ok(ev):
                fail(lineno, "value", 4)
            if not seat_value_ok(seat):
                fail(lineno, "value", 4)

            if ev not in events:
                fail(lineno, "reference", 5)
            st = sold[ev]
            if seat not in st:
                fail(lineno, "reference", 5)
            st.remove(seat)
            revenue -= events[ev][1]
            n_refund += 1
            record_count += 1

        elif typ == "END":
            if len(parts) != 3:
                fail(lineno, "syntax", 3)
            cnt = parts[1]
            cts = parts[2]
            if not (len(cnt) >= 1 and len(cnt) <= 9 and is_digits(cnt)):
                fail(lineno, "syntax", 3)
            if not (len(cts) >= 1 and len(cts) <= 12 and is_digits(cts)):
                fail(lineno, "syntax", 3)
            if len(cnt) > 1 and cnt[0] == "0":
                fail(lineno, "value", 4)
            if len(cts) > 1 and cts[0] == "0":
                fail(lineno, "value", 4)
            if int(cnt) != record_count or int(cts) != revenue:
                fail(lineno, "summary", 8)
            ended = True
            if i + 1 < len(lines):
                fail(lineno + 1, "summary", 8)
            break

        else:
            fail(lineno, "syntax", 3)

        i += 1

    if not ended:
        fail(len(lines) + 1, "summary", 8)

    out = []
    out.append("venues " + str(len(venues)) + " events " + str(len(events)) +
               " sold " + str(n_sold) + " refunds " + str(n_refund))
    out.append("revenue " + fmt(revenue))
    for code in sorted(venues.keys()):
        n = 0
        t = 0
        rev = 0
        for ev in events:
            vc = events[ev][0]
            if vc == code:
                n += 1
                c = len(sold[ev])
                t += c
                rev += c * events[ev][1]
        out.append(code + " events=" + str(n) + " tickets=" + str(t) +
                   " revenue=" + fmt(rev))

    tops = []
    for ev in events:
        tops.append((ev, len(sold[ev])))
    tops.sort(key=lambda p: (-p[1], int(p[0])))
    limit = 3 if len(tops) >= 3 else len(tops)
    for k in range(limit):
        out.append("top " + tops[k][0] + " " + str(tops[k][1]))

    sys.stdout.write("\n".join(out) + "\n")


main()

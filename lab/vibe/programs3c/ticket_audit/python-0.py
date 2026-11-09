import re
import sys

CODES = {
    "header": 2,
    "syntax": 3,
    "value": 4,
    "reference": 5,
    "duplicate": 6,
    "capacity": 7,
    "summary": 8,
}

VENUE_RE = r"[A-Z]{3}"
CAP_RE = r"[0-9]{1,6}"
EVENT_RE = r"[0-9]{6}"
DATE_RE = r"[0-9]{4}-[0-9]{2}-[0-9]{2}"
TIME_RE = r"[0-9]{2}:[0-9]{2}"
PRICE_RE = r"[0-9]{1,4}\.[0-9]{2}"
SEAT_RE = r"[A-Z][0-9]{1,3}"
BUYER_RE = r"[a-z][a-z0-9]{3,11}"
COUNT_RE = r"[0-9]{1,9}"
CENTS_RE = r"[0-9]{1,12}"


def fail(lineno, cat):
    sys.stdout.write(f"line {lineno}: {cat}\n")
    sys.stdout.flush()
    sys.exit(CODES[cat])


def fm(pattern, s):
    return re.fullmatch(pattern, s) is not None


def name_ok(s):
    if not (1 <= len(s) <= 40):
        return False
    for c in s:
        o = ord(c)
        if o < 0x20 or o > 0x7E or c == "|":
            return False
    return s[0] != " " and s[-1] != " "


def no_leading_zero(s):
    return len(s) == 1 or s[0] != "0"


def checksum_ok(s):
    d = [int(c) for c in s]
    w = [3, 1, 3, 1, 3, 1]
    return sum(a * b for a, b in zip(w, d)) % 10 == 0


def date_ok(s):
    y = int(s[0:4])
    m = int(s[5:7])
    d = int(s[8:10])
    if not (2000 <= y <= 2099):
        return False
    if not (1 <= m <= 12):
        return False
    leap = y % 4 == 0
    days = [31, 29 if leap else 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31][m - 1]
    return 1 <= d <= days


def time_ok(s):
    return int(s[0:2]) <= 23 and int(s[3:5]) <= 59


def price_cents(s):
    ip, fp = s.split(".")
    return int(ip) * 100 + int(fp)


def price_ok(s):
    ip = s.split(".")[0]
    if not no_leading_zero(ip):
        return False
    return price_cents(s) % 5 == 0


def money(c):
    return f"{c // 100}.{c % 100:02d}"


def main():
    if len(sys.argv) != 2:
        sys.exit(1)
    try:
        with open(sys.argv[1], "rb") as fh:
            data = fh.read()
    except OSError:
        sys.exit(1)

    text = data.decode("latin-1")
    lines = text.split("\n")
    if lines and lines[-1] == "":
        lines.pop()

    if not lines or lines[0] != "TKT/1":
        fail(1, "header")

    venues = {}   # code -> capacity
    events = {}   # number -> {"venue", "price", "sold"}
    n_records = 0
    n_s = 0
    n_r = 0
    revenue = 0
    ended = False
    arity = {"V": 4, "E": 6, "S": 4, "R": 3, "END": 3}

    for lineno in range(2, len(lines) + 1):
        line = lines[lineno - 1]
        if ended:
            fail(lineno, "summary")

        f = line.split("|")
        t = f[0]
        if t not in arity or len(f) != arity[t]:
            fail(lineno, "syntax")

        if t == "V":
            code, name, cap = f[1], f[2], f[3]
            if not (fm(VENUE_RE, code) and name_ok(name) and fm(CAP_RE, cap)):
                fail(lineno, "syntax")
            if not (no_leading_zero(cap) and 1 <= int(cap) <= 100000):
                fail(lineno, "value")
            if code in venues:
                fail(lineno, "duplicate")
            venues[code] = int(cap)
            n_records += 1

        elif t == "E":
            num, vc, date, tm, price = f[1], f[2], f[3], f[4], f[5]
            if not (fm(EVENT_RE, num) and fm(VENUE_RE, vc) and fm(DATE_RE, date)
                    and fm(TIME_RE, tm) and fm(PRICE_RE, price)):
                fail(lineno, "syntax")
            if not (checksum_ok(num) and date_ok(date) and time_ok(tm) and price_ok(price)):
                fail(lineno, "value")
            if vc not in venues:
                fail(lineno, "reference")
            if num in events:
                fail(lineno, "duplicate")
            events[num] = {"venue": vc, "price": price_cents(price), "sold": set()}
            n_records += 1

        elif t == "S":
            num, seat, buyer = f[1], f[2], f[3]
            if not (fm(EVENT_RE, num) and fm(SEAT_RE, seat) and fm(BUYER_RE, buyer)):
                fail(lineno, "syntax")
            if not (checksum_ok(num) and seat[1] != "0"):
                fail(lineno, "value")
            ev = events.get(num)
            if ev is None:
                fail(lineno, "reference")
            sold = ev["sold"]
            if seat in sold:
                fail(lineno, "duplicate")
            if len(sold) >= venues[ev["venue"]]:
                fail(lineno, "capacity")
            sold.add(seat)
            revenue += ev["price"]
            n_s += 1
            n_records += 1

        elif t == "R":
            num, seat = f[1], f[2]
            if not (fm(EVENT_RE, num) and fm(SEAT_RE, seat)):
                fail(lineno, "syntax")
            if not (checksum_ok(num) and seat[1] != "0"):
                fail(lineno, "value")
            ev = events.get(num)
            if ev is None or seat not in ev["sold"]:
                fail(lineno, "reference")
            ev["sold"].remove(seat)
            revenue -= ev["price"]
            n_r += 1
            n_records += 1

        else:  # END
            cnt, cents = f[1], f[2]
            if not (fm(COUNT_RE, cnt) and fm(CENTS_RE, cents)):
                fail(lineno, "syntax")
            if not (no_leading_zero(cnt) and no_leading_zero(cents)):
                fail(lineno, "value")
            if int(cnt) != n_records or int(cents) != revenue:
                fail(lineno, "summary")
            ended = True

    if not ended:
        fail(len(lines) + 1, "summary")

    out = []
    out.append(f"venues {len(venues)} events {len(events)} sold {n_s} refunds {n_r}")
    out.append(f"revenue {money(revenue)}")
    for code in sorted(venues):
        n = 0
        tickets = 0
        rev = 0
        for ev in events.values():
            if ev["venue"] == code:
                n += 1
                tickets += len(ev["sold"])
                rev += ev["price"] * len(ev["sold"])
        out.append(f"{code} events={n} tickets={tickets} revenue={money(rev)}")
    ranked = sorted(events.items(), key=lambda kv: (-len(kv[1]["sold"]), kv[0]))
    for num, ev in ranked[:3]:
        out.append(f"top {num} {len(ev['sold'])}")
    sys.stdout.write("\n".join(out) + "\n")


if __name__ == "__main__":
    main()

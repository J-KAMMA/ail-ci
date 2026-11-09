import re
import sys

EXIT = {"header": 2, "syntax": 3, "value": 4, "reference": 5,
        "duplicate": 6, "capacity": 7, "summary": 8}

RE_VCODE = re.compile(r"[A-Z]{3}")
RE_CAP = re.compile(r"[0-9]{1,6}")
RE_EVENT = re.compile(r"[0-9]{6}")
RE_DATE = re.compile(r"[0-9]{4}-[0-9]{2}-[0-9]{2}")
RE_TIME = re.compile(r"[0-9]{2}:[0-9]{2}")
RE_PRICE = re.compile(r"[0-9]{1,4}\.[0-9]{2}")
RE_SEAT = re.compile(r"[A-Z][0-9]{1,3}")
RE_BUYER = re.compile(r"[a-z][a-z0-9]{3,11}")
RE_COUNT = re.compile(r"[0-9]{1,9}")
RE_CENTS = re.compile(r"[0-9]{1,12}")


class Fail(Exception):
    def __init__(self, cat, line):
        super().__init__(cat)
        self.cat = cat
        self.line = line


def ok_name(s):
    if not (1 <= len(s) <= 40):
        return False
    if not all(0x20 <= ord(c) <= 0x7E for c in s):
        return False
    return s[0] != " " and s[-1] != " "


def ok_leading_zero(s):
    return s == "0" or s[0] != "0"


def ok_event_checksum(s):
    d = [int(c) for c in s]
    total = 3 * d[0] + d[1] + 3 * d[2] + d[3] + 3 * d[4] + d[5]
    return total % 10 == 0


def ok_date(s):
    y = int(s[0:4])
    m = int(s[5:7])
    d = int(s[8:10])
    if not (2000 <= y <= 2099):
        return False
    if not (1 <= m <= 12):
        return False
    days = [31, 29 if y % 4 == 0 else 28, 31, 30, 31, 30,
            31, 31, 30, 31, 30, 31][m - 1]
    return 1 <= d <= days


def ok_time(s):
    h = int(s[0:2])
    mi = int(s[3:5])
    return h <= 23 and mi <= 59


def price_cents(s):
    ip, fp = s.split(".")
    return int(ip) * 100 + int(fp)


def ok_price(s):
    ip = s.split(".")[0]
    if len(ip) > 1 and ip[0] == "0":
        return False
    return price_cents(s) % 5 == 0


def money(c):
    return f"{c // 100}.{c % 100:02d}"


def run(lines):
    if not lines or lines[0] != "TKT/1":
        raise Fail("header", 1)

    venues = {}   # code -> capacity
    events = {}   # event number -> (venue code, price cents)
    sold = {}     # event number -> set of sold seats
    nS = 0
    nR = 0
    nrec = 0
    revenue = 0
    ended = False

    for idx in range(1, len(lines)):
        ln = idx + 1
        if ended:
            raise Fail("summary", ln)

        f = lines[idx].split("|")
        t = f[0]
        expected = {"V": 4, "E": 6, "S": 4, "R": 3, "END": 3}.get(t)
        if expected is None or len(f) != expected:
            raise Fail("syntax", ln)

        if t == "V":
            code, name, cap = f[1], f[2], f[3]
            if not (RE_VCODE.fullmatch(code) and ok_name(name)
                    and RE_CAP.fullmatch(cap)):
                raise Fail("syntax", ln)
            if not (cap[0] != "0" and 1 <= int(cap) <= 100000):
                raise Fail("value", ln)
            if code in venues:
                raise Fail("duplicate", ln)
            venues[code] = int(cap)
            nrec += 1

        elif t == "E":
            num, vcode, date, time, price = f[1], f[2], f[3], f[4], f[5]
            if not (RE_EVENT.fullmatch(num) and RE_VCODE.fullmatch(vcode)
                    and RE_DATE.fullmatch(date) and RE_TIME.fullmatch(time)
                    and RE_PRICE.fullmatch(price)):
                raise Fail("syntax", ln)
            if not (ok_event_checksum(num) and ok_date(date)
                    and ok_time(time) and ok_price(price)):
                raise Fail("value", ln)
            if vcode not in venues:
                raise Fail("reference", ln)
            if num in events:
                raise Fail("duplicate", ln)
            events[num] = (vcode, price_cents(price))
            sold[num] = set()
            nrec += 1

        elif t == "S":
            num, seat, buyer = f[1], f[2], f[3]
            if not (RE_EVENT.fullmatch(num) and RE_SEAT.fullmatch(seat)
                    and RE_BUYER.fullmatch(buyer)):
                raise Fail("syntax", ln)
            if not (ok_event_checksum(num) and seat[1] != "0"):
                raise Fail("value", ln)
            if num not in events:
                raise Fail("reference", ln)
            if seat in sold[num]:
                raise Fail("duplicate", ln)
            vcode, price = events[num]
            if len(sold[num]) >= venues[vcode]:
                raise Fail("capacity", ln)
            sold[num].add(seat)
            revenue += price
            nS += 1
            nrec += 1

        elif t == "R":
            num, seat = f[1], f[2]
            if not (RE_EVENT.fullmatch(num) and RE_SEAT.fullmatch(seat)):
                raise Fail("syntax", ln)
            if not (ok_event_checksum(num) and seat[1] != "0"):
                raise Fail("value", ln)
            if num not in events or seat not in sold[num]:
                raise Fail("reference", ln)
            sold[num].discard(seat)
            revenue -= events[num][1]
            nR += 1
            nrec += 1

        else:  # END
            count, cents = f[1], f[2]
            if not (RE_COUNT.fullmatch(count) and RE_CENTS.fullmatch(cents)):
                raise Fail("syntax", ln)
            if not (ok_leading_zero(count) and ok_leading_zero(cents)):
                raise Fail("value", ln)
            if int(count) != nrec or int(cents) != revenue:
                raise Fail("summary", ln)
            ended = True

    if not ended:
        raise Fail("summary", len(lines) + 1)

    out = []
    out.append(f"venues {len(venues)} events {len(events)} "
               f"sold {nS} refunds {nR}")
    out.append(f"revenue {money(revenue)}")
    for code in sorted(venues):
        n = 0
        tk = 0
        rev = 0
        for num, (vcode, price) in events.items():
            if vcode == code:
                n += 1
                k = len(sold[num])
                tk += k
                rev += k * price
        out.append(f"{code} events={n} tickets={tk} revenue={money(rev)}")
    ranking = sorted(events.keys(), key=lambda num: (-len(sold[num]), num))
    for num in ranking[:3]:
        out.append(f"top {num} {len(sold[num])}")
    sys.stdout.write("\n".join(out) + "\n")


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
    if text.endswith("\n"):
        lines.pop()

    try:
        run(lines)
    except Fail as e:
        print(f"line {e.line}: {e.cat}")
        sys.exit(EXIT[e.cat])
    sys.exit(0)


if __name__ == "__main__":
    main()

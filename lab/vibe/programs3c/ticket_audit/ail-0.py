import sys
import re

NEED = {'V': 4, 'E': 6, 'S': 4, 'R': 3, 'END': 3}

RE_VCODE = re.compile(r'[A-Z]{3}')
RE_CAP = re.compile(r'[1-9][0-9]{0,5}')
RE_EVENT = re.compile(r'[0-9]{6}')
RE_DATE = re.compile(r'[0-9]{4}-[0-9]{2}-[0-9]{2}')
RE_TIME = re.compile(r'[0-9]{2}:[0-9]{2}')
RE_PRICE = re.compile(r'(0|[1-9][0-9]{0,3})\.[0-9]{2}')
RE_SEAT = re.compile(r'[A-Z][1-9][0-9]{0,2}')
RE_BUYER = re.compile(r'[a-z][a-z0-9]{3,11}')
RE_COUNT = re.compile(r'0|[1-9][0-9]{0,8}')
RE_CENTS = re.compile(r'0|[1-9][0-9]{0,11}')


def fail(n, cat, status):
    print("line %d: %s" % (n, cat))
    sys.exit(status)


def name_ok(s):
    if len(s) < 1 or len(s) > 40:
        return False
    for c in s:
        o = ord(c)
        if o < 32 or o > 126:
            return False
    return s[0] != ' ' and s[-1] != ' '


def event_ok(s):
    d = [ord(c) - 48 for c in s]
    return (3 * d[0] + d[1] + 3 * d[2] + d[3] + 3 * d[4] + d[5]) % 10 == 0


def date_ok(s):
    y = int(s[0:4])
    m = int(s[5:7])
    d = int(s[8:10])
    if y < 2000 or y > 2099 or m < 1 or m > 12:
        return False
    if m == 2:
        last = 29 if y % 4 == 0 else 28
    elif m in (4, 6, 9, 11):
        last = 30
    else:
        last = 31
    return 1 <= d <= last


def time_ok(s):
    return int(s[0:2]) <= 23 and int(s[3:5]) <= 59


def price_cents(s):
    ip, fp = s.split('.')
    return int(ip) * 100 + int(fp)


def money(c):
    return f"{c // 100}.{c % 100:02d}"


def main():
    if len(sys.argv) != 2:
        sys.exit(1)
    try:
        with open(sys.argv[1], 'rb') as fh:
            data = fh.read()
    except OSError:
        sys.exit(1)

    text = data.decode('latin-1')
    lines = text.split('\n')
    if lines and lines[-1] == '':
        lines.pop()
    total = len(lines)
    if total == 0 or lines[0] != 'TKT/1':
        fail(1, 'header', 2)

    venues = {}   # code -> capacity
    events = {}   # event -> (venue code, price cents)
    sold = {}     # event -> set of sold seats
    nrec = 0
    nsold = 0
    nref = 0
    revenue = 0
    ended = False

    for idx in range(1, total):
        n = idx + 1
        if ended:
            fail(n, 'summary', 8)
        f = lines[idx].split('|')
        t = f[0]
        if t not in NEED or len(f) != NEED[t]:
            fail(n, 'syntax', 3)

        if t == 'V':
            code, name, cap = f[1], f[2], f[3]
            if not (RE_VCODE.fullmatch(code) and name_ok(name) and RE_CAP.fullmatch(cap)):
                fail(n, 'syntax', 3)
            if int(cap) < 1 or int(cap) > 100000:
                fail(n, 'value', 4)
            if code in venues:
                fail(n, 'duplicate', 6)
            venues[code] = int(cap)
            nrec += 1

        elif t == 'E':
            ev, vc, dt, tm, pr = f[1], f[2], f[3], f[4], f[5]
            if not (RE_EVENT.fullmatch(ev) and RE_VCODE.fullmatch(vc)
                    and RE_DATE.fullmatch(dt) and RE_TIME.fullmatch(tm)
                    and RE_PRICE.fullmatch(pr)):
                fail(n, 'syntax', 3)
            cents = price_cents(pr)
            if not (event_ok(ev) and date_ok(dt) and time_ok(tm) and cents % 5 == 0):
                fail(n, 'value', 4)
            if vc not in venues:
                fail(n, 'reference', 5)
            if ev in events:
                fail(n, 'duplicate', 6)
            events[ev] = (vc, cents)
            sold[ev] = set()
            nrec += 1

        elif t == 'S':
            ev, seat, buyer = f[1], f[2], f[3]
            if not (RE_EVENT.fullmatch(ev) and RE_SEAT.fullmatch(seat)
                    and RE_BUYER.fullmatch(buyer)):
                fail(n, 'syntax', 3)
            if not event_ok(ev):
                fail(n, 'value', 4)
            if ev not in events:
                fail(n, 'reference', 5)
            s = sold[ev]
            if seat in s:
                fail(n, 'duplicate', 6)
            if len(s) >= venues[events[ev][0]]:
                fail(n, 'capacity', 7)
            s.add(seat)
            revenue += events[ev][1]
            nsold += 1
            nrec += 1

        elif t == 'R':
            ev, seat = f[1], f[2]
            if not (RE_EVENT.fullmatch(ev) and RE_SEAT.fullmatch(seat)):
                fail(n, 'syntax', 3)
            if not event_ok(ev):
                fail(n, 'value', 4)
            if ev not in events or seat not in sold[ev]:
                fail(n, 'reference', 5)
            sold[ev].discard(seat)
            revenue -= events[ev][1]
            nref += 1
            nrec += 1

        else:
            count, cents = f[1], f[2]
            if not (RE_COUNT.fullmatch(count) and RE_CENTS.fullmatch(cents)):
                fail(n, 'syntax', 3)
            if int(count) != nrec or int(cents) != revenue:
                fail(n, 'summary', 8)
            ended = True

    if not ended:
        fail(total + 1, 'summary', 8)

    stats = {code: [0, 0, 0] for code in venues}
    for ev, (vc, price) in events.items():
        k = len(sold[ev])
        st = stats[vc]
        st[0] += 1
        st[1] += k
        st[2] += k * price

    out = []
    out.append(f"venues {len(venues)} events {len(events)} sold {nsold} refunds {nref}")
    out.append(f"revenue {money(revenue)}")
    for code in sorted(venues):
        st = stats[code]
        out.append(f"{code} events={st[0]} tickets={st[1]} revenue={money(st[2])}")
    ranked = sorted(events, key=lambda e: (-len(sold[e]), e))
    for ev in ranked[:3]:
        out.append(f"top {ev} {len(sold[ev])}")
    sys.stdout.write("\n".join(out) + "\n")


main()

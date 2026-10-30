import sys
import re

R_VEN = re.compile(rb'[A-Z]{3}')
R_NAME = re.compile(rb'[\x20-\x7b\x7d-\x7e]{1,40}')
R_CAP = re.compile(rb'[0-9]{1,6}')
R_EVT = re.compile(rb'[0-9]{6}')
R_DATE = re.compile(rb'([0-9]{4})-([0-9]{2})-([0-9]{2})')
R_TIME = re.compile(rb'([0-9]{2}):([0-9]{2})')
R_PRICE = re.compile(rb'([0-9]{1,4})\.([0-9]{2})')
R_SEAT = re.compile(rb'[A-Z]([0-9]{1,3})')
R_BUYER = re.compile(rb'[a-z][a-z0-9]{3,11}')
R_COUNT = re.compile(rb'[0-9]{1,9}')
R_CENTS = re.compile(rb'[0-9]{1,12}')

CODES = {'header': 2, 'syntax': 3, 'value': 4, 'reference': 5,
         'duplicate': 6, 'capacity': 7, 'summary': 8}


def fail(n, cat):
    sys.stdout.write("line %d: %s\n" % (n, cat))
    sys.stdout.flush()
    sys.exit(CODES[cat])


def money(c):
    return "%d.%02d" % (c // 100, c % 100)


def noleadzero(b):
    return not (len(b) > 1 and b[0:1] == b'0')


def main():
    if len(sys.argv) != 2:
        sys.exit(1)
    try:
        with open(sys.argv[1], 'rb') as f:
            data = f.read()
    except Exception:
        sys.exit(1)
    lines = data.split(b'\n')
    if lines and lines[-1] == b'':
        lines.pop()
    if not lines or lines[0] != b'TKT/1':
        fail(1, 'header')

    venues = {}   # code -> capacity
    events = {}   # num -> [venue, price, set]
    nrec = 0
    nS = nR = 0
    sold_total = 0
    revenue = 0
    n = len(lines)
    for i in range(1, n):
        ln = i + 1
        parts = lines[i].split(b'|')
        t = parts[0]
        nf = len(parts) - 1
        if t == b'V' and nf == 3:
            code, name, cap = parts[1:]
            if not (R_VEN.fullmatch(code) and R_NAME.fullmatch(name)
                    and name[0] != 0x20 and name[-1] != 0x20
                    and R_CAP.fullmatch(cap)):
                fail(ln, 'syntax')
            if not noleadzero(cap) or not (1 <= int(cap) <= 100000):
                fail(ln, 'value')
            if code in venues:
                fail(ln, 'duplicate')
            venues[code] = int(cap)
            nrec += 1
        elif t == b'E' and nf == 5:
            ev, vc, date, tm, price = parts[1:]
            md = R_DATE.fullmatch(date)
            mt = R_TIME.fullmatch(tm)
            mp = R_PRICE.fullmatch(price)
            if not (R_EVT.fullmatch(ev) and R_VEN.fullmatch(vc) and md and mt and mp):
                fail(ln, 'syntax')
            d = [x - 48 for x in ev]
            bad = (3 * d[0] + d[1] + 3 * d[2] + d[3] + 3 * d[4] + d[5]) % 10 != 0
            y, mo, da = int(md.group(1)), int(md.group(2)), int(md.group(3))
            if not (2000 <= y <= 2099 and 1 <= mo <= 12):
                bad = True
            else:
                dim = [31, 29 if y % 4 == 0 else 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31][mo - 1]
                if not (1 <= da <= dim):
                    bad = True
            if int(mt.group(1)) > 23 or int(mt.group(2)) > 59:
                bad = True
            if not noleadzero(mp.group(1)):
                bad = True
            cents = int(mp.group(1)) * 100 + int(mp.group(2))
            if cents % 5 != 0:
                bad = True
            if bad:
                fail(ln, 'value')
            if vc not in venues:
                fail(ln, 'reference')
            if ev in events:
                fail(ln, 'duplicate')
            events[ev] = [vc, cents, set()]
            nrec += 1
        elif t == b'S' and nf == 3:
            ev, seat, buyer = parts[1:]
            ms = R_SEAT.fullmatch(seat)
            if not (R_EVT.fullmatch(ev) and ms and R_BUYER.fullmatch(buyer)):
                fail(ln, 'syntax')
            d = [x - 48 for x in ev]
            if (3 * d[0] + d[1] + 3 * d[2] + d[3] + 3 * d[4] + d[5]) % 10 != 0:
                fail(ln, 'value')
            sn = ms.group(1)
            if sn[0:1] == b'0':
                fail(ln, 'value')
            e = events.get(ev)
            if e is None:
                fail(ln, 'reference')
            if seat in e[2]:
                fail(ln, 'duplicate')
            if len(e[2]) >= venues[e[0]]:
                fail(ln, 'capacity')
            e[2].add(seat)
            sold_total += 1
            revenue += e[1]
            nS += 1
            nrec += 1
        elif t == b'R' and nf == 2:
            ev, seat = parts[1:]
            ms = R_SEAT.fullmatch(seat)
            if not (R_EVT.fullmatch(ev) and ms):
                fail(ln, 'syntax')
            d = [x - 48 for x in ev]
            if (3 * d[0] + d[1] + 3 * d[2] + d[3] + 3 * d[4] + d[5]) % 10 != 0:
                fail(ln, 'value')
            if ms.group(1)[0:1] == b'0':
                fail(ln, 'value')
            e = events.get(ev)
            if e is None or seat not in e[2]:
                fail(ln, 'reference')
            e[2].discard(seat)
            sold_total -= 1
            revenue -= e[1]
            nR += 1
            nrec += 1
        elif t == b'END' and nf == 2:
            cnt, cents = parts[1:]
            if not (R_COUNT.fullmatch(cnt) and R_CENTS.fullmatch(cents)):
                fail(ln, 'syntax')
            if not noleadzero(cnt) or not noleadzero(cents):
                fail(ln, 'value')
            if int(cnt) != nrec or int(cents) != revenue:
                fail(ln, 'summary')
            if i + 1 < n:
                fail(ln + 1, 'summary')
            out = []
            out.append("venues %d events %d sold %d refunds %d" % (len(venues), len(events), nS, nR))
            out.append("revenue " + money(revenue))
            per = {}
            for ev, (vc, price, s) in events.items():
                p = per.setdefault(vc, [0, 0, 0])
                p[0] += 1
                p[1] += len(s)
                p[2] += len(s) * price
            for vc in sorted(venues):
                p = per.get(vc, [0, 0, 0])
                out.append("%s events=%d tickets=%d revenue=%s" % (vc.decode(), p[0], p[1], money(p[2])))
            top = sorted(events.items(), key=lambda kv: (-len(kv[1][2]), kv[0]))[:3]
            for ev, e in top:
                out.append("top %s %d" % (ev.decode(), len(e[2])))
            sys.stdout.write("\n".join(out) + "\n")
            return
        else:
            fail(ln, 'syntax')
    fail(n + 1, 'summary')


main()

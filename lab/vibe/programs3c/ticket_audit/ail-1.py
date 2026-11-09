import sys

EXIT = {'header': 2, 'syntax': 3, 'value': 4, 'reference': 5,
        'duplicate': 6, 'capacity': 7, 'summary': 8}


def fail(n, cat):
    print("line " + str(n) + ": " + cat)
    sys.exit(EXIT[cat])


def is_dig(s):
    if len(s) == 0:
        return False
    for c in s:
        if c < '0' or c > '9':
            return False
    return True


def is_upper(s):
    for c in s:
        if c < 'A' or c > 'Z':
            return False
    return True


def is_lower_or_dig(c):
    return ('a' <= c <= 'z') or ('0' <= c <= '9')


def days_in(y, m):
    if m == 2:
        return 29 if y % 4 == 0 else 28
    if m in (4, 6, 9, 11):
        return 30
    return 31


def zero_lead_ok(s):
    return not (len(s) > 1 and s[0] == '0')


# ---- syntax rules ----
def syn_code(s):
    return len(s) == 3 and is_upper(s)


def syn_name(s):
    n = len(s)
    if n < 1 or n > 40:
        return False
    for c in s:
        o = ord(c)
        if o < 32 or o > 126 or c == '|':
            return False
    if s[0] == ' ' or s[-1] == ' ':
        return False
    return True


def syn_cap(s):
    return 1 <= len(s) <= 6 and is_dig(s)


def syn_event(s):
    return len(s) == 6 and is_dig(s)


def syn_date(s):
    return (len(s) == 10 and s[4] == '-' and s[7] == '-'
            and is_dig(s[0:4]) and is_dig(s[5:7]) and is_dig(s[8:10]))


def syn_time(s):
    return len(s) == 5 and s[2] == ':' and is_dig(s[0:2]) and is_dig(s[3:5])


def syn_price(s):
    p = s.split('.')
    return (len(p) == 2 and 1 <= len(p[0]) <= 4 and is_dig(p[0])
            and len(p[1]) == 2 and is_dig(p[1]))


def syn_seat(s):
    return (2 <= len(s) <= 4 and 'A' <= s[0] <= 'Z' and is_dig(s[1:])
            and 1 <= len(s) - 1 <= 3)


def syn_buyer(s):
    if len(s) < 4 or len(s) > 12:
        return False
    for c in s:
        if not is_lower_or_dig(c):
            return False
    return 'a' <= s[0] <= 'z'


def syn_count(s):
    return 1 <= len(s) <= 9 and is_dig(s)


def syn_cents(s):
    return 1 <= len(s) <= 12 and is_dig(s)


# ---- value rules ----
def val_cap(s):
    return zero_lead_ok(s) and 1 <= int(s) <= 100000


def val_event(s):
    d = [int(c) for c in s]
    return (3 * d[0] + d[1] + 3 * d[2] + d[3] + 3 * d[4] + d[5]) % 10 == 0


def val_date(s):
    y = int(s[0:4])
    m = int(s[5:7])
    d = int(s[8:10])
    if y < 2000 or y > 2099:
        return False
    if m < 1 or m > 12:
        return False
    return 1 <= d <= days_in(y, m)


def val_time(s):
    return int(s[0:2]) <= 23 and int(s[3:5]) <= 59


def price_cents(s):
    p = s.split('.')
    return int(p[0]) * 100 + int(p[1])


def val_price(s):
    p = s.split('.')
    return zero_lead_ok(p[0]) and price_cents(s) % 5 == 0


def val_seat(s):
    num = s[1:]
    return num[0] != '0' and 1 <= int(num) <= 999


def val_count(s):
    return zero_lead_ok(s)


def money(c):
    return str(c // 100) + "." + str(c % 100).zfill(2)


def main():
    if len(sys.argv) != 2:
        sys.exit(1)
    try:
        with open(sys.argv[1], 'rb') as fh:
            data = fh.read()
    except Exception:
        sys.exit(1)

    text = data.decode('latin-1')
    lines = text.split('\n')
    if len(lines) > 0 and lines[-1] == '':
        lines.pop()

    if len(lines) == 0 or lines[0] != 'TKT/1':
        fail(1, 'header')

    venues = {}   # code -> capacity
    events = {}   # num -> (venue code, price cents)
    sold = {}     # num -> set of sold seats
    total = 0
    nrec = 0
    ns = 0
    nr = 0
    seen_end = False

    idx = 1
    while idx < len(lines):
        ln = idx + 1
        f = lines[idx].split('|')
        t = f[0]
        if t == 'V':
            if len(f) != 4:
                fail(ln, 'syntax')
            code, name, cap = f[1], f[2], f[3]
            if not (syn_code(code) and syn_name(name) and syn_cap(cap)):
                fail(ln, 'syntax')
            if not val_cap(cap):
                fail(ln, 'value')
            if code in venues:
                fail(ln, 'duplicate')
            venues[code] = int(cap)
            nrec += 1
        elif t == 'E':
            if len(f) != 6:
                fail(ln, 'syntax')
            num, ven, date, tm, price = f[1], f[2], f[3], f[4], f[5]
            if not (syn_event(num) and syn_code(ven) and syn_date(date)
                    and syn_time(tm) and syn_price(price)):
                fail(ln, 'syntax')
            if not (val_event(num) and val_date(date) and val_time(tm)
                    and val_price(price)):
                fail(ln, 'value')
            if ven not in venues:
                fail(ln, 'reference')
            if num in events:
                fail(ln, 'duplicate')
            events[num] = (ven, price_cents(price))
            sold[num] = set()
            nrec += 1
        elif t == 'S':
            if len(f) != 4:
                fail(ln, 'syntax')
            num, seat, buyer = f[1], f[2], f[3]
            if not (syn_event(num) and syn_seat(seat) and syn_buyer(buyer)):
                fail(ln, 'syntax')
            if not (val_event(num) and val_seat(seat)):
                fail(ln, 'value')
            if num not in events:
                fail(ln, 'reference')
            s_set = sold[num]
            if seat in s_set:
                fail(ln, 'duplicate')
            ven, pc = events[num]
            if len(s_set) >= venues[ven]:
                fail(ln, 'capacity')
            s_set.add(seat)
            total += pc
            ns += 1
            nrec += 1
        elif t == 'R':
            if len(f) != 3:
                fail(ln, 'syntax')
            num, seat = f[1], f[2]
            if not (syn_event(num) and syn_seat(seat)):
                fail(ln, 'syntax')
            if not (val_event(num) and val_seat(seat)):
                fail(ln, 'value')
            if num not in events or seat not in sold[num]:
                fail(ln, 'reference')
            sold[num].discard(seat)
            total -= events[num][1]
            nr += 1
            nrec += 1
        elif t == 'END':
            if len(f) != 3:
                fail(ln, 'syntax')
            count, cents = f[1], f[2]
            if not (syn_count(count) and syn_cents(cents)):
                fail(ln, 'syntax')
            if not (val_count(count) and zero_lead_ok(cents)):
                fail(ln, 'value')
            if int(count) != nrec or int(cents) != total:
                fail(ln, 'summary')
            seen_end = True
            if idx + 1 < len(lines):
                fail(ln + 1, 'summary')
            break
        else:
            fail(ln, 'syntax')
        idx += 1

    if not seen_end:
        fail(len(lines) + 1, 'summary')

    print("venues " + str(len(venues)) + " events " + str(len(events))
          + " sold " + str(ns) + " refunds " + str(nr))
    print("revenue " + money(total))

    stats = {}
    for code in venues:
        stats[code] = [0, 0, 0]
    for num in events:
        ven, pc = events[num]
        k = len(sold[num])
        st = stats[ven]
        st[0] += 1
        st[1] += k
        st[2] += k * pc
    for code in sorted(venues.keys()):
        st = stats[code]
        print(code + " events=" + str(st[0]) + " tickets=" + str(st[1])
              + " revenue=" + money(st[2]))

    ranking = sorted(events.keys(), key=lambda num: (-len(sold[num]), num))
    for num in ranking[:3]:
        print("top " + num + " " + str(len(sold[num])))


main()

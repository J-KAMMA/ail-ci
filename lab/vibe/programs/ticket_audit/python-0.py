import sys


def fail(line, category, status):
    sys.stdout.write(f"line {line}: {category}\n")
    sys.exit(status)


def digits(f):
    return all(48 <= c <= 57 for c in f)


def val_ok(f):
    return True


def syn_venue(f):
    return len(f) == 3 and all(65 <= c <= 90 for c in f)


def syn_name(f):
    if not (1 <= len(f) <= 40):
        return False
    if f[0] == 32 or f[-1] == 32:
        return False
    return all(0x20 <= c <= 0x7E and c != 0x7C for c in f)


def syn_capacity(f):
    return 1 <= len(f) <= 6 and digits(f)


def val_capacity(f):
    if len(f) > 1 and f[0] == 48:
        return False
    v = int(f)
    return 1 <= v <= 100000


def syn_event(f):
    return len(f) == 6 and digits(f)


def val_event(f):
    d = [c - 48 for c in f]
    return (3 * d[0] + d[1] + 3 * d[2] + d[3] + 3 * d[4] + d[5]) % 10 == 0


def syn_date(f):
    if len(f) != 10:
        return False
    if f[4] != 45 or f[7] != 45:
        return False
    return all(48 <= f[i] <= 57 for i in (0, 1, 2, 3, 5, 6, 8, 9))


def val_date(f):
    year = int(f[0:4])
    month = int(f[5:7])
    day = int(f[8:10])

    if not (2000 <= year <= 2099):
        return False
    if not (1 <= month <= 12):
        return False

    if month == 2:
        max_day = 29 if year % 4 == 0 else 28
    elif month in (4, 6, 9, 11):
        max_day = 30
    else:
        max_day = 31

    return 1 <= day <= max_day


def syn_time(f):
    return (
        len(f) == 5
        and f[2] == 58
        and all(48 <= f[i] <= 57 for i in (0, 1, 3, 4))
    )


def val_time(f):
    hour = int(f[0:2])
    minute = int(f[3:5])
    return 0 <= hour <= 23 and 0 <= minute <= 59


def syn_price(f):
    if not (4 <= len(f) <= 7):
        return False
    dot = len(f) - 3
    if f[dot] != 46:
        return False
    return digits(f[:dot]) and digits(f[dot + 1:])


def val_price(f):
    dot = f.index(46)
    whole = f[:dot]
    cents = f[dot + 1:]

    if len(whole) > 1 and whole[0] == 48:
        return False

    amount = int(whole) * 100 + int(cents)
    return amount % 5 == 0


def price_cents(f):
    dot = f.index(46)
    return int(f[:dot]) * 100 + int(f[dot + 1:])


def syn_seat(f):
    return (
        2 <= len(f) <= 4
        and 65 <= f[0] <= 90
        and digits(f[1:])
    )


def val_seat(f):
    number = f[1:]
    if len(number) > 1 and number[0] == 48:
        return False
    return 1 <= int(number) <= 999


def syn_buyer(f):
    if not (4 <= len(f) <= 12):
        return False
    if not (97 <= f[0] <= 122):
        return False
    return all(97 <= c <= 122 or 48 <= c <= 57 for c in f)


def syn_count(f):
    return 1 <= len(f) <= 9 and digits(f)


def syn_cents(f):
    return 1 <= len(f) <= 12 and digits(f)


def val_no_leading_zero(f):
    return len(f) == 1 or f[0] != 48


FIELD_RULES = {
    b"V": [
        (syn_venue, val_ok),
        (syn_name, val_ok),
        (syn_capacity, val_capacity),
    ],
    b"E": [
        (syn_event, val_event),
        (syn_venue, val_ok),
        (syn_date, val_date),
        (syn_time, val_time),
        (syn_price, val_price),
    ],
    b"S": [
        (syn_event, val_event),
        (syn_seat, val_seat),
        (syn_buyer, val_ok),
    ],
    b"R": [
        (syn_event, val_event),
        (syn_seat, val_seat),
    ],
    b"END": [
        (syn_count, val_no_leading_zero),
        (syn_cents, val_no_leading_zero),
    ],
}


def money(cents):
    return f"{cents // 100}.{cents % 100:02d}"


def emit_success(venues, events, sold, s_count, r_count, revenue):
    out = []
    out.append(
        f"venues {len(venues)} events {len(events)} "
        f"sold {s_count} refunds {r_count}"
    )
    out.append(f"revenue {money(revenue)}")

    stats = {code: [0, 0, 0] for code in venues}

    for event, (venue_code, price) in events.items():
        stat = stats[venue_code]
        sold_count = len(sold[event])
        stat[0] += 1
        stat[1] += sold_count
        stat[2] += sold_count * price

    for code in sorted(venues):
        n, t, r = stats[code]
        out.append(
            f"{code.decode('ascii')} events={n} tickets={t} revenue={money(r)}"
        )

    top_events = sorted(
        events,
        key=lambda event: (-len(sold[event]), event),
    )[:3]

    for event in top_events:
        out.append(f"top {event.decode('ascii')} {len(sold[event])}")

    sys.stdout.write("\n".join(out) + "\n")


def main():
    if len(sys.argv) != 2:
        return 1

    try:
        with open(sys.argv[1], "rb") as f:
            data = f.read()
    except (OSError, ValueError):
        return 1

    lines = data.split(b"\n")
    if data.endswith(b"\n"):
        lines.pop()

    if not lines or lines[0] != b"TKT/1":
        fail(1, "header", 2)

    venues = {}
    events = {}
    sold = {}

    record_count = 0
    s_count = 0
    r_count = 0
    revenue = 0

    for index in range(1, len(lines)):
        line_number = index + 1
        fields = lines[index].split(b"|")
        record_type = fields[0]

        if record_type not in FIELD_RULES:
            fail(line_number, "syntax", 3)

        rules = FIELD_RULES[record_type]

        if len(fields) != len(rules) + 1:
            fail(line_number, "syntax", 3)

        for i, (syntax_check, _) in enumerate(rules, start=1):
            if not syntax_check(fields[i]):
                fail(line_number, "syntax", 3)

        for i, (_, value_check) in enumerate(rules, start=1):
            if not value_check(fields[i]):
                fail(line_number, "value", 4)

        if record_type == b"V":
            code = fields[1]
            capacity = int(fields[3])

            if code in venues:
                fail(line_number, "duplicate", 6)

            venues[code] = capacity
            record_count += 1

        elif record_type == b"E":
            event = fields[1]
            venue_code = fields[2]
            price = price_cents(fields[5])

            if venue_code not in venues:
                fail(line_number, "reference", 5)
            if event in events:
                fail(line_number, "duplicate", 6)

            events[event] = (venue_code, price)
            sold[event] = set()
            record_count += 1

        elif record_type == b"S":
            event = fields[1]
            seat = fields[2]

            if event not in events:
                fail(line_number, "reference", 5)
            if seat in sold[event]:
                fail(line_number, "duplicate", 6)

            venue_code, price = events[event]
            if len(sold[event]) >= venues[venue_code]:
                fail(line_number, "capacity", 7)

            sold[event].add(seat)
            revenue += price
            s_count += 1
            record_count += 1

        elif record_type == b"R":
            event = fields[1]
            seat = fields[2]

            if event not in events or seat not in sold[event]:
                fail(line_number, "reference", 5)

            sold[event].remove(seat)
            revenue -= events[event][1]
            r_count += 1
            record_count += 1

        else:
            count = int(fields[1])
            cents = int(fields[2])

            if count != record_count or cents != revenue:
                fail(line_number, "summary", 8)

            if index + 1 < len(lines):
                fail(index + 2, "summary", 8)

            emit_success(venues, events, sold, s_count, r_count, revenue)
            return 0

    fail(len(lines) + 1, "summary", 8)


if __name__ == "__main__":
    sys.exit(main())

import sys


def money(cents):
    return f"{cents // 100}.{cents % 100:02d}"


def is_digits(b, lo, hi):
    return lo <= len(b) <= hi and all(48 <= ch <= 57 for ch in b)


def no_leading_zero(b):
    return len(b) == 1 or b[0] != 48


def is_venue_code(b):
    return len(b) == 3 and all(65 <= ch <= 90 for ch in b)


def is_name(b):
    return (
        1 <= len(b) <= 40
        and all(32 <= ch <= 126 and ch != 124 for ch in b)
        and b[0] != 32
        and b[-1] != 32
    )


def capacity_value(b):
    return no_leading_zero(b) and 1 <= int(b) <= 100000


def event_value(b):
    d = [ch - 48 for ch in b]
    return (3 * d[0] + d[1] + 3 * d[2] + d[3] + 3 * d[4] + d[5]) % 10 == 0


def is_date_syntax(b):
    return (
        len(b) == 10
        and b[4] == 45
        and b[7] == 45
        and is_digits(b[0:4], 4, 4)
        and is_digits(b[5:7], 2, 2)
        and is_digits(b[8:10], 2, 2)
    )


def date_value(b):
    year = int(b[0:4])
    month = int(b[5:7])
    day = int(b[8:10])

    if year < 2000 or year > 2099 or month < 1 or month > 12:
        return False

    days = [31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31]
    last = days[month - 1]
    if month == 2 and year % 4 == 0:
        last = 29
    return 1 <= day <= last


def is_time_syntax(b):
    return (
        len(b) == 5
        and b[2] == 58
        and is_digits(b[0:2], 2, 2)
        and is_digits(b[3:5], 2, 2)
    )


def time_value(b):
    hour = int(b[0:2])
    minute = int(b[3:5])
    return 0 <= hour <= 23 and 0 <= minute <= 59


def is_price_syntax(b):
    parts = b.split(b".")
    return (
        len(parts) == 2
        and is_digits(parts[0], 1, 4)
        and is_digits(parts[1], 2, 2)
    )


def price_value(b):
    whole, frac = b.split(b".")
    if len(whole) > 1 and whole[0] == 48:
        return False, 0
    cents = int(whole) * 100 + int(frac)
    return cents % 5 == 0, cents


def is_seat_syntax(b):
    return (
        2 <= len(b) <= 4
        and 65 <= b[0] <= 90
        and all(48 <= ch <= 57 for ch in b[1:])
    )


def seat_value(b):
    digits = b[1:]
    if len(digits) > 1 and digits[0] == 48:
        return False
    return int(digits) >= 1


def is_buyer_syntax(b):
    if not (4 <= len(b) <= 12):
        return False
    if not (97 <= b[0] <= 122):
        return False
    return all((97 <= ch <= 122) or (48 <= ch <= 57) for ch in b[1:])


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

    def fail(line_no, category, status):
        sys.stdout.write(f"line {line_no}: {category}\n")
        sys.exit(status)

    if not lines or lines[0] != b"TKT/1":
        fail(1, "header", 2)

    venues = {}
    events = {}
    sold = {}

    sold_records = 0
    refund_records = 0
    record_count = 0
    revenue = 0

    i = 1
    while i < len(lines):
        line = lines[i]
        line_no = i + 1
        fields = line.split(b"|")
        typ = fields[0]

        if typ == b"V":
            if len(fields) != 4:
                fail(line_no, "syntax", 3)

            code, name, cap = fields[1], fields[2], fields[3]

            if not (
                is_venue_code(code)
                and is_name(name)
                and is_digits(cap, 1, 6)
            ):
                fail(line_no, "syntax", 3)

            if not capacity_value(cap):
                fail(line_no, "value", 4)

            if code in venues:
                fail(line_no, "duplicate", 6)

            venues[code] = int(cap)
            record_count += 1

        elif typ == b"E":
            if len(fields) != 6:
                fail(line_no, "syntax", 3)

            ev, vc, dt, tm, pr = (
                fields[1],
                fields[2],
                fields[3],
                fields[4],
                fields[5],
            )

            if not (
                is_digits(ev, 6, 6)
                and is_venue_code(vc)
                and is_date_syntax(dt)
                and is_time_syntax(tm)
                and is_price_syntax(pr)
            ):
                fail(line_no, "syntax", 3)

            if not event_value(ev):
                fail(line_no, "value", 4)
            if not date_value(dt):
                fail(line_no, "value", 4)
            if not time_value(tm):
                fail(line_no, "value", 4)

            price_ok, price = price_value(pr)
            if not price_ok:
                fail(line_no, "value", 4)

            if vc not in venues:
                fail(line_no, "reference", 5)
            if ev in events:
                fail(line_no, "duplicate", 6)

            events[ev] = (vc, price)
            sold[ev] = set()
            record_count += 1

        elif typ == b"S":
            if len(fields) != 4:
                fail(line_no, "syntax", 3)

            ev, seat, buyer = fields[1], fields[2], fields[3]

            if not (
                is_digits(ev, 6, 6)
                and is_seat_syntax(seat)
                and is_buyer_syntax(buyer)
            ):
                fail(line_no, "syntax", 3)

            if not event_value(ev):
                fail(line_no, "value", 4)
            if not seat_value(seat):
                fail(line_no, "value", 4)

            if ev not in events:
                fail(line_no, "reference", 5)
            if seat in sold[ev]:
                fail(line_no, "duplicate", 6)

            venue_code = events[ev][0]
            if len(sold[ev]) >= venues[venue_code]:
                fail(line_no, "capacity", 7)

            sold[ev].add(seat)
            revenue += events[ev][1]
            sold_records += 1
            record_count += 1

        elif typ == b"R":
            if len(fields) != 3:
                fail(line_no, "syntax", 3)

            ev, seat = fields[1], fields[2]

            if not (is_digits(ev, 6, 6) and is_seat_syntax(seat)):
                fail(line_no, "syntax", 3)

            if not event_value(ev):
                fail(line_no, "value", 4)
            if not seat_value(seat):
                fail(line_no, "value", 4)

            if ev not in events or seat not in sold[ev]:
                fail(line_no, "reference", 5)

            sold[ev].remove(seat)
            revenue -= events[ev][1]
            refund_records += 1
            record_count += 1

        elif typ == b"END":
            if len(fields) != 3:
                fail(line_no, "syntax", 3)

            count, cents = fields[1], fields[2]

            if not (is_digits(count, 1, 9) and is_digits(cents, 1, 12)):
                fail(line_no, "syntax", 3)

            if not (no_leading_zero(count) and no_leading_zero(cents)):
                fail(line_no, "value", 4)

            if int(count) != record_count or int(cents) != revenue:
                fail(line_no, "summary", 8)

            if i + 1 < len(lines):
                fail(i + 2, "summary", 8)

            per_venue = {code: [0, 0, 0] for code in venues}
            for ev, (vc, price) in events.items():
                tickets = len(sold[ev])
                per_venue[vc][0] += 1
                per_venue[vc][1] += tickets
                per_venue[vc][2] += tickets * price

            out = [
                f"venues {len(venues)} events {len(events)} sold {sold_records} refunds {refund_records}\n",
                f"revenue {money(revenue)}\n",
            ]

            for code in sorted(venues):
                event_count, tickets, venue_revenue = per_venue[code]
                out.append(
                    f"{code.decode('ascii')} events={event_count} tickets={tickets} "
                    f"revenue={money(venue_revenue)}\n"
                )

            top_events = sorted(
                events,
                key=lambda ev: (-len(sold[ev]), ev),
            )[:3]

            for ev in top_events:
                out.append(f"top {ev.decode('ascii')} {len(sold[ev])}\n")

            sys.stdout.write("".join(out))
            return 0

        else:
            fail(line_no, "syntax", 3)

        i += 1

    fail(len(lines) + 1, "summary", 8)


if __name__ == "__main__":
    sys.exit(main())

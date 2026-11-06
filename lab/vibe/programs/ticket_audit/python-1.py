import sys


def is_digits(value, minimum, maximum):
    if not (minimum <= len(value) <= maximum):
        return False
    for c in value:
        if c < 48 or c > 57:
            return False
    return True


def has_leading_zero(value):
    return len(value) > 1 and value[0] == 48


def is_venue_code(value):
    return len(value) == 3 and all(65 <= c <= 90 for c in value)


def is_name(value):
    if not (1 <= len(value) <= 40):
        return False
    for c in value:
        if c < 0x20 or c > 0x7E or c == 0x7C:
            return False
    return value[0] != 0x20 and value[-1] != 0x20


def is_date_syntax(value):
    if len(value) != 10 or value[4] != 45 or value[7] != 45:
        return False
    return (
        is_digits(value[0:4], 4, 4)
        and is_digits(value[5:7], 2, 2)
        and is_digits(value[8:10], 2, 2)
    )


def is_time_syntax(value):
    return (
        len(value) == 5
        and value[2] == 58
        and is_digits(value[0:2], 2, 2)
        and is_digits(value[3:5], 2, 2)
    )


def is_price_syntax(value):
    if value.count(b".") != 1:
        return False
    dot = value.index(b".")
    return is_digits(value[:dot], 1, 4) and is_digits(value[dot + 1:], 2, 2)


def is_seat_syntax(value):
    if not (2 <= len(value) <= 4):
        return False
    if not (65 <= value[0] <= 90):
        return False
    return is_digits(value[1:], 1, 3)


def is_buyer_syntax(value):
    if not (4 <= len(value) <= 12):
        return False
    if not (97 <= value[0] <= 122):
        return False
    for c in value[1:]:
        if not ((97 <= c <= 122) or (48 <= c <= 57)):
            return False
    return True


def event_value(value):
    weights = (3, 1, 3, 1, 3, 1)
    total = 0
    for i, c in enumerate(value):
        total += (c - 48) * weights[i]
    return total % 10 == 0


def date_value(value):
    year = int(value[0:4])
    month = int(value[5:7])
    day = int(value[8:10])

    if year < 2000 or year > 2099:
        return False
    if month < 1 or month > 12:
        return False

    if month == 2:
        maximum = 29 if year % 4 == 0 else 28
    elif month in (4, 6, 9, 11):
        maximum = 30
    else:
        maximum = 31

    return 1 <= day <= maximum


def time_value(value):
    hour = int(value[0:2])
    minute = int(value[3:5])
    return 0 <= hour <= 23 and 0 <= minute <= 59


def price_value(value):
    dot = value.index(b".")
    whole = value[:dot]
    if has_leading_zero(whole):
        return False
    cents = int(whole) * 100 + int(value[dot + 1:])
    return cents % 5 == 0


def price_cents(value):
    dot = value.index(b".")
    return int(value[:dot]) * 100 + int(value[dot + 1:])


def seat_value(value):
    number = value[1:]
    if has_leading_zero(number):
        return False
    return 1 <= int(number) <= 999


def money(cents):
    return f"{cents // 100}.{cents % 100:02d}"


def output_success(venues, events, venue_stats, sold_count, refund_count, revenue):
    result = []
    result.append(
        f"venues {len(venues)} events {len(events)} "
        f"sold {sold_count} refunds {refund_count}"
    )
    result.append(f"revenue {money(revenue)}")

    for code in sorted(venues):
        event_count, tickets, venue_revenue = venue_stats[code]
        result.append(
            f"{code.decode('ascii')} events={event_count} "
            f"tickets={tickets} revenue={money(venue_revenue)}"
        )

    ranked = sorted(
        events,
        key=lambda event: (-len(events[event][2]), event)
    )

    for event in ranked[:3]:
        result.append(f"top {event.decode('ascii')} {len(events[event][2])}")

    sys.stdout.write("\n".join(result) + "\n")


def main():
    if len(sys.argv) != 2:
        return 1

    try:
        with open(sys.argv[1], "rb") as handle:
            data = handle.read()
    except OSError:
        return 1

    lines = data.split(b"\n")
    if data.endswith(b"\n"):
        lines.pop()

    if not lines or lines[0] != b"TKT/1":
        print("line 1: header")
        return 2

    venues = {}
    events = {}
    venue_stats = {}

    revenue = 0
    record_count = 0
    sold_count = 0
    refund_count = 0

    for index in range(1, len(lines)):
        line_number = index + 1
        fields = lines[index].split(b"|")
        record_type = fields[0]

        if record_type == b"V":
            if len(fields) != 4:
                print(f"line {line_number}: syntax")
                return 3

            code, name, capacity = fields[1], fields[2], fields[3]

            if not (is_venue_code(code) and is_name(name) and is_digits(capacity, 1, 6)):
                print(f"line {line_number}: syntax")
                return 3

            if has_leading_zero(capacity):
                print(f"line {line_number}: value")
                return 4

            capacity_number = int(capacity)
            if capacity_number < 1 or capacity_number > 100000:
                print(f"line {line_number}: value")
                return 4

            if code in venues:
                print(f"line {line_number}: duplicate")
                return 6

            venues[code] = capacity_number
            venue_stats[code] = [0, 0, 0]
            record_count += 1

        elif record_type == b"E":
            if len(fields) != 6:
                print(f"line {line_number}: syntax")
                return 3

            event, venue, date, time, price = fields[1:6]

            if not (
                is_digits(event, 6, 6)
                and is_venue_code(venue)
                and is_date_syntax(date)
                and is_time_syntax(time)
                and is_price_syntax(price)
            ):
                print(f"line {line_number}: syntax")
                return 3

            if not event_value(event):
                print(f"line {line_number}: value")
                return 4
            if not date_value(date):
                print(f"line {line_number}: value")
                return 4
            if not time_value(time):
                print(f"line {line_number}: value")
                return 4
            if not price_value(price):
                print(f"line {line_number}: value")
                return 4

            if venue not in venues:
                print(f"line {line_number}: reference")
                return 5

            if event in events:
                print(f"line {line_number}: duplicate")
                return 6

            events[event] = [venue, price_cents(price), set()]
            venue_stats[venue][0] += 1
            record_count += 1

        elif record_type == b"S":
            if len(fields) != 4:
                print(f"line {line_number}: syntax")
                return 3

            event, seat, buyer = fields[1], fields[2], fields[3]

            if not (
                is_digits(event, 6, 6)
                and is_seat_syntax(seat)
                and is_buyer_syntax(buyer)
            ):
                print(f"line {line_number}: syntax")
                return 3

            if not event_value(event):
                print(f"line {line_number}: value")
                return 4
            if not seat_value(seat):
                print(f"line {line_number}: value")
                return 4

            if event not in events:
                print(f"line {line_number}: reference")
                return 5

            event_data = events[event]
            venue = event_data[0]
            price = event_data[1]
            sold_seats = event_data[2]

            if seat in sold_seats:
                print(f"line {line_number}: duplicate")
                return 6

            if len(sold_seats) >= venues[venue]:
                print(f"line {line_number}: capacity")
                return 7

            sold_seats.add(seat)
            revenue += price

            stats = venue_stats[venue]
            stats[1] += 1
            stats[2] += price

            sold_count += 1
            record_count += 1

        elif record_type == b"R":
            if len(fields) != 3:
                print(f"line {line_number}: syntax")
                return 3

            event, seat = fields[1], fields[2]

            if not (is_digits(event, 6, 6) and is_seat_syntax(seat)):
                print(f"line {line_number}: syntax")
                return 3

            if not event_value(event):
                print(f"line {line_number}: value")
                return 4
            if not seat_value(seat):
                print(f"line {line_number}: value")
                return 4

            if event not in events or seat not in events[event][2]:
                print(f"line {line_number}: reference")
                return 5

            event_data = events[event]
            venue = event_data[0]
            price = event_data[1]
            event_data[2].remove(seat)

            revenue -= price

            stats = venue_stats[venue]
            stats[1] -= 1
            stats[2] -= price

            refund_count += 1
            record_count += 1

        elif record_type == b"END":
            if len(fields) != 3:
                print(f"line {line_number}: syntax")
                return 3

            count, cents = fields[1], fields[2]

            if not (is_digits(count, 1, 9) and is_digits(cents, 1, 12)):
                print(f"line {line_number}: syntax")
                return 3

            if has_leading_zero(count) or has_leading_zero(cents):
                print(f"line {line_number}: value")
                return 4

            if int(count) != record_count or int(cents) != revenue:
                print(f"line {line_number}: summary")
                return 8

            if index < len(lines) - 1:
                print(f"line {line_number + 1}: summary")
                return 8

            output_success(
                venues,
                events,
                venue_stats,
                sold_count,
                refund_count,
                revenue,
            )
            return 0

        else:
            print(f"line {line_number}: syntax")
            return 3

    print(f"line {len(lines) + 1}: summary")
    return 8


if __name__ == "__main__":
    sys.exit(main())

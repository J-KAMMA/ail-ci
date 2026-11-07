import sys


def is_digits(s: str, lo: int, hi: int) -> bool:
    n: int = len(s)
    if n < lo or n > hi:
        return False
    i: int = 0
    while i < n:
        c: int = ord(s[i])
        if c < 48 or c > 57:
            return False
        i += 1
    return True


def no_leading_zero(s: str) -> bool:
    if len(s) > 1 and s[0] == "0":
        return False
    return True


def is_venue_code(s: str) -> bool:
    if len(s) != 3:
        return False
    i: int = 0
    while i < 3:
        c: int = ord(s[i])
        if c < 65 or c > 90:
            return False
        i += 1
    return True


def is_name(s: str) -> bool:
    n: int = len(s)
    if n < 1 or n > 40:
        return False
    if s[0] == " " or s[n - 1] == " ":
        return False
    i: int = 0
    while i < n:
        c: int = ord(s[i])
        if c < 32 or c > 126:
            return False
        if c == 124:
            return False
        i += 1
    return True


def event_value(s: str) -> bool:
    d1: int = ord(s[0]) - 48
    d2: int = ord(s[1]) - 48
    d3: int = ord(s[2]) - 48
    d4: int = ord(s[3]) - 48
    d5: int = ord(s[4]) - 48
    d6: int = ord(s[5]) - 48
    total: int = 3 * d1 + d2 + 3 * d3 + d4 + 3 * d5 + d6
    if total % 10 != 0:
        return False
    return True


def date_syntax(s: str) -> bool:
    if len(s) != 10:
        return False
    if not is_digits(s[0:4], 4, 4):
        return False
    if s[4] != "-":
        return False
    if not is_digits(s[5:7], 2, 2):
        return False
    if s[7] != "-":
        return False
    if not is_digits(s[8:10], 2, 2):
        return False
    return True


def date_value(s: str) -> bool:
    year: int = int(s[0:4])
    month: int = int(s[5:7])
    day: int = int(s[8:10])
    if year < 2000 or year > 2099:
        return False
    if month < 1 or month > 12:
        return False
    maxd: int = 31
    if month == 4 or month == 6 or month == 9 or month == 11:
        maxd = 30
    elif month == 2:
        if year % 4 == 0:
            maxd = 29
        else:
            maxd = 28
    if day < 1 or day > maxd:
        return False
    return True


def time_syntax(s: str) -> bool:
    if len(s) != 5:
        return False
    if not is_digits(s[0:2], 2, 2):
        return False
    if s[2] != ":":
        return False
    if not is_digits(s[3:5], 2, 2):
        return False
    return True


def time_value(s: str) -> bool:
    hh: int = int(s[0:2])
    mm: int = int(s[3:5])
    if hh > 23:
        return False
    if mm > 59:
        return False
    return True


def price_syntax(s: str) -> bool:
    n: int = len(s)
    i: int = 0
    dot: int = -1
    count_dot: int = 0
    while i < n:
        if s[i] == ".":
            dot = i
            count_dot += 1
        i += 1
    if count_dot != 1:
        return False
    if dot < 1 or dot > 4:
        return False
    if n - dot - 1 != 2:
        return False
    if not is_digits(s[0:dot], 1, 4):
        return False
    if not is_digits(s[dot + 1:n], 2, 2):
        return False
    return True


def price_value(s: str) -> bool:
    n: int = len(s)
    i: int = 0
    dot: int = -1
    while i < n:
        if s[i] == ".":
            dot = i
            break
        i += 1
    if dot < 0:
        return False
    ip: str = s[0:dot]
    fp: str = s[dot + 1:n]
    if len(ip) > 1 and ip[0] == "0":
        return False
    cents: int = int(ip) * 100 + int(fp)
    if cents % 5 != 0:
        return False
    return True


def price_cents(s: str) -> int:
    n: int = len(s)
    i: int = 0
    dot: int = -1
    while i < n:
        if s[i] == ".":
            dot = i
            break
        i += 1
    ip: str = s[0:dot]
    fp: str = s[dot + 1:n]
    return int(ip) * 100 + int(fp)


def seat_syntax(s: str) -> bool:
    n: int = len(s)
    if n < 2 or n > 4:
        return False
    c: int = ord(s[0])
    if c < 65 or c > 90:
        return False
    return is_digits(s[1:n], 1, 3)


def seat_value(s: str) -> bool:
    if s[1] == "0":
        return False
    return True


def buyer_syntax(s: str) -> bool:
    n: int = len(s)
    if n < 4 or n > 12:
        return False
    c0: int = ord(s[0])
    if c0 < 97 or c0 > 122:
        return False
    i: int = 1
    while i < n:
        c: int = ord(s[i])
        if (c >= 97 and c <= 122) or (c >= 48 and c <= 57):
            i += 1
        else:
            return False
    return True


def money(x: int) -> str:
    units: int = x // 100
    frac: int = x % 100
    if frac < 10:
        return str(units) + ".0" + str(frac)
    return str(units) + "." + str(frac)


def top_key(r: tuple[str, int]) -> tuple[int, str]:
    return (-r[1], r[0])


def fail(lineno: int, cat: str, status: int) -> int:
    print("line " + str(lineno) + ": " + cat)
    return status


def main() -> int:
    if len(sys.argv) != 2:
        return 1
    path: str = sys.argv[1]
    data: bytes = b""
    try:
        with open(path, "rb") as f:
            data = f.read()
    except OSError:
        return 1

    lines: list[str] = []
    if len(data) > 0:
        text: str = data.decode("latin-1")
        parts: list[str] = text.split("\n")
        last: int = len(parts) - 1
        if parts[last] == "":
            parts = parts[0:last]
        lines = parts

    if len(lines) < 1 or lines[0] != "TKT/1":
        return fail(1, "header", 2)

    venue_list: list[tuple[str, int]] = []
    venue_index: dict[str, int] = {}
    venue_event_count: list[int] = []
    venue_sold: list[int] = []
    venue_rev: list[int] = []

    event_list: list[tuple[str, int, int]] = []
    event_index: dict[str, int] = {}
    sold_count: list[int] = []

    sold_set: set[tuple[int, int]] = set()

    revenue: int = 0
    record_count: int = 0
    sold_records: int = 0
    refund_records: int = 0

    nlines: int = len(lines)
    i: int = 1
    while i < nlines:
        line: str = lines[i]
        lineno: int = i + 1
        fields: list[str] = line.split("|")
        typ: str = fields[0]
        expected: int = -1
        if typ == "V":
            expected = 4
        elif typ == "E":
            expected = 6
        elif typ == "S":
            expected = 4
        elif typ == "R":
            expected = 3
        elif typ == "END":
            expected = 3
        if expected < 0 or len(fields) != expected:
            return fail(lineno, "syntax", 3)

        if typ == "V":
            code: str = fields[1]
            name: str = fields[2]
            capstr: str = fields[3]
            if not is_venue_code(code) or not is_name(name) or not is_digits(capstr, 1, 6):
                return fail(lineno, "syntax", 3)
            capval: int = 0
            bad: bool = False
            if not no_leading_zero(capstr):
                bad = True
            else:
                capval = int(capstr)
                if capval < 1 or capval > 100000:
                    bad = True
            if bad:
                return fail(lineno, "value", 4)
            if code in venue_index:
                return fail(lineno, "duplicate", 6)
            vi: int = len(venue_list)
            venue_index[code] = vi
            venue_list.append((code, capval))
            venue_event_count.append(0)
            venue_sold.append(0)
            venue_rev.append(0)
            record_count += 1
        elif typ == "E":
            ev: str = fields[1]
            vcode: str = fields[2]
            dstr: str = fields[3]
            tstr: str = fields[4]
            pstr: str = fields[5]
            if not is_digits(ev, 6, 6) or not is_venue_code(vcode) or not date_syntax(dstr) or not time_syntax(tstr) or not price_syntax(pstr):
                return fail(lineno, "syntax", 3)
            if not event_value(ev) or not date_value(dstr) or not time_value(tstr) or not price_value(pstr):
                return fail(lineno, "value", 4)
            if vcode not in venue_index:
                return fail(lineno, "reference", 5)
            if ev in event_index:
                return fail(lineno, "duplicate", 6)
            vi = venue_index[vcode]
            event_index[ev] = len(event_list)
            event_list.append((ev, vi, price_cents(pstr)))
            sold_count.append(0)
            venue_event_count[vi] += 1
            record_count += 1
        elif typ == "S":
            ev = fields[1]
            seat: str = fields[2]
            buyer: str = fields[3]
            if not is_digits(ev, 6, 6) or not seat_syntax(seat) or not buyer_syntax(buyer):
                return fail(lineno, "syntax", 3)
            if not event_value(ev) or not seat_value(seat):
                return fail(lineno, "value", 4)
            if ev not in event_index:
                return fail(lineno, "reference", 5)
            ei: int = event_index[ev]
            snum: int = int(seat[1:])
            key: tuple[int, int] = (ei, snum)
            if key in sold_set:
                return fail(lineno, "duplicate", 6)
            vi = event_list[ei][1]
            if sold_count[ei] >= venue_list[vi][1]:
                return fail(lineno, "capacity", 7)
            sold_set.add(key)
            sold_count[ei] += 1
            venue_sold[vi] += 1
            pcents: int = event_list[ei][2]
            revenue += pcents
            venue_rev[vi] += pcents
            sold_records += 1
            record_count += 1
        elif typ == "R":
            ev = fields[1]
            seat = fields[2]
            if not is_digits(ev, 6, 6) or not seat_syntax(seat):
                return fail(lineno, "syntax", 3)
            if not event_value(ev) or not seat_value(seat):
                return fail(lineno, "value", 4)
            if ev not in event_index:
                return fail(lineno, "reference", 5)
            ei = event_index[ev]
            snum = int(seat[1:])
            key = (ei, snum)
            if key not in sold_set:
                return fail(lineno, "reference", 5)
            sold_set.remove(key)
            sold_count[ei] -= 1
            vi = event_list[ei][1]
            venue_sold[vi] -= 1
            pcents = event_list[ei][2]
            revenue -= pcents
            venue_rev[vi] -= pcents
            refund_records += 1
            record_count += 1
        else:
            cstr: str = fields[1]
            xstr: str = fields[2]
            if not is_digits(cstr, 1, 9) or not is_digits(xstr, 1, 12):
                return fail(lineno, "syntax", 3)
            if not no_leading_zero(cstr) or not no_leading_zero(xstr):
                return fail(lineno, "value", 4)
            cval: int = int(cstr)
            xval: int = int(xstr)
            if cval != record_count or xval != revenue:
                return fail(lineno, "summary", 8)
            if i + 1 < nlines:
                return fail(lineno + 1, "summary", 8)

            out: list[str] = []
            out.append("venues " + str(len(venue_list)) + " events " + str(len(event_list)) + " sold " + str(sold_records) + " refunds " + str(refund_records))
            out.append("revenue " + money(revenue))

            codes: list[str] = []
            k: int = 0
            while k < len(venue_list):
                codes.append(venue_list[k][0])
                k += 1
            codes.sort()
            k = 0
            while k < len(codes):
                vj: int = venue_index[codes[k]]
                out.append(codes[k] + " events=" + str(venue_event_count[vj]) + " tickets=" + str(venue_sold[vj]) + " revenue=" + money(venue_rev[vj]))
                k += 1

            rows: list[tuple[str, int]] = []
            k = 0
            while k < len(event_list):
                rows.append((event_list[k][0], sold_count[k]))
                k += 1
            rows.sort(key=top_key)
            k = 0
            while k < len(rows) and k < 3:
                out.append("top " + rows[k][0] + " " + str(rows[k][1]))
                k += 1

            k = 0
            while k < len(out):
                print(out[k])
                k += 1
            return 0

        i += 1

    return fail(nlines + 1, "summary", 8)


if __name__ == "__main__":
    sys.exit(main())

"""The runtime of `datetime` (library batch 4), written in the Python subset the compiler builds.

It is plain Python: CPython runs this file as a module (the test suite compares every function with the
`datetime` module on generated values) and dtlib.py appends the functions a program uses to the program
itself, after the class definition below. One class stands for the four value types:

    kind 0  datetime.date        k = ordinal * 86400000000
    kind 1  datetime.datetime    k = ordinal * 86400000000 + microseconds since midnight
    kind 2  datetime.timedelta   k = total microseconds
    kind 3  datetime.time        k = microseconds since midnight

so a comparison is a comparison of `k`, and a subtraction of two dates is a subtraction of two `k`. Every
field of every kind exists (the ones that do not apply are 0), which is why `d.year`, `td.days` and
`t.hour` are plain field reads. Values are immutable; every function returns a new one.

Section markers (`# -- name: needs a, b`) tell dtlib.py which functions to append; everything is a module
level function on purpose (the compiler infers methods less reliably than functions).
"""

# -- core:
US_DAY = 86400000000
DIM = [0, 31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31]
DBM = [0, 0, 31, 59, 90, 120, 151, 181, 212, 243, 273, 304, 334]
MAX_ORDINAL = 3652059
TD_LIMIT = 4611686018427387904 // 2


class AilDT:
    """The last three fields exist only when the program names a time zone (dtlib.Dt.attach drops them
    otherwise): aware is 0 for a naive value, 1 for an aware one and 2 for one whose zone has a name."""

    def __init__(self, kind: int, k: int, year: int, month: int, day: int, hour: int, minute: int, second: int,
                 microsecond: int, days: int, seconds: int, microseconds: int, aware: int = 0, off: int = 0,
                 tzn: str = "") -> None:
        self.kind = kind
        self.k = k
        self.year = year
        self.month = month
        self.day = day
        self.hour = hour
        self.minute = minute
        self.second = second
        self.microsecond = microsecond
        self.days = days
        self.seconds = seconds
        self.microseconds = microseconds
        self.aware = aware
        self.off = off
        self.tzn = tzn


def isleap(y: int) -> bool:
    return y % 4 == 0 and (y % 100 != 0 or y % 400 == 0)


def dim(y: int, m: int) -> int:
    if m == 2 and isleap(y):
        return 29
    return DIM[m]


def ymd2ord(y: int, m: int, d: int) -> int:
    y1 = y - 1
    n = y1 * 365 + y1 // 4 - y1 // 100 + y1 // 400 + DBM[m] + d
    if m > 2 and isleap(y):
        n += 1
    return n


def ord_year(n: int) -> int:
    m = n - 1
    n400 = m // 146097
    m = m % 146097
    n100 = m // 36524
    m = m % 36524
    n4 = m // 1461
    m = m % 1461
    n1 = m // 365
    year = n400 * 400 + 1 + n100 * 100 + n4 * 4 + n1
    if n1 == 4 or n100 == 4:
        return year - 1
    return year


def ord_month(n: int) -> int:
    year = ord_year(n)
    yday = n - ymd2ord(year, 1, 1)
    month = (yday + 50) >> 5
    preceding = DBM[month]
    if month > 2 and isleap(year):
        preceding += 1
    if preceding > yday:
        month -= 1
    return month


def ord_day(n: int) -> int:
    year = ord_year(n)
    month = ord_month(n)
    return n - ymd2ord(year, month, 1) + 1


def from_k(kind: int, k: int) -> AilDT:
    """The value of `kind` whose key is `k` (the key is in range)."""
    if kind == 2:
        days = k // US_DAY
        rest = k - days * US_DAY
        return AilDT(2, k, 0, 0, 0, 0, 0, 0, 0, days, rest // 1000000, rest % 1000000)
    if kind == 3:
        return AilDT(3, k, 0, 0, 0, k // 3600000000, (k // 60000000) % 60, (k // 1000000) % 60, k % 1000000, 0, 0, 0)
    n = k // US_DAY
    y = ord_year(n)
    m = ord_month(n)
    d = n - ymd2ord(y, m, 1) + 1
    if kind == 0:
        return AilDT(0, k, y, m, d, 0, 0, 0, 0, 0, 0, 0)
    t = k - n * US_DAY
    return AilDT(1, k, y, m, d, t // 3600000000, (t // 60000000) % 60, (t // 1000000) % 60, t % 1000000, 0, 0, 0)


def check_ymd(y: int, m: int, d: int) -> None:
    if y < 1 or y > 9999:
        raise ValueError("year " + str(y) + " is out of range")
    if m < 1 or m > 12:
        raise ValueError("month must be in 1..12")
    if d < 1 or d > dim(y, m):
        raise ValueError("day is out of range for month")


def check_hmsu(hh: int, mm: int, ss: int, us: int) -> None:
    if hh < 0 or hh > 23:
        raise ValueError("hour must be in 0..23")
    if mm < 0 or mm > 59:
        raise ValueError("minute must be in 0..59")
    if ss < 0 or ss > 59:
        raise ValueError("second must be in 0..59")
    if us < 0 or us > 999999:
        raise ValueError("microsecond must be in 0..999999")


def mk_date(y: int, m: int, d: int) -> AilDT:
    check_ymd(y, m, d)
    return from_k(0, ymd2ord(y, m, d) * US_DAY)


def mk_datetime(y: int, m: int, d: int, hh: int, mm: int, ss: int, us: int) -> AilDT:
    check_ymd(y, m, d)
    check_hmsu(hh, mm, ss, us)
    return from_k(1, ymd2ord(y, m, d) * US_DAY + ((hh * 60 + mm) * 60 + ss) * 1000000 + us)


def mk_time(hh: int, mm: int, ss: int, us: int) -> AilDT:
    check_hmsu(hh, mm, ss, us)
    return from_k(3, ((hh * 60 + mm) * 60 + ss) * 1000000 + us)


def mk_timedelta(days: int, seconds: int, microseconds: int, milliseconds: int, minutes: int, hours: int,
                 weeks: int) -> AilDT:
    d = weeks * 7 + days
    if d > 106751991 or d < -106751991:
        raise OverflowError("days=" + str(d) + "; must have magnitude <= 106751991 (a larger timedelta is not built)")
    s = ((hours * 60 + minutes) * 60) + seconds
    if s > 9223372036854775 or s < -9223372036854775:
        raise OverflowError("timedelta out of range")
    k = d * US_DAY + s * 1000000 + milliseconds * 1000 + microseconds
    return from_k(2, k)


def mk_ordinal(n: int) -> AilDT:
    if n < 1:
        raise ValueError("ordinal must be >= 1")
    if n > MAX_ORDINAL:
        raise ValueError("year " + str(ord_year(n)) + " is out of range")
    return from_k(0, n * US_DAY)


def date_min() -> AilDT:
    return from_k(0, US_DAY)


def date_max() -> AilDT:
    return from_k(0, MAX_ORDINAL * US_DAY)


def datetime_min() -> AilDT:
    return from_k(1, US_DAY)


def datetime_max() -> AilDT:
    return from_k(1, MAX_ORDINAL * US_DAY + US_DAY - 1)


def in_range(k: int) -> bool:
    return k >= US_DAY and k < (MAX_ORDINAL + 1) * US_DAY


# -- arith: needs core
def kind_name(kind: int) -> str:
    if kind == 0:
        return "datetime.date"
    if kind == 1:
        return "datetime.datetime"
    if kind == 2:
        return "datetime.timedelta"
    return "datetime.time"


def bad_operands(op: str, a: AilDT, b: AilDT) -> None:
    raise RuntimeError("TypeError: unsupported operand type(s) for " + op + ": '" + kind_name(a.kind) + "' and '" + kind_name(b.kind) + "'")


def add(a: AilDT, b: AilDT) -> AilDT:
    if a.kind == 2 and b.kind == 2:
        return from_k(2, a.k + b.k)
    x = a
    y = b
    if a.kind == 2 and (b.kind == 0 or b.kind == 1):
        x = b
        y = a
    if y.kind != 2 or x.kind > 1:
        bad_operands("+", a, b)
    if x.kind == 0:
        k = x.k + y.days * US_DAY
    else:
        k = x.k + y.k
    if not in_range(k):
        raise OverflowError("date value out of range")
    return from_k(x.kind, k)


def sub(a: AilDT, b: AilDT) -> AilDT:
    if a.kind == 2 and b.kind == 2:
        return from_k(2, a.k - b.k)
    if a.kind <= 1 and b.kind == 2:
        if a.kind == 0:
            k = a.k - b.days * US_DAY
        else:
            k = a.k - b.k
        if not in_range(k):
            raise OverflowError("date value out of range")
        return from_k(a.kind, k)
    if a.kind == b.kind and a.kind <= 1:
        return from_k(2, a.k - b.k)
    bad_operands("-", a, b)
    return a


def neg(a: AilDT) -> AilDT:
    if a.kind != 2:
        raise RuntimeError("TypeError: bad operand type for unary -: '" + kind_name(a.kind) + "'")
    return from_k(2, -a.k)


def absval(a: AilDT) -> AilDT:
    if a.kind != 2:
        raise RuntimeError("TypeError: bad operand type for abs(): '" + kind_name(a.kind) + "'")
    if a.k < 0:
        return from_k(2, -a.k)
    return a


def mul(a: AilDT, n: int) -> AilDT:
    if a.kind != 2:
        raise RuntimeError("TypeError: unsupported operand type(s) for *: '" + kind_name(a.kind) + "' and 'int'")
    if n != 0:
        m = n if n > 0 else -n
        x = a.k if a.k >= 0 else -a.k
        if x > TD_LIMIT // m:
            raise OverflowError("timedelta out of range (a timedelta beyond 53 million days is not built)")
    return from_k(2, a.k * n)


def floordiv_int(a: AilDT, n: int) -> AilDT:
    if a.kind != 2:
        raise RuntimeError("TypeError: unsupported operand type(s) for //: '" + kind_name(a.kind) + "' and 'int'")
    if n == 0:
        raise ZeroDivisionError("integer division or modulo by zero")
    return from_k(2, a.k // n)


def floordiv_td(a: AilDT, b: AilDT) -> int:
    if a.kind != 2 or b.kind != 2:
        bad_operands("//", a, b)
    if b.k == 0:
        raise ZeroDivisionError("integer division or modulo by zero")
    return a.k // b.k


def truediv_int(a: AilDT, n: int) -> AilDT:
    if a.kind != 2:
        raise RuntimeError("TypeError: unsupported operand type(s) for /: '" + kind_name(a.kind) + "' and 'int'")
    if n == 0:
        raise ZeroDivisionError("division by zero")
    return from_k(2, round_div(a.k, n))


def round_div(x: int, n: int) -> int:
    """x / n rounded half to even (n != 0)."""
    q = x // n
    r = x - q * n          # same sign as n, |r| < |n|
    twice = 2 * r
    if n < 0:
        twice = -twice
    m = n
    if m < 0:
        m = -m
    if twice > m or (twice == m and q % 2 != 0):
        q += 1
    return q


def truediv_td(a: AilDT, b: AilDT) -> float:
    if a.kind != 2 or b.kind != 2:
        bad_operands("/", a, b)
    if b.k == 0:
        raise ZeroDivisionError("division by zero")
    return a.k / b.k


def mod(a: AilDT, b: AilDT) -> AilDT:
    if a.kind != 2 or b.kind != 2:
        bad_operands("%", a, b)
    if b.k == 0:
        raise ZeroDivisionError("integer division or modulo by zero")
    return from_k(2, a.k % b.k)


def pick_max(a: AilDT, b: AilDT) -> AilDT:
    if b.k > a.k:
        return b
    return a


def pick_min(a: AilDT, b: AilDT) -> AilDT:
    if b.k < a.k:
        return b
    return a


def max_list(xs: list[AilDT]) -> AilDT:
    if len(xs) == 0:
        raise ValueError("max() iterable argument is empty")
    best = xs[0]
    for i in range(1, len(xs)):
        if xs[i].k > best.k:
            best = xs[i]
    return best


def min_list(xs: list[AilDT]) -> AilDT:
    if len(xs) == 0:
        raise ValueError("min() iterable argument is empty")
    best = xs[0]
    for i in range(1, len(xs)):
        if xs[i].k < best.k:
            best = xs[i]
    return best


def nonzero(a: AilDT) -> bool:
    if a.kind == 2:
        return a.k != 0
    return True


def total_seconds(a: AilDT) -> float:
    """Exact (one correctly rounded division) while |k| < 2**53 microseconds, about 285 years; beyond that the
    whole seconds and the fraction are added, which can differ from CPython in the last bit."""
    if a.k < 9007199254740992 and a.k > -9007199254740992:
        return a.k / 1000000
    q = a.k // 1000000
    r = a.k - q * 1000000
    return q + r / 1000000


# -- fields: needs core
def weekday(a: AilDT) -> int:
    n = a.k // US_DAY
    return (n + 6) % 7


def isoweekday(a: AilDT) -> int:
    return weekday(a) + 1


def toordinal(a: AilDT) -> int:
    return a.k // US_DAY


def date_of(a: AilDT) -> AilDT:
    if a.kind != 1:
        raise RuntimeError("AttributeError: '" + kind_name(a.kind) + "' object has no attribute 'date'")
    return from_k(0, (a.k // US_DAY) * US_DAY)


def time_of(a: AilDT) -> AilDT:
    if a.kind != 1:
        raise RuntimeError("AttributeError: '" + kind_name(a.kind) + "' object has no attribute 'time'")
    return from_k(3, a.k % US_DAY)


def combine(d: AilDT, t: AilDT) -> AilDT:
    if d.kind > 1 or t.kind != 3:
        raise RuntimeError("TypeError: combine() argument 1 must be datetime.date, not " + kind_name(d.kind))
    return from_k(1, (d.k // US_DAY) * US_DAY + t.k)


def replace(a: AilDT, year: int, month: int, day: int, hour: int, minute: int, second: int, microsecond: int) -> AilDT:
    """Slots are -1 when not given."""
    if a.kind == 2:
        raise RuntimeError("TypeError: 'datetime.timedelta' object has no attribute 'replace'")
    if a.kind == 0:
        if hour != -1 or minute != -1 or second != -1 or microsecond != -1:
            raise RuntimeError("TypeError: 'hour' is an invalid keyword argument for replace()")
        y = year if year != -1 else a.year
        m = month if month != -1 else a.month
        d = day if day != -1 else a.day
        return mk_date(y, m, d)
    h = hour if hour != -1 else a.hour
    mi = minute if minute != -1 else a.minute
    s = second if second != -1 else a.second
    u = microsecond if microsecond != -1 else a.microsecond
    if a.kind == 3:
        if year != -1 or month != -1 or day != -1:
            raise RuntimeError("TypeError: 'year' is an invalid keyword argument for replace()")
        return mk_time(h, mi, s, u)
    y = year if year != -1 else a.year
    m = month if month != -1 else a.month
    d = day if day != -1 else a.day
    return mk_datetime(y, m, d, h, mi, s, u)


# -- text: needs core
def weekdays() -> list[str]:
    return ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]


def months() -> list[str]:
    return ["", "January", "February", "March", "April", "May", "June", "July", "August", "September", "October",
            "November", "December"]


def p2(n: int) -> str:
    s = str(n)
    if len(s) < 2:
        s = "0" + s
    return s


def p4(n: int) -> str:
    s = str(n)
    while len(s) < 4:
        s = "0" + s
    return s


def p6(n: int) -> str:
    s = str(n)
    while len(s) < 6:
        s = "0" + s
    return s


def time_text(hh: int, mm: int, ss: int, us: int, timespec: str) -> str:
    if timespec == "auto":
        if us != 0:
            return p2(hh) + ":" + p2(mm) + ":" + p2(ss) + "." + p6(us)
        return p2(hh) + ":" + p2(mm) + ":" + p2(ss)
    if timespec == "hours":
        return p2(hh)
    if timespec == "minutes":
        return p2(hh) + ":" + p2(mm)
    if timespec == "seconds":
        return p2(hh) + ":" + p2(mm) + ":" + p2(ss)
    if timespec == "milliseconds":
        ms = str(us // 1000)
        while len(ms) < 3:
            ms = "0" + ms
        return p2(hh) + ":" + p2(mm) + ":" + p2(ss) + "." + ms
    if timespec == "microseconds":
        return p2(hh) + ":" + p2(mm) + ":" + p2(ss) + "." + p6(us)
    raise ValueError("Unknown timespec value")


def iso(a: AilDT, sep: str, timespec: str) -> str:
    if a.kind == 0:
        return p4(a.year) + "-" + p2(a.month) + "-" + p2(a.day)
    if a.kind == 3:
        return time_text(a.hour, a.minute, a.second, a.microsecond, timespec)
    if a.kind == 1:
        return p4(a.year) + "-" + p2(a.month) + "-" + p2(a.day) + sep + time_text(a.hour, a.minute, a.second, a.microsecond, timespec)
    raise RuntimeError("AttributeError: 'datetime.timedelta' object has no attribute 'isoformat'")


def td_str(a: AilDT) -> str:
    out = ""
    if a.days != 0:
        out = str(a.days) + " day"
        if a.days != 1 and a.days != -1:
            out += "s"
        out += ", "
    mm = a.seconds // 60
    ss = a.seconds % 60
    hh = mm // 60
    mm = mm % 60
    out += str(hh) + ":" + p2(mm) + ":" + p2(ss)
    if a.microseconds != 0:
        out += "." + p6(a.microseconds)
    return out


def text(a: AilDT) -> str:
    if a.kind == 2:
        return td_str(a)
    return iso(a, " ", "auto")


def td_repr(a: AilDT) -> str:
    parts = ""
    if a.days != 0:
        parts = "days=" + str(a.days)
    if a.seconds != 0:
        if parts != "":
            parts += ", "
        parts += "seconds=" + str(a.seconds)
    if a.microseconds != 0:
        if parts != "":
            parts += ", "
        parts += "microseconds=" + str(a.microseconds)
    if parts == "":
        parts = "0"
    return "datetime.timedelta(" + parts + ")"


def rep(a: AilDT) -> str:
    if a.kind == 2:
        return td_repr(a)
    if a.kind == 0:
        return "datetime.date(" + str(a.year) + ", " + str(a.month) + ", " + str(a.day) + ")"
    if a.kind == 3:
        out = "datetime.time(" + str(a.hour) + ", " + str(a.minute)
        if a.second != 0 or a.microsecond != 0:
            out += ", " + str(a.second)
        if a.microsecond != 0:
            out += ", " + str(a.microsecond)
        return out + ")"
    out = "datetime.datetime(" + str(a.year) + ", " + str(a.month) + ", " + str(a.day) + ", " + str(a.hour) + ", " + str(a.minute)
    if a.second != 0 or a.microsecond != 0:
        out += ", " + str(a.second)
    if a.microsecond != 0:
        out += ", " + str(a.microsecond)
    return out + ")"


# -- strftime: needs text
def doy(a: AilDT) -> int:
    return a.k // US_DAY - ymd2ord(a.year, 1, 1) + 1


def week_number(a: AilDT, first: int) -> int:
    """%U (first = 6: weeks start on Sunday) and %W (first = 0: on Monday): days before the first such day are week 0."""
    yday = doy(a) - 1
    wd = weekday(a)
    if first == 6:
        wd = (wd + 1) % 7
    return (yday + 7 - wd) // 7


def iso_year_week(a: AilDT, which: int) -> int:
    """%G (which = 0) and %V (which = 1) of the ISO 8601 week date."""
    n = a.k // US_DAY
    wd = (n + 6) % 7
    thursday = n - wd + 3
    y = ord_year(thursday)
    first = ymd2ord(y, 1, 1)
    week = (thursday - first) // 7 + 1
    if which == 0:
        return y
    return week


def ampm(h: int, upper: bool) -> str:
    if h < 12:
        if upper:
            return "AM"
        return "am"
    if upper:
        return "PM"
    return "pm"


def pad_space(s: str) -> str:
    if len(s) < 2:
        return " " + s
    return s


def hour12(h: int) -> int:
    x = h % 12
    if x == 0:
        return 12
    return x


def fmt(a: AilDT, f: str) -> str:
    if a.kind == 2:
        raise RuntimeError("AttributeError: 'datetime.timedelta' object has no attribute 'strftime'")
    if a.kind == 3:
        return fmt(from_k(1, ymd2ord(1900, 1, 1) * US_DAY + a.k), f)
    out = ""
    i = 0
    n = len(f)
    while i < n:
        c = f[i]
        i += 1
        if c != "%":
            out += c
            continue
        if i >= n:
            out += "%"
            break
        d = f[i]
        i += 1
        if d == "Y":
            out += str(a.year)
        elif d == "m":
            out += p2(a.month)
        elif d == "d":
            out += p2(a.day)
        elif d == "H":
            out += p2(a.hour)
        elif d == "M":
            out += p2(a.minute)
        elif d == "S":
            out += p2(a.second)
        elif d == "f":
            out += p6(a.microsecond)
        elif d == "y":
            out += p2(a.year % 100)
        elif d == "I":
            out += p2(hour12(a.hour))
        elif d == "p":
            out += ampm(a.hour, True)
        elif d == "%":
            out += "%"
        elif d == "a":
            out += weekdays()[weekday(a)][0:3]
        elif d == "A":
            out += weekdays()[weekday(a)]
        elif d == "w":
            out += str((weekday(a) + 1) % 7)
        elif d == "u":
            out += str(weekday(a) + 1)
        elif d == "b" or d == "h":
            out += months()[a.month][0:3]
        elif d == "B":
            out += months()[a.month]
        elif d == "j":
            s = str(doy(a))
            while len(s) < 3:
                s = "0" + s
            out += s
        elif d == "U":
            out += p2(week_number(a, 6))
        elif d == "W":
            out += p2(week_number(a, 0))
        elif d == "G":
            out += str(iso_year_week(a, 0))
        elif d == "g":
            out += p2(iso_year_week(a, 0) % 100)
        elif d == "V":
            out += p2(iso_year_week(a, 1))
        elif d == "e":
            s = str(a.day)
            out += pad_space(s)
        elif d == "k":
            s = str(a.hour)
            out += pad_space(s)
        elif d == "l":
            s = str(hour12(a.hour))
            out += pad_space(s)
        elif d == "P":
            out += ampm(a.hour, False)
        elif d == "C":
            out += str(a.year // 100)
        elif d == "D":
            out += p2(a.month) + "/" + p2(a.day) + "/" + p2(a.year % 100)
        elif d == "F":
            out += str(a.year) + "-" + p2(a.month) + "-" + p2(a.day)
        elif d == "T" or d == "X":
            out += p2(a.hour) + ":" + p2(a.minute) + ":" + p2(a.second)
        elif d == "R":
            out += p2(a.hour) + ":" + p2(a.minute)
        elif d == "r":
            out += p2(hour12(a.hour)) + ":" + p2(a.minute) + ":" + p2(a.second) + " " + ampm(a.hour, True)
        elif d == "x":
            out += p2(a.month) + "/" + p2(a.day) + "/" + p2(a.year % 100)
        elif d == "c":
            s = str(a.day)
            if len(s) < 2:
                s = " " + s
            out += weekdays()[weekday(a)][0:3] + " " + months()[a.month][0:3] + " " + s + " " + p2(a.hour) + ":" + p2(a.minute) + ":" + p2(a.second) + " " + str(a.year)
        elif d == "n":
            out += "\n"
        elif d == "t":
            out += "\t"
        elif d == "z" or d == "Z":
            out += ""
        else:
            out += "%" + d
    return out


# -- parse: needs core
def isdig(c: str) -> bool:
    return c >= "0" and c <= "9"


def digits_at(data: str, pos: int, n: int) -> int:
    """The value of the n digits at pos, or -1 when they are not n ASCII digits."""
    if pos + n > len(data):
        return -1
    v = 0
    for i in range(n):
        c = data[pos + i]
        if not isdig(c):
            return -1
        v = v * 10 + int(c)
    return v


def iso_week1_monday(year: int) -> int:
    first = ymd2ord(year, 1, 1)
    first_weekday = (first + 6) % 7
    week1 = first - first_weekday
    if first_weekday > 3:
        week1 += 7
    return week1


def iso_to_ordinal(year: int, week: int, day: int) -> int:
    """The ordinal of an ISO year-week-day, or -4 (year), -2 (week), -3 (day) when there is no such day."""
    if year < 1 or year > 9999:
        return -4
    if week <= 0 or week >= 53:
        ok = False
        if week == 53:
            fw = (ymd2ord(year, 1, 1) + 6) % 7
            if fw == 3 or (fw == 2 and isleap(year)):
                ok = True
        if not ok:
            return -2
    if day <= 0 or day >= 8:
        return -3
    return iso_week1_monday(year) + (week - 1) * 7 + day - 1


def from_isocalendar(year: int, week: int, day: int) -> AilDT:
    if year < 1 or year > 9999:
        raise ValueError("Year is out of range: " + str(year))
    o = iso_to_ordinal(year, week, day)
    if o == -2:
        raise ValueError("Invalid week: " + str(week))
    if o == -3:
        raise ValueError("Invalid day: " + str(day) + " (range is [1, 7])")
    return from_k(0, o * US_DAY)


def parse_iso_date(s: str, start: int, length: int) -> int:
    """_Py_parse_isoformat_date over s[start:start+length]: year * 10000 + month * 100 + day (not yet range
    checked), or -1 when it is not a date."""
    p = start
    year = digits_at(s, p, 4)
    if year < 0:
        return -1
    p += 4
    uses_sep = p < len(s) and s[p] == "-"
    if uses_sep:
        p += 1
    if p < len(s) and s[p] == "W":
        p += 1
        week = digits_at(s, p, 2)
        if week < 0:
            return -1
        p += 2
        day = 1
        if p - start < length:
            if uses_sep:
                if p >= len(s) or s[p] != "-":
                    return -1
                p += 1
            day = digits_at(s, p, 1)
            if day < 0:
                return -1
        o = iso_to_ordinal(year, week, day)
        if year == 0:
            return 10001
        if o < 0:
            return -1
        d0 = from_k(0, o * US_DAY)
        return d0.year * 10000 + d0.month * 100 + d0.day
    month = digits_at(s, p, 2)
    if month < 0:
        return -1
    p += 2
    if uses_sep:
        if p >= len(s) or s[p] != "-":
            return -1
        p += 1
    day = digits_at(s, p, 2)
    if day < 0:
        return -1
    return year * 10000 + month * 100 + day


def bad_iso(s: str) -> None:
    raise ValueError("Invalid isoformat string: '" + s + "'")


def packed_ordinal(packed: int) -> int:
    y = packed // 10000
    m = (packed // 100) % 100
    d = packed % 100
    check_ymd(y, m, d)
    return ymd2ord(y, m, d)


def from_iso_date(s: str) -> AilDT:
    n = len(s)
    if n != 7 and n != 8 and n != 10:
        bad_iso(s)
    packed = parse_iso_date(s, 0, n)
    if packed < 0:
        bad_iso(s)
    return from_k(0, packed_ordinal(packed) * US_DAY)


def iso_separator(s: str) -> int:
    n = len(s)
    if n == 7:
        return 7
    if n < 5:
        return -1
    if s[4] == "-":
        if n < 6:
            return -1
        if s[5] == "W":
            if n < 8:
                return -1
            if n > 8 and s[8] == "-":
                if n > 10 and isdig(s[10]):
                    return 8
                return 10
            return 8
        return 10
    if s[4] == "W":
        idx = 7
        while idx < n and isdig(s[idx]):
            idx += 1
        if idx < 9:
            return idx
        if idx % 2 == 0:
            return 7
        return 8
    return 8


def nul_at(s: str, i: int) -> str:
    if i < len(s):
        return s[i]
    return "\0"


def parse_hh_mm_ss_ff(s: str, start: int, end: int, has_tz: bool) -> int:
    """parse_hh_mm_ss_ff over s[start:end] (no UTC offset): the microseconds of the day, or -1 when it is
    not a time."""
    vals = [0, 0, 0]
    p = start
    has_sep = True
    i = 0
    while i < 3:
        v = digits_at(s, p, 2)
        if v < 0:
            return -1
        vals[i] = v
        p += 2
        c = nul_at(s, p)
        p += 1
        if i == 0:
            has_sep = c == ":"
        if p >= end:
            if c != "\0" and not has_tz:
                return -1
            return ((vals[0] * 100 + vals[1]) * 100 + vals[2]) * 1000000
        if has_sep and c == ":":
            i += 1
            continue
        if c == "." or c == ",":
            break
        if not has_sep:
            p -= 1
        else:
            return -1
        i += 1
    to_parse = end - p
    if to_parse >= 6:
        to_parse = 6
    if to_parse <= 0:
        return -1
    frac = digits_at(s, p, to_parse)
    if frac < 0:
        return -1
    p += to_parse
    if to_parse < 6:
        m = 1
        for q in range(6 - to_parse):
            m = m * 10
        frac = frac * m
    while p < len(s) and isdig(s[p]):
        p += 1
    if p < len(s) and not has_tz:
        return -1
    return ((vals[0] * 100 + vals[1]) * 100 + vals[2]) * 1000000 + frac


def from_iso_datetime(s: str) -> AilDT:
    n = len(s)
    if n < 7:
        bad_iso(s)
    sep = iso_separator(s)
    if sep < 0:
        bad_iso(s)
    packed = parse_iso_date(s, 0, sep)
    if packed < 0:
        bad_iso(s)
    tod = 0
    if n > sep:
        start = sep + 1
        tz = start
        while tz < n and s[tz] != "Z" and s[tz] != "+" and s[tz] != "-":
            tz += 1
        has_tz = tz < n
        tod = parse_hh_mm_ss_ff(s, start, tz, has_tz)
        if tod < 0:
            bad_iso(s)
        if has_tz:
            # a UTC offset: valid ones make the value aware (not built), anything else is not an ISO string
            if s[tz] == "Z":
                if tz + 1 < n:
                    bad_iso(s)
            else:
                off = parse_hh_mm_ss_ff(s, tz + 1, n, False)
                if off < 0:
                    bad_iso(s)
            o2 = packed_ordinal(packed)
            check_hmsu(tod // 10000000000, (tod // 100000000) % 100, (tod // 1000000) % 100, tod % 1000000)
            raise RuntimeError("datetime.fromisoformat with a UTC offset gives a timezone-aware datetime, which is not built")
    o = packed_ordinal(packed)
    hh = tod // 10000000000
    mm = (tod // 100000000) % 100
    ss = (tod // 1000000) % 100
    us = tod % 1000000
    check_hmsu(hh, mm, ss, us)
    return from_k(1, o * US_DAY + ((hh * 60 + mm) * 60 + ss) * 1000000 + us)


def strp_names_b() -> list[str]:
    return ["september", "february", "november", "december", "january", "october", "august", "march", "april", "june", "july", "may"]


def strp_names_a() -> list[str]:
    return ["wednesday", "thursday", "saturday", "tuesday", "monday", "friday", "sunday"]


def strp_names_abb() -> list[str]:
    return ["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"]


def strp_names_ab() -> list[str]:
    return ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]


def strp_names_p() -> list[str]:
    return ["am", "pm"]




class AilStrp:
    def __init__(self) -> None:
        self.year = -1
        self.month = 1
        self.day = 1
        self.hour = 0
        self.hour12 = -1
        self.pm = -1
        self.minute = 0
        self.second = 0
        self.frac = 0
        self.iso_year = -1
        self.iso_week = -1
        self.week_of_year = -1
        self.week_start = -1
        self.weekday = -1
        self.julian = -1
        self.aware = 0


def strp_alts(d: str) -> list[str]:
    """The alternatives of a numeric directive in the order the regular expression tries them: each is a
    string of (low, high) character pairs, one pair per character ("3301" is 3[0-1], "09" is \\d)."""
    if d == "d":
        return ["3301", "1209", "0019", "19", "  19"]
    if d == "H":
        return ["2203", "0109", "09"]
    if d == "I":
        return ["1102", "0019", "19"]
    if d == "m":
        return ["1102", "0019", "19"]
    if d == "M":
        return ["0509", "09"]
    if d == "S":
        return ["6601", "0509", "09"]
    if d == "U" or d == "W":
        return ["5503", "0409", "09"]
    if d == "V":
        return ["5503", "0019", "1409", "09"]
    if d == "j":
        return ["336606", "330509", "120909", "001909", "000019", "1909", "0019", "19"]
    if d == "w":
        return ["06"]
    if d == "u":
        return ["17"]
    if d == "y":
        return ["0909"]
    if d == "Y" or d == "G":
        return ["09090909"]
    return []


def alt_end(alt: str, data: str, pos: int) -> int:
    k = len(alt) // 2
    if pos + k > len(data):
        return -1
    for t in range(k):
        c = data[pos + t]
        if c < alt[2 * t] or c > alt[2 * t + 1]:
            return -1
    return pos + k


def name_ends(names: list[str], data: str, pos: int) -> list[int]:
    out: list[int] = []
    for nm in names:
        k = len(nm)
        if pos + k <= len(data) and data[pos:pos + k].lower() == nm:
            out.append(pos + k)
    return out


def tz_offset_ends(data: str, pos: int) -> list[int]:
    """The ends the %z pattern [+-]\\d\\d:?[0-5]\\d(:?[0-5]\\d(\\.\\d{1,6})?)?|Z can match at pos, in the order the
    regular expression tries them."""
    out: list[int] = []
    n = len(data)
    if pos < n and data[pos] == "Z":
        pass
    if pos + 3 <= n and (data[pos] == "+" or data[pos] == "-") and isdig(data[pos + 1]) and isdig(data[pos + 2]):
        for colon in range(2):
            q = pos + 3
            if colon == 0:
                if q < n and data[q] == ":":
                    q += 1
                else:
                    continue
            if q + 2 <= n and data[q] >= "0" and data[q] <= "5" and isdig(data[q + 1]):
                q += 2
                # the optional seconds group, with or without its colon and its fraction
                for sec_colon in range(2):
                    r = q
                    if sec_colon == 0:
                        if r < n and data[r] == ":":
                            r += 1
                        else:
                            continue
                    if r + 2 <= n and data[r] >= "0" and data[r] <= "5" and isdig(data[r + 1]):
                        r += 2
                        if r < n and data[r] == "." and r + 1 < n and isdig(data[r + 1]):
                            run = 0
                            while run < 6 and r + 1 + run < n and isdig(data[r + 1 + run]):
                                run += 1
                            while run >= 1:
                                out.append(r + 1 + run)
                                run -= 1
                        out.append(r)
                out.append(q)
    if pos < n and data[pos] == "Z":
        out.append(pos + 1)
    return out


def strp_cands(d: str, data: str, pos: int) -> list[int]:
    out: list[int] = []
    if d == "z":
        return tz_offset_ends(data, pos)
    if d == "f":
        run = 0
        while run < 6 and pos + run < len(data) and isdig(data[pos + run]):
            run += 1
        while run >= 1:
            out.append(pos + run)
            run -= 1
        return out
    if d == "%":
        if pos < len(data) and data[pos] == "%":
            out.append(pos + 1)
        return out
    if d == "B":
        return name_ends(strp_names_b(), data, pos)
    if d == "b":
        return name_ends(strp_names_abb(), data, pos)
    if d == "A":
        return name_ends(strp_names_a(), data, pos)
    if d == "a":
        return name_ends(strp_names_ab(), data, pos)
    if d == "p":
        return name_ends(strp_names_p(), data, pos)
    for alt in strp_alts(d):
        e = alt_end(alt, data, pos)
        if e >= 0:
            out.append(e)
    return out


def index_of(names: list[str], piece: str) -> int:
    for i in range(len(names)):
        if names[i] == piece:
            return i
    return -1


def strp_set(st: AilStrp, d: str, data: str, pos: int, end: int) -> None:
    piece = data[pos:end]
    if d == "y":
        v = int(piece)
        st.year = v + 2000 if v <= 68 else v + 1900
    elif d == "Y":
        st.year = int(piece)
    elif d == "G":
        st.iso_year = int(piece)
    elif d == "m":
        st.month = int(piece)
    elif d == "B":
        st.month = index_of(["january", "february", "march", "april", "may", "june", "july", "august", "september", "october", "november", "december"], piece.lower()) + 1
    elif d == "b":
        st.month = index_of(strp_names_abb(), piece.lower()) + 1
    elif d == "d":
        st.day = int(piece.strip())
    elif d == "H":
        st.hour = int(piece)
        st.hour12 = -1
    elif d == "I":
        st.hour12 = int(piece)
    elif d == "M":
        st.minute = int(piece)
    elif d == "S":
        st.second = int(piece)
    elif d == "f":
        s = piece
        while len(s) < 6:
            s += "0"
        st.frac = int(s)
    elif d == "p":
        st.pm = index_of(strp_names_p(), piece.lower())
    elif d == "A":
        st.weekday = index_of(["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"], piece.lower())
    elif d == "a":
        st.weekday = index_of(strp_names_ab(), piece.lower())
    elif d == "w":
        w = int(piece)
        st.weekday = 6 if w == 0 else w - 1
    elif d == "u":
        st.weekday = int(piece) - 1
    elif d == "j":
        st.julian = int(piece)
    elif d == "U":
        st.week_of_year = int(piece)
        st.week_start = 6
    elif d == "W":
        st.week_of_year = int(piece)
        st.week_start = 0
    elif d == "V":
        st.iso_week = int(piece)
    elif d == "z":
        st.aware = 1


def strp_match(st: AilStrp, pat: str, fi: int, data: str, pos: int) -> int:
    n = len(pat)
    p = pos
    i = fi
    while i < n:
        c = pat[i]
        if c == "%":
            d = pat[i + 1]
            ends = strp_cands(d, data, p)
            for e in ends:
                strp_set(st, d, data, p, e)
                r = strp_match(st, pat, i + 2, data, e)
                if r >= 0:
                    return r
            return -1
        if c.isspace():
            j = i
            while j < n and pat[j].isspace():
                j += 1
            run = p
            while run < len(data) and data[run].isspace():
                run += 1
            if run == p:
                return -1
            e = run
            while e > p:
                r = strp_match(st, pat, j, data, e)
                if r >= 0:
                    return r
                e -= 1
            return -1
        if p >= len(data) or data[p].lower() != c.lower():
            return -1
        p += 1
        i += 1
    return p


def strp_expand(pat: str) -> str:
    out = ""
    i = 0
    n = len(pat)
    while i < n:
        c = pat[i]
        if c == "%" and i + 1 < n:
            d = pat[i + 1]
            if d == "c":
                out += "%a %b %d %H:%M:%S %Y"
            elif d == "x":
                out += "%m/%d/%y"
            elif d == "X":
                out += "%H:%M:%S"
            else:
                out += "%" + d
            i += 2
        else:
            out += c
            i += 1
    return out


def strp_check(pat: str) -> None:
    i = 0
    n = len(pat)
    while i < n:
        if pat[i] == "%":
            if i + 1 >= n:
                raise ValueError("stray % in format '" + pat + "'")
            d = pat[i + 1]
            if d.isspace() or d in ".^$*+?(){}[]|\\":
                raise ValueError("'%' is a bad directive in format '" + pat + "'")
            if d == "Z":
                raise RuntimeError("strptime %Z names the machine's time zones, which is not built")
            if d not in "dfHIGjmMSUwuVWyYAaBbpz%":
                raise ValueError("'" + d + "' is a bad directive in format '" + pat + "'")
            i += 2
        else:
            i += 1


def calc_julian_uw(year: int, week_of_year: int, day_of_week: int, week_starts_mon: bool) -> int:
    first_weekday = (ymd2ord(year, 1, 1) + 6) % 7
    dow = day_of_week
    if not week_starts_mon:
        first_weekday = (first_weekday + 1) % 7
        dow = (dow + 1) % 7
    week_0_length = (7 - first_weekday) % 7
    if week_of_year == 0:
        return 1 + dow - first_weekday
    days_to_week = week_0_length + 7 * (week_of_year - 1)
    return 1 + days_to_week + dow


def strptime(data: str, fmt0: str) -> AilDT:
    pattern = strp_expand(fmt0)
    strp_check(pattern)
    st = AilStrp()
    end = strp_match(st, pattern, 0, data, 0)
    if end < 0:
        raise ValueError("time data '" + data + "' does not match format '" + fmt0 + "'")
    if end != len(data):
        raise ValueError("unconverted data remains: " + data[end:])
    if st.aware == 1:
        raise RuntimeError("strptime %z gives a timezone-aware datetime, which is not built")
    year = st.year
    month = st.month
    day = st.day
    hour = st.hour
    if st.hour12 >= 0:
        hour = st.hour12
        if st.pm == 1:
            if hour != 12:
                hour += 12
        else:
            if hour == 12:
                hour = 0
    julian = st.julian
    weekday_v = st.weekday
    if st.iso_year != -1:
        if julian != -1:
            raise ValueError("Day of the year directive '%j' is not compatible with ISO year directive '%G'. Use '%Y' instead.")
        if st.iso_week == -1 or weekday_v == -1:
            raise ValueError("ISO year directive '%G' must be used with the ISO week directive '%V' and a weekday directive ('%A', '%a', '%w', or '%u').")
    elif st.iso_week != -1:
        if year == -1 or weekday_v == -1:
            raise ValueError("ISO week directive '%V' must be used with the ISO year directive '%G' and a weekday directive ('%A', '%a', '%w', or '%u').")
        raise ValueError("ISO week directive '%V' is incompatible with the year directive '%Y'. Use the ISO year '%G' instead.")
    leap_fix = False
    if year == -1 and month == 2 and day == 29:
        year = 1904
        leap_fix = True
    elif year == -1:
        year = 1900
    if julian == -1 and weekday_v != -1:
        if st.week_of_year != -1:
            julian = calc_julian_uw(year, st.week_of_year, weekday_v, st.week_start == 0)
        elif st.iso_year != -1 and st.iso_week != -1:
            dd = from_isocalendar(st.iso_year, st.iso_week, weekday_v + 1)
            year = dd.year
            month = dd.month
            day = dd.day
        if julian != -1 and julian <= 0:
            year -= 1
            yday = 366 if isleap(year) else 365
            julian += yday
    if julian != -1:
        o = julian - 1 + ymd2ord(year, 1, 1)
        if o < 1 or o > MAX_ORDINAL:
            raise ValueError("ordinal must be >= 1")
        d0 = from_k(0, o * US_DAY)
        year = d0.year
        month = d0.month
        day = d0.day
    if leap_fix:
        year = 1900
    return mk_datetime(year, month, day, hour, st.minute, st.second, st.frac)


# -- clock: needs core, strftime
# The wall clock and the OS time zone (stage G9). `_ail_time_ns`, `_ail_time`, `_ail_sleep_ns`,
# `_ail_local_offset`, `_ail_local_isdst`, `_ail_tz_name` and `_ail_mktime` are the compiler's own
# primitives (clockrt.py); the tests give this file stand-ins when CPython runs it.
EPOCH_ORD = 719163
EPOCH_K = 719163 * US_DAY
TIME_T_LIMIT = 9.2233720368547758e18
TM_UNSET = -4611686018427387904


class AilTM:
    """time.struct_time: the nine fields and tm_zone, tm_gmtoff."""

    def __init__(self, tm_year: int, tm_mon: int, tm_mday: int, tm_hour: int, tm_min: int, tm_sec: int,
                 tm_wday: int, tm_yday: int, tm_isdst: int, tm_zone: str, tm_gmtoff: int) -> None:
        self.tm_year = tm_year
        self.tm_mon = tm_mon
        self.tm_mday = tm_mday
        self.tm_hour = tm_hour
        self.tm_min = tm_min
        self.tm_sec = tm_sec
        self.tm_wday = tm_wday
        self.tm_yday = tm_yday
        self.tm_isdst = tm_isdst
        self.tm_zone = tm_zone
        self.tm_gmtoff = tm_gmtoff


def local_off(secs: int) -> int:
    off = _ail_local_offset(secs)
    if off > 100000 or off < -100000:
        raise OSError("[Errno 75] Value too large for defined data type")
    return off


def local_secs(u: int) -> int:
    """CPython's local(u): the local reading at the Unix time `u`, counted in seconds from the epoch as if it were
    UTC; a reading outside years 1..9999 is the ValueError CPython raises."""
    r = u + local_off(u)
    n = r // 86400 + EPOCH_ORD
    if n < 1 or n > MAX_ORDINAL:
        year_error_n(n)
    return r


def tz_text(v: int) -> str:
    s = ""
    for i in range(7):
        c = (v >> (8 * i)) & 255
        if c == 0:
            break
        s += chr(c)
    return s


def year_error_n(n: int) -> None:
    """The error CPython gives for a time on the proleptic ordinal day `n` outside years 1..9999: the C library
    fails (EOVERFLOW) once the year does not fit a C int."""
    y = ord_year(n)
    if y - 1900 > 2147483647 or y - 1900 < -2147483648:
        raise OSError("[Errno 75] Value too large for defined data type")
    raise ValueError("year " + str(y) + " is out of range")


def year_error(k: int) -> None:
    year_error_n(k // US_DAY)


def wall_from_unix(secs: int, us: int, off: int) -> AilDT:
    """The naive datetime that the Unix time `secs` + `us` microseconds shows on a clock `off` seconds east."""
    k = EPOCH_K + (secs + off) * 1000000 + us
    if not in_range(k):
        year_error(k)
    return from_k(1, k)


def float_secs(t: float) -> float:
    if t != t:
        raise ValueError("Invalid value NaN (not a number)")
    if t - t != 0.0:
        raise OverflowError("timestamp out of range for platform time_t")
    return t


def ts_us(t: float) -> int:
    """A float timestamp as whole seconds * 1000000 + microseconds, microseconds rounded half to even (the
    rounding datetime.fromtimestamp does)."""
    float_secs(t)
    if t >= 1e12 or t <= -1e12:
        if t >= TIME_T_LIMIT or t <= -TIME_T_LIMIT:
            raise OverflowError("timestamp out of range for platform time_t")
        year_error_n(int(t) // 86400 + EPOCH_ORD)
    ip = float(int(t))
    r = round((t - ip) * 1000000.0)
    if r >= 1000000:
        r -= 1000000
        ip += 1.0
    elif r < 0:
        r += 1000000
        ip -= 1.0
    return int(ip) * 1000000 + r


def floor_secs(t: float) -> int:
    """floor(t) as a time_t (what time.localtime(t), time.gmtime(t) and date.fromtimestamp(t) use)."""
    float_secs(t)
    f = t // 1.0
    if f >= TIME_T_LIMIT or f < -TIME_T_LIMIT:
        raise OverflowError("timestamp out of range for platform time_t")
    return int(f)


def now_secs() -> int:
    return _ail_time_ns() // 1000000000


def dt_from_us(total: int, utc: bool) -> AilDT:
    secs = total // 1000000
    us = total - secs * 1000000
    if utc:
        return wall_from_unix(secs, us, 0)
    off = local_off(secs)
    a = wall_from_unix(secs, us, off)
    # CPython probes a day back for a fold (and so fails for a time within a day of year 1 or 9999)
    probe = local_secs(secs - 86400)
    transition = secs + off - probe - 86400
    if transition < 0:
        if local_secs(secs + transition) == secs + off:
            # fold = 1 is kept in the `seconds` slot, which a datetime does not otherwise use
            return AilDT(1, a.k, a.year, a.month, a.day, a.hour, a.minute, a.second, a.microsecond, 0, 1, 0)
    return a


def now_local() -> AilDT:
    """datetime.now(): the clock floored to microseconds, shown on the local clock."""
    return dt_from_us(_ail_time_ns() // 1000, False)


def now_utc() -> AilDT:
    """datetime.utcnow()"""
    return dt_from_us(_ail_time_ns() // 1000, True)


def dt_from_ts(t: float, utc: bool) -> AilDT:
    """datetime.fromtimestamp(t) (utc False) and datetime.utcfromtimestamp(t)."""
    return dt_from_us(ts_us(t), utc)


def dt_today() -> AilDT:
    """datetime.today(): fromtimestamp(time.time())"""
    return dt_from_ts(_ail_time(), False)


def date_from_ts(t: float) -> AilDT:
    """date.fromtimestamp(t): the local date of floor(t)."""
    secs = floor_secs(t)
    n = (secs + local_off(secs)) // 86400 + EPOCH_ORD
    if n < 1 or n > MAX_ORDINAL:
        year_error_n(n)
    return from_k(0, n * US_DAY)


def date_today() -> AilDT:
    return date_from_ts(_ail_time())


def local_to_utc(t: int, fold: int) -> int:
    """The Unix time whose local reading is `t` (a reading counted in seconds from the epoch as if it were UTC),
    CPython's local_to_seconds."""
    a = local_secs(t) - t
    u1 = t - a
    t1 = local_secs(u1)
    b = 0
    if t1 == t:
        u2 = u1 - 86400
        if fold != 0:
            u2 = u1 + 86400
        b = local_secs(u2) - u2
        if a == b:
            return u1
    else:
        b = t1 - u1
    u2 = t - b
    t2 = local_secs(u2)
    if t2 == t:
        return u2
    if t1 == t:
        return u1
    if fold != 0:
        if u1 < u2:
            return u1
        return u2
    if u1 > u2:
        return u1
    return u2


def timestamp(a: AilDT) -> float:
    """datetime.timestamp() of a naive datetime: it is read as local time."""
    if a.kind != 1:
        raise RuntimeError("AttributeError: '" + kind_name(a.kind) + "' object has no attribute 'timestamp'")
    wall = (a.k - EPOCH_K) // 1000000
    return float(local_to_utc(wall, a.seconds)) + a.microsecond / 1e6


def sleep_for(x: float) -> int:
    """time.sleep(x)"""
    float_secs(x)
    ns = x * 1e9
    if ns >= TIME_T_LIMIT or ns <= -TIME_T_LIMIT:
        raise OverflowError("timestamp out of range for platform time_t")
    n = int(ns)
    if float(n) < ns:
        n += 1
    elif float(n) > ns:
        n -= 1
    if n < 0:
        raise ValueError("sleep length must be non-negative")
    return _ail_sleep_ns(n)


def tm_build(secs: int, off: int, isdst: int, zone: str) -> AilTM:
    t = secs + off
    n = t // 86400 + EPOCH_ORD
    sod = t - (n - EPOCH_ORD) * 86400
    y = ord_year(n)
    if y - 1900 > 2147483647 or y - 1900 < -2147483648:
        year_error_n(n)
    m = ord_month(n)
    d = n - ymd2ord(y, m, 1) + 1
    return AilTM(y, m, d, sod // 3600, (sod // 60) % 60, sod % 60, (n + 6) % 7, n - ymd2ord(y, 1, 1) + 1, isdst, zone, off)


def tm_gm(t: float) -> AilTM:
    """time.gmtime(t)"""
    return tm_build(floor_secs(t), 0, 0, "GMT")


def tm_gm_now() -> AilTM:
    return tm_build(now_secs(), 0, 0, "GMT")


def tm_at(secs: int) -> AilTM:
    off = local_off(secs)
    return tm_build(secs, off, _ail_local_isdst(secs), tz_text(_ail_tz_name(secs)))


def tm_local(t: float) -> AilTM:
    """time.localtime(t)"""
    return tm_at(floor_secs(t))


def tm_local_now() -> AilTM:
    return tm_at(now_secs())


def mktime_fields(y: int, mo: int, d: int, hh: int, mm: int, ss: int, isdst: int) -> float:
    """time.mktime((y, mo, d, hh, mm, ss, wday, yday, isdst))"""
    r = _ail_mktime(y, mo, d, hh, mm, ss, isdst)
    if r < -4611686018427387904:
        raise OverflowError("mktime argument out of range")
    return float(r)


def tm_mktime(t: AilTM) -> float:
    return mktime_fields(t.tm_year, t.tm_mon, t.tm_mday, t.tm_hour, t.tm_min, t.tm_sec, t.tm_isdst)


def gmt_off_text(off: int) -> str:
    sign = "+"
    if off < 0:
        sign = "-"
        off = -off
    return sign + p2(off // 3600) + p2((off // 60) % 60)


def tm_strftime(f: str, t: AilTM) -> str:
    """time.strftime(f, t): %z and %Z come from the struct, the rest is the datetime directives."""
    g = ""
    i = 0
    n = len(f)
    while i < n:
        c = f[i]
        if c == "%" and i + 1 < n:
            d = f[i + 1]
            if d == "z":
                g += gmt_off_text(t.tm_gmtoff)
            elif d == "Z":
                g += t.tm_zone
            else:
                g += c + d
            i += 2
        else:
            g += c
            i += 1
    if t.tm_year < 1 or t.tm_year > 9999:
        raise RuntimeError("time.strftime: years outside 1..9999 are not built")
    return fmt(mk_datetime(t.tm_year, t.tm_mon, t.tm_mday, t.tm_hour, t.tm_min, t.tm_sec, 0), g)


# -- aware: needs core, text, clock
# Fixed-offset time zones and aware datetimes (stage G9). A program that names a time zone gets these in place of
# the naive functions (dtlib.AWARE_ALT); the key `k` of an aware value stays the key of its wall clock fields, so
# weekday(), strftime() and the fields work as they do for a naive value, and `ukey` is the key of the instant.
class AilTZ:
    """datetime.timezone: `off` seconds east of UTC; `named` is 1 when a name was given (then `name` is the name)."""

    def __init__(self, off: int, name: str, named: int) -> None:
        self.off = off
        self.name = name
        self.named = named


def tz_utc() -> AilTZ:
    return AilTZ(0, "UTC", 0)


def tz_offset_text(off: int, colon: bool) -> str:
    """+HH:MM, or +HH:MM:SS when there are seconds (without the colons for %z)."""
    sign = "+"
    if off < 0:
        sign = "-"
        off = -off
    c = ""
    if colon:
        c = ":"
    out = sign + p2(off // 3600) + c + p2((off // 60) % 60)
    if off % 60 != 0:
        out += c + p2(off % 60)
    return out


def tz_make(td: AilDT, name: str, named: int) -> AilTZ:
    if td.kind != 2:
        raise RuntimeError("TypeError: timezone() argument 1 must be datetime.timedelta, not " + kind_name(td.kind))
    if td.k % 1000000 != 0:
        raise RuntimeError("a timezone offset with microseconds is not built")
    s = td.k // 1000000
    if s <= -86400 or s >= 86400:
        raise ValueError("offset must be a timedelta strictly between -timedelta(hours=24) and timedelta(hours=24), not " + td_repr(td) + ".")
    if named == 0 and s == 0:
        return tz_utc()
    return AilTZ(s, name, named)


def tz_name(z: AilTZ) -> str:
    if z.named != 0:
        return z.name
    if z.off == 0:
        return "UTC"
    return "UTC" + tz_offset_text(z.off, True)


def tz_repr(off: int, name: str, named: int) -> str:
    if named == 0 and off == 0:
        return "datetime.timezone.utc"
    out = "datetime.timezone(" + td_repr(from_k(2, off * 1000000))
    if named != 0:
        out += ", " + repr(name)
    return out + ")"


def tz_rep(z: AilTZ) -> str:
    return tz_repr(z.off, z.name, z.named)


def tz_utcoffset(z: AilTZ) -> AilDT:
    return from_k(2, z.off * 1000000)


def tz_eq(a: AilTZ, b: AilTZ) -> bool:
    return a.off == b.off


def aw_set(a: AilDT, off: int, name: str, named: int) -> AilDT:
    """`a` (a fresh value) marked aware with that offset and name."""
    a.aware = 1 + named
    a.off = off
    a.tzn = name
    return a


def aw_tz(a: AilDT) -> AilTZ:
    return AilTZ(a.off, a.tzn, a.aware - 1)


def aw_attach(a: AilDT, z: AilTZ) -> AilDT:
    """a.replace(tzinfo=z): the wall clock fields stay."""
    if a.kind != 1:
        raise RuntimeError("TypeError: tzinfo is only built for a datetime")
    return aw_set(from_k(1, a.k), z.off, z.name, z.named)


def aw_strip(a: AilDT) -> AilDT:
    """a.replace(tzinfo=None)"""
    if a.kind != 1:
        raise RuntimeError("TypeError: tzinfo is only built for a datetime")
    return from_k(1, a.k)


def aw_copy(a: AilDT, src: AilDT) -> AilDT:
    """`a` (fresh) with the zone of `src`."""
    if a.kind == 1 and src.aware != 0:
        a.aware = src.aware
        a.off = src.off
        a.tzn = src.tzn
    return a


def is_naive(a: AilDT) -> bool:
    return a.aware == 0


def ukey(a: AilDT) -> int:
    return a.k - a.off * 1000000


def is_mixed(a: AilDT, b: AilDT) -> bool:
    return (a.aware == 0 and b.aware != 0) or (a.aware != 0 and b.aware == 0)


def mixed_error(what: str) -> None:
    raise RuntimeError("TypeError: can't " + what + " offset-naive and offset-aware datetimes")


def cmp_lt(a: AilDT, b: AilDT) -> bool:
    if is_mixed(a, b):
        mixed_error("compare")
    return ukey(a) < ukey(b)


def cmp_le(a: AilDT, b: AilDT) -> bool:
    if is_mixed(a, b):
        mixed_error("compare")
    return ukey(a) <= ukey(b)


def cmp_gt(a: AilDT, b: AilDT) -> bool:
    if is_mixed(a, b):
        mixed_error("compare")
    return ukey(a) > ukey(b)


def cmp_ge(a: AilDT, b: AilDT) -> bool:
    if is_mixed(a, b):
        mixed_error("compare")
    return ukey(a) >= ukey(b)


def cmp_eq(a: AilDT, b: AilDT) -> bool:
    if is_mixed(a, b):
        return False
    return ukey(a) == ukey(b)


def cmp_ne(a: AilDT, b: AilDT) -> bool:
    return not cmp_eq(a, b)


def add_aw(a: AilDT, b: AilDT) -> AilDT:
    r = add(a, b)
    if a.kind == 1:
        return aw_copy(r, a)
    return aw_copy(r, b)


def sub_aw(a: AilDT, b: AilDT) -> AilDT:
    if a.kind == 1 and b.kind == 1:
        if is_mixed(a, b):
            mixed_error("subtract")
        return from_k(2, ukey(a) - ukey(b))
    r = sub(a, b)
    if a.kind == 1:
        return aw_copy(r, a)
    return r


def pick_max_aw(a: AilDT, b: AilDT) -> AilDT:
    if ukey(b) > ukey(a):
        return b
    return a


def pick_min_aw(a: AilDT, b: AilDT) -> AilDT:
    if ukey(b) < ukey(a):
        return b
    return a


def max_list_aw(xs: list[AilDT]) -> AilDT:
    if len(xs) == 0:
        raise ValueError("max() iterable argument is empty")
    best = xs[0]
    for i in range(1, len(xs)):
        if ukey(xs[i]) > ukey(best):
            best = xs[i]
    return best


def min_list_aw(xs: list[AilDT]) -> AilDT:
    if len(xs) == 0:
        raise ValueError("min() iterable argument is empty")
    best = xs[0]
    for i in range(1, len(xs)):
        if ukey(xs[i]) < ukey(best):
            best = xs[i]
    return best


def replace_aw(a: AilDT, year: int, month: int, day: int, hour: int, minute: int, second: int, microsecond: int) -> AilDT:
    return aw_copy(replace(a, year, month, day, hour, minute, second, microsecond), a)


def iso_aw(a: AilDT, sep: str, timespec: str) -> str:
    out = iso(a, sep, timespec)
    if a.kind == 1 and a.aware != 0:
        out += tz_offset_text(a.off, True)
    return out


def text_aw(a: AilDT) -> str:
    if a.kind == 2:
        return td_str(a)
    return iso_aw(a, " ", "auto")


def rep_aw(a: AilDT) -> str:
    r = rep(a)
    if a.kind == 1 and a.aware != 0:
        return r[0:len(r) - 1] + ", tzinfo=" + tz_repr(a.off, a.tzn, a.aware - 1) + ")"
    return r


def fmt_aw(a: AilDT, f: str) -> str:
    """strftime with %z and %Z (empty for a naive value)."""
    if a.kind != 1:
        return fmt(a, f)
    g = ""
    i = 0
    n = len(f)
    while i < n:
        c = f[i]
        if c == "%" and i + 1 < n:
            d = f[i + 1]
            if d == "z":
                if a.aware != 0:
                    g += tz_offset_text(a.off, False)
            elif d == "Z":
                if a.aware != 0:
                    g += tz_name(aw_tz(a))
            else:
                g += c + d
            i += 2
        else:
            g += c
            i += 1
    return fmt(a, g)


def utcoffset_aw(a: AilDT) -> AilDT:
    if a.kind != 1 or a.aware == 0:
        raise RuntimeError("utcoffset() of a naive value is None, which is not built: test d.tzinfo is None first")
    return from_k(2, a.off * 1000000)


def tzname_aw(a: AilDT) -> str:
    if a.kind != 1 or a.aware == 0:
        raise RuntimeError("tzname() of a naive value is None, which is not built: test d.tzinfo is None first")
    return tz_name(aw_tz(a))


def wall_aware(secs: int, us: int, z: AilTZ) -> AilDT:
    """The aware datetime for the Unix time `secs` + `us` microseconds on the zone `z`."""
    return aw_set(wall_from_unix(secs, us, z.off), z.off, z.name, z.named)


def now_tz(z: AilTZ) -> AilDT:
    """datetime.now(tz)"""
    total = _ail_time_ns() // 1000
    secs = total // 1000000
    return wall_aware(secs, total - secs * 1000000, z)


def fromts_tz(t: float, z: AilTZ) -> AilDT:
    """datetime.fromtimestamp(t, tz)"""
    total = ts_us(t)
    secs = total // 1000000
    return wall_aware(secs, total - secs * 1000000, z)


def local_zone_at(secs: int) -> AilTZ:
    """The OS time zone at the Unix time `secs` as a fixed-offset zone named by its abbreviation."""
    return AilTZ(local_off(secs), tz_text(_ail_tz_name(secs)), 1)


def astimezone_to(a: AilDT, z: AilTZ) -> AilDT:
    """a.astimezone(z)"""
    if a.kind != 1:
        raise RuntimeError("AttributeError: only a datetime has astimezone")
    u = ukey(a)
    if a.aware == 0:
        u = (local_to_utc((a.k - EPOCH_K) // 1000000, a.seconds)) * 1000000 + a.microsecond + EPOCH_K
    k = u + z.off * 1000000
    if not in_range(k):
        raise OverflowError("date value out of range")
    return aw_set(from_k(1, k), z.off, z.name, z.named)


def astimezone_local(a: AilDT) -> AilDT:
    """a.astimezone(): the OS time zone, as a fixed offset named by its abbreviation."""
    if a.kind != 1:
        raise RuntimeError("AttributeError: only a datetime has astimezone")
    u = ukey(a)
    if a.aware == 0:
        u = (local_to_utc((a.k - EPOCH_K) // 1000000, a.seconds)) * 1000000 + a.microsecond + EPOCH_K
    secs = (u - EPOCH_K) // 1000000
    return astimezone_to(aw_set(from_k(1, u), 0, "UTC", 0), local_zone_at(secs))


def timestamp_aw(a: AilDT) -> float:
    if a.kind != 1:
        raise RuntimeError("AttributeError: '" + kind_name(a.kind) + "' object has no attribute 'timestamp'")
    if a.aware == 0:
        return timestamp(a)
    return total_seconds(from_k(2, ukey(a) - EPOCH_K))


def from_iso_datetime_aw(s: str) -> AilDT:
    """datetime.fromisoformat with a UTC offset or Z: aware; without one: naive."""
    n = len(s)
    if n < 7:
        bad_iso(s)
    sep = iso_separator(s)
    if sep < 0:
        bad_iso(s)
    packed = parse_iso_date(s, 0, sep)
    if packed < 0:
        bad_iso(s)
    tod = 0
    tzpos = -1
    secs = 0
    if n > sep:
        start = sep + 1
        tz = start
        while tz < n and s[tz] != "Z" and s[tz] != "+" and s[tz] != "-":
            tz += 1
        has_tz = tz < n
        tod = parse_hh_mm_ss_ff(s, start, tz, has_tz)
        if tod < 0:
            bad_iso(s)
        if has_tz:
            tzpos = tz
            if s[tz] == "Z":
                if tz + 1 < n:
                    bad_iso(s)
            else:
                off = parse_hh_mm_ss_ff(s, tz + 1, n, False)
                if off < 0:
                    bad_iso(s)
                if off % 1000000 != 0:
                    raise RuntimeError("a UTC offset with microseconds is not built")
                secs = (off // 10000000000) * 3600 + ((off // 100000000) % 100) * 60 + (off // 1000000) % 100
                if s[tz] == "-":
                    secs = -secs
                if secs <= -86400 or secs >= 86400:
                    raise ValueError("offset must be a timedelta strictly between -timedelta(hours=24) and timedelta(hours=24), not " + td_repr(from_k(2, secs * 1000000)) + ".")
    o = packed_ordinal(packed)
    hh = tod // 10000000000
    mm = (tod // 100000000) % 100
    ss = (tod // 1000000) % 100
    us = tod % 1000000
    check_hmsu(hh, mm, ss, us)
    base = from_k(1, o * US_DAY + ((hh * 60 + mm) * 60 + ss) * 1000000 + us)
    if tzpos < 0:
        return base
    if secs == 0:
        return aw_set(base, 0, "UTC", 0)
    return aw_set(base, secs, "", 0)

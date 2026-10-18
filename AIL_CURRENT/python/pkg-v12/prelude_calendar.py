# -*- coding: utf-8 -*-
# prelude_calendar.py -- the functions of `calendar` that smalllib5.py builds, as Python source (CPython 3.12's
# calendar.py for the Monday-first default).

def _ail_cal_isleap(year: int) -> bool:
    return year % 4 == 0 and (year % 100 != 0 or year % 400 == 0)


def _ail_cal_leapdays(y1: int, y2: int) -> int:
    y1 = y1 - 1
    y2 = y2 - 1
    return (y2 // 4 - y1 // 4) - (y2 // 100 - y1 // 100) + (y2 // 400 - y1 // 400)


def _ail_cal_mdays(month: int) -> int:
    if month == 2:
        return 28
    if month == 4 or month == 6 or month == 9 or month == 11:
        return 30
    return 31


def _ail_cal_weekday_int(year: int, month: int, day: int) -> int:
    if year < 1 or year > 9999:
        year = 2000 + year % 400
    if month < 1 or month > 12:
        raise ValueError("month must be in 1..12")
    dim = _ail_cal_mdays(month)
    if month == 2 and _ail_cal_isleap(year):
        dim = 29
    if day < 1 or day > dim:
        raise ValueError("day is out of range for month")
    y = year - 1
    days = y * 365 + y // 4 - y // 100 + y // 400 + day
    m = 1
    while m < month:
        days = days + _ail_cal_mdays(m)
        if m == 2 and _ail_cal_isleap(year):
            days = days + 1
        m = m + 1
    return (days + 6) % 7


class _AilDay(_AilIntEnum):
    def __repr__(self) -> str:
        return "calendar." + self.name


_ail_cal_day_members = [_AilDay("Day", "MONDAY", 0, 0), _AilDay("Day", "TUESDAY", 1, 1), _AilDay("Day", "WEDNESDAY", 2, 2),
                        _AilDay("Day", "THURSDAY", 3, 3), _AilDay("Day", "FRIDAY", 4, 4), _AilDay("Day", "SATURDAY", 5, 5),
                        _AilDay("Day", "SUNDAY", 6, 6)]


def _ail_cal_day(n: int):
    return _ail_cal_day_members[n]


def _ail_cal_weekday(year: int, month: int, day: int):
    return _ail_cal_day_members[_ail_cal_weekday_int(year, month, day)]


def _ail_cal_monthrange(year: int, month: int):
    r = _ail_cal_monthrange_int(year, month)
    return (_ail_cal_day_members[r[0]], r[1])


def _ail_cal_monthrange_int(year: int, month: int) -> tuple[int, int]:
    if month < 1 or month > 12:
        raise ValueError("bad month number %d; must be 1-12" % month)
    day1 = _ail_cal_weekday_int(year, month, 1)
    ndays = _ail_cal_mdays(month)
    if month == 2 and _ail_cal_isleap(year):
        ndays = 29
    return (day1, ndays)


def _ail_cal_monthcalendar(year: int, month: int) -> list[list[int]]:
    r = _ail_cal_monthrange_int(year, month)
    day1 = r[0]
    ndays = r[1]
    days = []
    before = day1 % 7
    i = 0
    while i < before:
        days.append(0)
        i = i + 1
    d = 1
    while d <= ndays:
        days.append(d)
        d = d + 1
    after = (0 - day1 - ndays) % 7
    i = 0
    while i < after:
        days.append(0)
        i = i + 1
    weeks = []
    i = 0
    while i < len(days):
        weeks.append(days[i:i + 7])
        i = i + 7
    return weeks


def _ail_cal_month_names() -> list[str]:
    return ["", "January", "February", "March", "April", "May", "June", "July", "August", "September", "October",
            "November", "December"]


def _ail_cal_month_abbrs() -> list[str]:
    return ["", "Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]


def _ail_cal_day_names() -> list[str]:
    return ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]


def _ail_cal_day_abbrs() -> list[str]:
    return ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]


def _ail_cal_center(s: str, width: int) -> str:
    n = len(s)
    if n >= width:
        return s
    marg = width - n
    left = marg // 2 + (marg & width & 1)
    return " " * left + s + " " * (marg - left)


def _ail_cal_month(year: int, month: int, w: int = 0, l: int = 0) -> str:
    if w < 2:
        w = 2
    if l < 1:
        l = 1
    if month < 1 or month > 12:
        raise ValueError("bad month number %d; must be 1-12" % month)
    names = _ail_cal_month_names()
    head = _ail_cal_center(names[month] + " " + str(year), 7 * (w + 1) - 1)
    s = head.rstrip() + "\n" * l
    wd = []
    dn = _ail_cal_day_names()
    da = _ail_cal_day_abbrs()
    i = 0
    while i < 7:
        if w >= 9:
            wd.append(_ail_cal_center(dn[i][:w], w))
        else:
            wd.append(_ail_cal_center(da[i][:w], w))
        i = i + 1
    s = s + " ".join(wd).rstrip() + "\n" * l
    for week in _ail_cal_monthcalendar(year, month):
        cells = []
        for d in week:
            if d == 0:
                cells.append(_ail_cal_center("", w))
            else:
                cells.append(_ail_cal_center("%2d" % d, w))
        s = s + " ".join(cells).rstrip() + "\n" * l
    return s

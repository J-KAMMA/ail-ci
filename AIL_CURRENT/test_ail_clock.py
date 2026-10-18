"""G9: the wall clock (time.time, time.sleep, time.localtime ..., datetime.now ...), compared with CPython 3.12.

The clock is a program input (Decision Q7). `AIL_CLOCK=<seconds>[.<fraction>]` pins it: every read returns that
value (the fraction keeps nine digits), and `sleep` advances it by the time it was asked for without sleeping.
CPython has no such switch, so the CPython side of every comparison runs under `FAKE_CLOCK` below: a prelude
that parses the same variable the same way and replaces time.time / time_ns / sleep / localtime / gmtime /
strftime (their "now" forms) and datetime.datetime.now / utcnow, which read the clock in C. Local time is the
OS time zone, so every comparison fixes TZ (POSIX rule strings, which need no tz database).

* the functions the compiler appends (dtrt.py, `# -- clock`) are plain Python: run by CPython with stand-ins for
  the C primitives they call, they must agree with datetime / time on generated timestamps, in several zones,
  errors included;
* whole programs (typed path and the general path, AIL_IR=0 and 1) print the same bytes as CPython under the fake
  clock for several pinned values and zones;
* without AIL_CLOCK the clock is the real one and sleep really sleeps;
* a malformed AIL_CLOCK is a ValueError at the first read;
* the names that stay refused are checked by name.
"""
import math
import os
import random
import re
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent
CLI = str(ROOT / "ail_chatgpt.py")
CORE_DIR = ROOT / "python" / "pkg-v12"

# POSIX TZ rules (no tz database needed): standard only, east and west, half-hour, northern and southern DST
ZONES = ["UTC0", "EST5EDT,M3.2.0,M11.1.0", "JST-9", "IST-5:30", "CET-1CEST,M3.5.0,M10.5.0/3",
         "NZST-12NZDT,M9.5.0,M4.1.0/3", "<-03>3<-02>,M3.5.0/-2,M10.5.0/-1"]
CLOCKS = ["1700000000", "1700000000.25", "1709999999.9999999", "0", "86399.5", "1710054000.000001",
          "1730613599.999999999", "4102444800.000000001", "1711846800"]

FAKE_CLOCK = r'''
import math, os, re, sys, time as _t, datetime as _d, warnings, runpy
warnings.simplefilter("ignore")
_s = os.environ.get("AIL_CLOCK", "")
_m = re.fullmatch(r"([+-]?)(\d+)(?:\.(\d*))?", _s)
if not _m:
    def _bad(*a, **k):
        raise ValueError("AIL_CLOCK must be a number of seconds since the epoch, like 1700000000.25")
    _t.time = _t.time_ns = _bad
    _state = [0]
else:
    _ns = int(_m.group(2)) * 10 ** 9 + int((_m.group(3) or "").ljust(9, "0")[:9])
    _state = [-_ns if _m.group(1) == "-" else _ns]
_real_localtime, _real_gmtime, _real_strftime = _t.localtime, _t.gmtime, _t.strftime
_real_dt = _d.datetime
if _m:
    def _time_ns():
        return _state[0]

    def _time():
        t = _state[0]
        return float(t // 10 ** 9) if t % 10 ** 9 == 0 else float(t) / 1e9

    def _sleep(x):
        if isinstance(x, float):
            if x != x:
                raise ValueError("Invalid value NaN (not a number)")
            d = x * 1e9
            if not (-9.2233720368547758e18 <= d < 9.2233720368547758e18):
                raise OverflowError("timestamp too large to convert to C _PyTime_t")
            n = math.ceil(d)
        else:
            n = x * 10 ** 9
        if n < 0:
            raise ValueError("sleep length must be non-negative")
        _state[0] += n

    def _localtime(secs=None):
        return _real_localtime(_state[0] // 10 ** 9 if secs is None else secs)

    def _gmtime(secs=None):
        return _real_gmtime(_state[0] // 10 ** 9 if secs is None else secs)

    def _strftime(fmt, t=None):
        return _real_strftime(fmt, _real_localtime(_state[0] // 10 ** 9) if t is None else t)
    _t.time, _t.time_ns, _t.sleep = _time, _time_ns, _sleep
    _t.localtime, _t.gmtime, _t.strftime = _localtime, _gmtime, _strftime

    class FakeDT(_real_dt):
        def __repr__(self):
            return "datetime.datetime" + _real_dt.__repr__(self)[len(type(self).__name__):]

        @classmethod
        def now(cls, tz=None):
            secs, us = divmod(_state[0] // 1000, 10 ** 6)
            r = _real_dt.fromtimestamp(secs, tz)
            return cls(r.year, r.month, r.day, r.hour, r.minute, r.second, us, r.tzinfo, fold=r.fold)

        @classmethod
        def fromtimestamp(cls, t, tz=None):
            r = _real_dt.fromtimestamp(t, tz)
            return cls(r.year, r.month, r.day, r.hour, r.minute, r.second, r.microsecond, r.tzinfo, fold=r.fold)

        @classmethod
        def utcnow(cls):
            secs, us = divmod(_state[0] // 1000, 10 ** 6)
            r = _real_dt.utcfromtimestamp(secs)
            return cls(r.year, r.month, r.day, r.hour, r.minute, r.second, us)
    _d.datetime = FakeDT
runpy.run_path(sys.argv[1], run_name="__main__")
'''


def oracle_env(zone, clock):
    env = dict(os.environ, PYTHONUTF8="1", TZ=zone)
    env.pop("PYTHONPATH", None)
    if clock is None:
        env.pop("AIL_CLOCK", None)
    else:
        env["AIL_CLOCK"] = clock
    return env


def build(src, exe, ir, typed, cwd=None):
    env = dict(os.environ, AIL_IR=ir)
    env.pop("AIL_NO_GENERAL", None)
    env.pop("AIL_TARGET", None)
    env.pop("AIL_CLOCK", None)
    if typed:
        env["AIL_NO_GENERAL"] = "1"
    return subprocess.run([sys.executable, "-B", CLI, "compile", str(src), "-o", str(exe)], cwd=cwd,
                          capture_output=True, text=True, timeout=900, env=env)


class Base(unittest.TestCase):
    def compare(self, name, text, zones=ZONES, clocks=CLOCKS, typed=True, irs=("0", "1"), general=False):
        """The compiled program prints what CPython prints under the fake clock, for every zone and clock."""
        with tempfile.TemporaryDirectory(prefix="ail-clock-") as tmp:
            src = Path(tmp) / (name + ".py")
            src.write_text(text, encoding="utf-8")
            prelude = Path(tmp) / "fake_clock.py"
            prelude.write_text(FAKE_CLOCK, encoding="utf-8")
            wants = {}
            for zone in zones:
                for clock in clocks:
                    want = subprocess.run([sys.executable, str(prelude), str(src)], cwd=tmp, capture_output=True,
                                          timeout=300, env=oracle_env(zone, clock))
                    self.assertEqual(want.returncode, 0, (zone, clock, want.stderr.decode()))
                    self.assertTrue(want.stdout, "the program prints nothing")
                    wants[(zone, clock)] = want.stdout
            for ir in irs:
                exe = Path(tmp) / ("exe" + ir)
                built = build(src, exe, ir, typed and not general, cwd=tmp)
                self.assertEqual(built.returncode, 0, "AIL_IR=%s: %s" % (ir, built.stderr[-3000:]))
                if general:
                    self.assertIn("general path", built.stderr)
                for (zone, clock), want in wants.items():
                    got = subprocess.run([str(exe)], cwd=tmp, capture_output=True, timeout=300,
                                         env=oracle_env(zone, clock))
                    self.assertEqual(got.returncode, 0, (zone, clock, got.stderr.decode()))
                    if got.stdout != want:
                        a = want.decode("utf-8", "replace").split("\n")
                        b = got.stdout.decode("utf-8", "replace").split("\n")
                        for i in range(max(len(a), len(b))):
                            x = a[i] if i < len(a) else "<none>"
                            y = b[i] if i < len(b) else "<none>"
                            if x != y:
                                self.fail("AIL_IR=%s TZ=%s AIL_CLOCK=%s line %d: CPython %r, AIL %r"
                                          % (ir, zone, clock, i + 1, x[:200], y[:200]))

    def refused(self, text, *needles, general_ok=False):
        with tempfile.TemporaryDirectory(prefix="ail-clock-") as tmp:
            src = Path(tmp) / "prog.py"
            src.write_text(text, encoding="utf-8")
            built = build(src, Path(tmp) / "exe", "1", not general_ok, cwd=tmp)
            self.assertNotEqual(built.returncode, 0, built.stdout)
            self.assertFalse((Path(tmp) / "exe").exists())
            self.assertNotIn("Traceback", built.stderr)
            for needle in needles:
                self.assertIn(needle, built.stderr)
            return built.stderr


TIME_PROGRAM = '''import time


def main() -> None:
    a = time.time()
    b = time.time_ns()
    print(a, b, a == b / 1e9)
    time.sleep(0.25)
    c = time.time()
    print(c, time.time_ns(), c - a, time.time_ns() - b)
    time.sleep(2)
    print(time.time_ns() - b)
    time.sleep(1e-9)
    print(time.time_ns() - b)
    time.sleep(0)
    time.sleep(0.1 + 0.2)
    print(time.time_ns() - b, time.time())
    for x in [1.0, 0.5, 2.5e-7, 12.0]:
        t0 = time.time_ns()
        time.sleep(x)
        print(x, time.time_ns() - t0)
    try:
        time.sleep(-1)
    except ValueError:
        print("ValueError")
    try:
        time.sleep(-0.5)
    except ValueError:
        print("ValueError")
    s = time.perf_counter()
    time.sleep(3)
    print(time.perf_counter() - s < 1.0)


main()
'''

FROM_IMPORT_PROGRAM = '''from time import time, time_ns, sleep


def main() -> None:
    t = time()
    n = time_ns()
    sleep(1.5)
    print(t, n, time() - t, time_ns() - n)


main()
'''

NOW_PROGRAM = '''import datetime


def show(d: datetime.datetime) -> None:
    print(d.isoformat(), d.weekday(), d.strftime("%A %d %B %Y %H:%M:%S.%f %j %U"))


def main() -> None:
    show(datetime.datetime.now())
    show(datetime.datetime.utcnow())
    show(datetime.datetime.today())
    print(datetime.date.today(), datetime.date.today().isoformat(), datetime.date.today().weekday())
    n = datetime.datetime.now()
    later = n + datetime.timedelta(hours=30, microseconds=7)
    print(later - n, (later - n).total_seconds(), later > n, n == datetime.datetime.now())
    print(datetime.datetime.now().date() == datetime.date.today())
    print(n.year, n.month, n.day, n.hour, n.minute, n.second, n.microsecond)
    print(datetime.datetime.now() - datetime.datetime.utcnow())
    print(repr(n), str(n))
    print(n.timestamp())
    print(datetime.datetime.utcnow().timestamp())


main()
'''

FROM_IMPORT_NOW = '''from datetime import date, datetime
import time


def main() -> None:
    n = datetime.now()
    t = time.time()
    time.sleep(90000)
    m = datetime.now()
    print(n, m, m - n, date.today())
    print(datetime.fromtimestamp(t), t)
    print(time.strftime("%Y-%m-%d %H:%M:%S %Z %z"), time.time() - t)
    print((m - n).days, (m - n).seconds)


main()
'''

TIMESTAMPS = [0.0, 1.0, -1.0, 0.5, -0.5, 1.5, 1700000000.0, 1700000000.123456, 1700000000.9999995, 951782400.0,
              1710054000.0, 1710053999.999999, 1710054000.000001, 1730613600.0, 1730617200.0, 1711846800.0,
              1711846799.5, 1743296400.0, 1.4e9, 2147483647.0, 2147483648.5, 4102444800.0, 253402300799.0,
              -62135596800.0, -2208988800.0, 86400.0, 0.0000005, 1.0000005, 1.0000015, 2.5e-7, 123456789.987654321,
              1e10, -1e10, 5e-7, 1.9999995, 1.9999994999]

STRUCT_PROGRAM = '''import time


def fields(t: time.struct_time) -> str:
    return " ".join([str(t.tm_year), str(t.tm_mon), str(t.tm_mday), str(t.tm_hour), str(t.tm_min), str(t.tm_sec),
                     str(t.tm_wday), str(t.tm_yday), str(t.tm_isdst), t.tm_zone, str(t.tm_gmtoff)])


def main() -> None:
    stamps = [@STAMPS@]
    for s in stamps:
        a = time.localtime(s)
        b = time.gmtime(s)
        print(s, "|", fields(a), "|", fields(b))
        print(time.strftime("%Y-%m-%d %H:%M:%S %Z %z|%a %A %b %B|%j %U %W %w %u|%I %p %y %C|%c|%x|%X|%e %k %l|%%", a))
        print(time.strftime("%Y-%m-%d %H:%M:%S %Z %z|%G %V %g %D %F %T %R %r %h %n %t.", b))
        print(time.mktime(a), time.mktime(b))
    print(fields(time.localtime()), fields(time.gmtime()))
    print(time.strftime("%Y-%m-%d %H:%M:%S %Z %z"), time.strftime("%j"))
    print(time.mktime(time.localtime()), time.mktime(time.localtime(86400)))
    n = time.localtime(None)
    print(n.tm_year, time.gmtime(None).tm_hour)
    time.sleep(40000)
    print(fields(time.localtime()), time.strftime("%H:%M:%S"))


main()
'''

MKTIME_PROGRAM = '''import time


def main() -> None:
    for isdst in [-1, 0, 1]:
        for month in [1, 3, 4, 6, 9, 10, 11, 12]:
            for day in [1, 10, 11, 25, 28, 31]:
                for hour in [0, 1, 2, 3, 12, 23]:
                    try:
                        print(isdst, month, day, hour, time.mktime((2024, month, day, hour, 30, 0, 0, 0, isdst)))
                    except OverflowError:
                        print("overflow")
    print(time.mktime((1970, 1, 1, 0, 0, 0, 0, 0, 0)), time.mktime((2024, 2, 30, 25, 61, 61, 0, 0, -1)))
    print(time.mktime((1900, 1, 1, 0, 0, 0, 0, 0, -1)), time.mktime((2100, 6, 1, 12, 0, 0, 0, 0, -1)))
    print(time.mktime((1, 1, 1, 0, 0, 0, 0, 0, -1)))


main()
'''

FROMTS_PROGRAM = '''import datetime


def show(d: datetime.datetime) -> str:
    return d.isoformat(" ") + " " + str(d.timestamp())


def main() -> None:
    stamps = [@STAMPS@]
    for s in stamps:
        a = datetime.datetime.fromtimestamp(s)
        b = datetime.datetime.utcfromtimestamp(s)
        print(s, "|", show(a), "|", b.isoformat(" "), "|", datetime.date.fromtimestamp(s))
    for k in range(-3, 4):
        print(datetime.datetime.fromtimestamp(k * 0.4999999 + 1.0), datetime.datetime.fromtimestamp(1700000000 + k))
    for s in [-1e20, 1e20, 1e12, -1e12, 3e11, 1e15, -62135596800.0, 253402300799.0, -62135510400.0, 253402214400.0, -3e18]:
        try:
            print(datetime.datetime.fromtimestamp(s))
        except ValueError:
            print("ValueError")
        except OverflowError:
            print("OverflowError")
        except OSError:
            print("OSError")
        try:
            print(datetime.date.fromtimestamp(s))
        except ValueError:
            print("ValueError")
        except OverflowError:
            print("OverflowError")
        except OSError:
            print("OSError")


main()
'''

TIMESTAMP_METHOD_PROGRAM = '''import datetime


def main() -> None:
    base = datetime.datetime(2024, 1, 1)
    for h in range(0, 24 * 366, 7):
        d = base + datetime.timedelta(hours=h, minutes=h % 60, microseconds=h * 77)
        print(d, d.timestamp())
    for y in [1971, 1999, 2038, 2100]:
        for m in [3, 10, 11]:
            for dd in [1, 25, 28]:
                for hh in [0, 1, 2, 3, 4]:
                    d = datetime.datetime(y, m, dd, hh, 30)
                    print(d, d.timestamp())


main()
'''

GENERAL_PROGRAM = '''import datetime
import time


class Bag:
    def __init__(self, v):
        self.v = v


b = Bag(3)
b.w = 4.5
mixed = [1, "a", 2.5]
t = time.time()
n = time.time_ns()
time.sleep(2.5)
print(b.v + b.w, len(mixed), t, n, time.time() - t, time.time_ns() - n)
m = time.localtime(1700000000)
print(m.tm_year, m.tm_hour, m.tm_zone, time.strftime("%Y-%m-%d %H:%M:%S %Z", m), time.mktime(m))
print(time.strftime("%H:%M:%S", time.gmtime(3661)))
d = datetime.datetime.fromtimestamp(1700000000.5)
print(d, datetime.datetime.now(), datetime.date.today())
'''


AWARE_PROGRAM = '''import datetime
from datetime import timedelta, timezone


def show(d: datetime.datetime) -> None:
    print(d, repr(d), d.isoformat(), d.utcoffset(), d.tzname(), d.timestamp())
    print(d.strftime("%Y-%m-%d %H:%M:%S %z %Z %A %j"), d.weekday(), d.date(), d.time())


def main() -> None:
    utc = timezone.utc
    ist = timezone(timedelta(hours=5, minutes=30))
    jst = timezone(timedelta(hours=9), "JST")
    odd = timezone(timedelta(hours=-3, seconds=15))
    print(utc, repr(utc), ist, repr(ist), jst, repr(jst), odd, repr(odd))
    print(ist.utcoffset(None), ist.tzname(None), jst.tzname(None), utc.tzname(None), timezone(timedelta(0)) == utc, ist == jst)
    a = datetime.datetime(2024, 3, 5, 12, 30, 45, 123456, tzinfo=ist)
    b = datetime.datetime(2024, 3, 5, 7, 0, 45, 123456, tzinfo=utc)
    c = datetime.datetime(2024, 1, 31, 23, 59, tzinfo=jst)
    show(a)
    show(b)
    show(c)
    print(a == b, a < b, a > b, a != b, a <= b, a >= b, a - b, b - a)
    print(a + timedelta(days=1, hours=20), c - timedelta(minutes=1))
    print(a.astimezone(utc), a.astimezone(jst), b.astimezone(odd), c.astimezone(ist))
    print(a.replace(tzinfo=None), a.replace(tzinfo=jst), a.replace(hour=1, tzinfo=odd), b.replace(minute=0))
    xs = [a, b, c, a + timedelta(hours=3), c - timedelta(days=2)]
    for y in sorted(xs):
        print(y)
    print(max(xs), min(xs), max(a, b), min(a, b))
    n = datetime.datetime.now(utc)
    m = datetime.datetime.now(jst)
    print(n, m, n == m, m - n, n.tzinfo is None, datetime.datetime.now().tzinfo is None, a.tzinfo is not None)
    print(datetime.datetime.fromtimestamp(1700000000.123456, ist), datetime.datetime.fromtimestamp(0, utc))
    print(datetime.datetime.fromtimestamp(-1.5, odd))
    print(datetime.datetime.fromisoformat("2024-01-02T03:04:05Z"), repr(datetime.datetime.fromisoformat("2024-01-02T03:04:05+00:00")))
    print(repr(datetime.datetime.fromisoformat("2024-01-02T03:04:05.5-03:30")), datetime.datetime.fromisoformat("2024-01-02 03:04:05+23:59:59"))
    print(datetime.datetime.fromisoformat("2024-01-02T03:04:05"))
    local = datetime.datetime(2024, 7, 1, 12, 0)
    print(local.astimezone(utc), local.astimezone(ist), local.timestamp())
    loc = local.astimezone()
    print(loc, repr(loc), loc.tzname(), loc.utcoffset())
    print(datetime.datetime.now(utc).astimezone(), datetime.datetime.now().astimezone(jst))
    u = datetime.datetime.now(datetime.UTC)
    print(u, f"{u:%Y-%m-%d %H:%M:%S%z}", "%s|%s" % (u, jst))
    print(str(ist), str(utc), repr(jst))


main()
'''

AWARE_LOOP_PROGRAM = '''from datetime import datetime, timedelta, timezone


def main() -> None:
    zones = [timezone.utc, timezone(timedelta(hours=-12)), timezone(timedelta(hours=14)), timezone(timedelta(minutes=-90), "X"),
             timezone(timedelta(hours=5, minutes=45)), timezone(timedelta(seconds=1)), timezone(timedelta(hours=-23, minutes=-59, seconds=-59))]
    stamps = [0.0, 86399.5, 1700000000.9999995, 1710054000.0, 4102444800.123456, 951782400.0, 253402128000.0, 86400.0]
    ds: list[datetime] = []
    for z in zones:
        for s in stamps:
            d = datetime.fromtimestamp(s, z)
            ds.append(d)
            print(d.isoformat(), d.strftime("%z %Z"), d.utcoffset(), d.timestamp(), repr(d), d.tzname())
    total = timedelta()
    ds.sort()
    for i in range(1, len(ds)):
        total += ds[i] - ds[i - 1]
        if ds[i] == ds[i - 1]:
            print("same", ds[i])
    print(total, ds[0], ds[-1], total.total_seconds())
    for d in ds[::9]:
        e = d.astimezone(timezone(timedelta(hours=3, minutes=7)))
        print(e, e == d, e.date(), e.replace(tzinfo=None) - d.replace(tzinfo=None))


main()
'''


AWARE_GENERAL_PROGRAM = '''import datetime
from datetime import timedelta, timezone


class Bag:
    def __init__(self, v):
        self.v = v


b = Bag(3)
b.w = 4.5
mixed = [1, "a", 2.5]
jst = timezone(timedelta(hours=9), "JST")
n = datetime.datetime.now(jst)
print(b.v + b.w, len(mixed), n, repr(n), n.utcoffset(), n.tzname())
m = datetime.datetime.fromtimestamp(1700000000.5, timezone.utc)
print(m, m < n, n - m, m.astimezone(jst), m.timestamp(), m.replace(tzinfo=None), m.tzinfo is None)
for d in sorted([n, m]):
    print(d.isoformat(), d.strftime("%z %Z"))
'''


class ClockPrograms(Base):
    def test_time_time_ns_sleep(self):
        self.compare("time_prog", TIME_PROGRAM)

    def test_from_import_names(self):
        self.compare("from_import", FROM_IMPORT_PROGRAM, clocks=CLOCKS[:3], zones=ZONES[:2])

    def test_datetime_now_family(self):
        self.compare("now_prog", NOW_PROGRAM)

    def test_from_import_datetime_and_time_together(self):
        self.compare("from_now", FROM_IMPORT_NOW)

    def test_struct_time_functions(self):
        stamps = ", ".join(repr(x) for x in TIMESTAMPS if x not in (-62135596800.0, 253402300799.0))
        self.compare("struct_prog", STRUCT_PROGRAM.replace("@STAMPS@", stamps), clocks=CLOCKS[:4])

    def test_mktime_tuples(self):
        self.compare("mktime_prog", MKTIME_PROGRAM, clocks=CLOCKS[:1])

    def test_fromtimestamp(self):
        stamps = ", ".join(repr(x) for x in TIMESTAMPS if x not in (-62135596800.0, 253402300799.0))
        self.compare("fromts_prog", FROMTS_PROGRAM.replace("@STAMPS@", stamps), clocks=CLOCKS[:1])

    def test_timestamp_method(self):
        self.compare("tsmethod_prog", TIMESTAMP_METHOD_PROGRAM, clocks=CLOCKS[:1])

    def test_aware_datetimes(self):
        self.compare("aware_prog", AWARE_PROGRAM, clocks=CLOCKS[:3], zones=ZONES[:3])

    def test_aware_datetimes_over_many_zones_and_stamps(self):
        self.compare("aware_loop", AWARE_LOOP_PROGRAM, clocks=CLOCKS[:1], zones=ZONES[:2])

    def test_aware_datetimes_on_the_general_path(self):
        self.compare("aware_general", AWARE_GENERAL_PROGRAM, typed=False, general=True, irs=("1",),
                     clocks=CLOCKS[:2], zones=ZONES[:2])

    def test_general_path(self):
        self.compare("general_prog", GENERAL_PROGRAM, typed=False, general=True, irs=("1",),
                     clocks=CLOCKS[:3], zones=ZONES[:3])


class ClockWithoutPin(Base):
    def run_program(self, text, ir="1", env_extra=None):
        with tempfile.TemporaryDirectory(prefix="ail-clock-") as tmp:
            src = Path(tmp) / "prog.py"
            src.write_text(text, encoding="utf-8")
            exe = Path(tmp) / "exe"
            built = build(src, exe, ir, True, cwd=tmp)
            self.assertEqual(built.returncode, 0, built.stderr[-3000:])
            env = oracle_env("UTC0", None)
            env.update(env_extra or {})
            return subprocess.run([str(exe)], cwd=tmp, capture_output=True, timeout=120, env=env)

    def test_real_clock_and_real_sleep(self):
        text = ('import datetime\nimport time\n\n\ndef main() -> None:\n    a = time.time()\n    p = time.perf_counter()\n'
                '    time.sleep(0.3)\n    b = time.time()\n    q = time.perf_counter()\n    n = datetime.datetime.now()\n'
                '    print(b - a >= 0.3, b - a < 5.0, q - p >= 0.29)\n    print(a, n.isoformat())\n\n\nmain()\n')
        for ir in ("0", "1"):
            before = time.time()
            ran = self.run_program(text, ir)
            after = time.time()
            self.assertEqual(ran.returncode, 0, ran.stderr)
            lines = ran.stdout.decode().split("\n")
            self.assertEqual(lines[0], "True True True")
            stamp, iso = lines[1].split(" ")
            self.assertTrue(before - 1 <= float(stamp) <= after + 1)
            import datetime
            self.assertLess(abs((datetime.datetime.fromisoformat(iso) - datetime.datetime.utcnow()).total_seconds()), 10)

    def test_malformed_pin_is_a_value_error(self):
        text = 'import time\n\n\ndef main() -> None:\n    print(time.time())\n\n\nmain()\n'
        guarded = ('import time\n\n\ndef main() -> None:\n    try:\n        print(time.time())\n    except ValueError:\n'
                   '        print("ValueError")\n\n\nmain()\n')
        for bad in ("abc", "1.5x", "1e9", ".5", "1700000000.25.5", "--1", "9999999999999"):
            ran = self.run_program(text, env_extra={"AIL_CLOCK": bad})
            self.assertEqual(ran.returncode, 1, bad)
            self.assertIn("ValueError: AIL_CLOCK must be a number of seconds since the epoch, like 1700000000.25",
                          ran.stderr.decode(), bad)
            ran = self.run_program(guarded, env_extra={"AIL_CLOCK": bad})
            self.assertEqual((ran.returncode, ran.stdout.decode()), (0, "ValueError\n"), bad)

    def test_pin_forms(self):
        text = 'import time\n\n\ndef main() -> None:\n    print(time.time_ns())\n    time.sleep(0.5)\n    print(time.time_ns())\n\n\nmain()\n'
        for pin, first in (("5", 5000000000), ("5.", 5000000000), ("5.0000000019", 5000000001), ("+7.5", 7500000000),
                           ("0.000000001", 1), ("-2.5", -2500000000), ("0", 0), ("9223372035", 9223372035000000000)):
            ran = self.run_program(text, env_extra={"AIL_CLOCK": pin})
            self.assertEqual(ran.stdout.decode(), "%d\n%d\n" % (first, first + 500000000), pin)


class ClockRefusals(Base):
    def test_aware_and_unbuilt_forms_are_named(self):
        self.refused("import datetime\n\n\ndef main():\n    print(datetime.timezone.min)\n\n\nmain()\n",
                     "datetime.timezone.min has a microsecond offset")
        self.refused("import datetime\n\n\nclass Z(datetime.tzinfo):\n    pass\n\n\ndef main():\n    print(1)\n\n\nmain()\n",
                     "a tzinfo subclass is not built")
        self.refused("import zoneinfo\n\n\ndef main():\n    print(zoneinfo.ZoneInfo('Asia/Tokyo'))\n\n\nmain()\n",
                     "zoneinfo: a named time zone needs the tz database")
        self.refused("import datetime\n\n\ndef main():\n    d = datetime.datetime.now(datetime.timezone.utc)\n    print(d.dst())\n\n\nmain()\n",
                     ".dst()")
        self.refused("import datetime\n\n\ndef main():\n    d = datetime.datetime.now(datetime.timezone.utc)\n    print(d.tzinfo)\n\n\nmain()\n",
                     ".tzinfo used as a value is not built")
        self.refused("import time\n\n\ndef main():\n    print(time.asctime())\n\n\nmain()\n", "time.asctime() with these arguments is not built")
        self.refused("import time\n\n\ndef main():\n    print(time.strftime('%Y', (2024, 1, 1, 0, 0, 0, 0, 0, 0)))\n\n\nmain()\n",
                     "strftime(format, tuple) is not built")
        self.refused("import time\n\n\ndef main():\n    print(time.tzname)\n\n\nmain()\n", "time.tzname used as a value is not built")
        self.refused("import time\n\n\ndef main():\n    print(time.sleep(1, 2))\n\n\nmain()\n", "sleep(seconds)")

    def test_unseeded_random_is_still_refused(self):
        self.refused("import random\n\n\ndef main():\n    print(random.random())\n\n\nmain()\n", "seed")


class PlainBase(unittest.TestCase):
    """dtrt.py's clock functions are plain Python: CPython runs them with stand-ins for the C primitives."""

    def setUp(self):
        sys.path.insert(0, str(CORE_DIR))
        try:
            import dtrt
        finally:
            sys.path.pop(0)
        self.R = dtrt
        self._old_tz = os.environ.get("TZ")
        self.state = {"ns": 1700000000123456789}
        R = dtrt
        BAD = -(2 ** 63)

        def days_from_civil(y, m, d):
            y -= m <= 2
            era = y // 400
            yoe = y - era * 400
            doy = (153 * (m + (-3 if m > 2 else 9)) + 2) // 5 + d - 1
            doe = yoe * 365 + yoe // 4 - yoe // 100 + doy
            return era * 146097 + doe - 719468

        def local(secs):
            try:
                return time.localtime(secs)
            except (OverflowError, OSError, ValueError):
                return None

        def local_offset(secs):
            t = local(secs)
            if t is None:
                return BAD
            return days_from_civil(t.tm_year, t.tm_mon, t.tm_mday) * 86400 + t.tm_hour * 3600 + t.tm_min * 60 + t.tm_sec - secs

        def isdst(secs):
            t = local(secs)
            return BAD if t is None else (1 if t.tm_isdst > 0 else (0 if t.tm_isdst == 0 else -1))

        def tz_name(secs):
            t = local(secs)
            if t is None:
                return BAD
            v = 0
            for i, c in enumerate(t.tm_zone.encode()[:7]):
                v |= c << (8 * i)
            return v

        def mk(y, mo, d, h, mi, s, dst):
            try:
                return int(time.mktime((y, mo, d, h, mi, s, 0, 0, dst)))
            except (OverflowError, OSError, ValueError):
                return BAD
        self.slept = []
        R._ail_time_ns = lambda: self.state["ns"]
        R._ail_time = lambda: (self.state["ns"] // 10 ** 9) * 1.0 if self.state["ns"] % 10 ** 9 == 0 else float(self.state["ns"]) / 1e9
        R._ail_sleep_ns = lambda n: self.slept.append(n) or 0
        R._ail_local_offset, R._ail_local_isdst, R._ail_tz_name, R._ail_mktime = local_offset, isdst, tz_name, mk

    def tearDown(self):
        if self._old_tz is None:
            os.environ.pop("TZ", None)
        else:
            os.environ["TZ"] = self._old_tz
        time.tzset()

    def zone(self, name):
        os.environ["TZ"] = name
        time.tzset()

    @staticmethod
    def outcome(f):
        try:
            return ("ok", f())
        except RuntimeError:
            return ("limit",)
        except Exception as e:
            return (type(e).__name__, str(e))

    def view(self, x):
        return (x.kind, x.year, x.month, x.day, x.hour, x.minute, x.second, x.microsecond)

    def pyview(self, x):
        if isinstance(x, __import__("datetime").datetime):
            return (1, x.year, x.month, x.day, x.hour, x.minute, x.second, x.microsecond)
        return (0, x.year, x.month, x.day, 0, 0, 0, 0)

    def stamps(self, rng, n):
        out = list(TIMESTAMPS)
        for _ in range(n):
            kind = rng.random()
            if kind < 0.3:
                out.append(float(rng.randint(-3 * 10 ** 9, 5 * 10 ** 9)))
            elif kind < 0.6:
                out.append(rng.randint(-3 * 10 ** 9, 5 * 10 ** 9) + rng.randint(0, 2 * 10 ** 6) / 2e6)
            elif kind < 0.8:
                out.append(rng.uniform(-3e9, 5e9))
            elif kind < 0.9:
                out.append(rng.choice([1710054000, 1730613600, 1711846800, 1743296400, 1729990800]) + rng.randint(-7300, 7300) / 2.0)
            else:
                out.append(rng.choice([-1, 1]) * 10 ** rng.uniform(0, 21))
        return out



class ClockRuntimeInPlainPython(PlainBase):
    def test_fromtimestamp_family(self):
        import datetime as D
        R = self.R
        rng = random.Random(901)
        bad = []
        checked = 0
        for zone in ZONES:
            self.zone(zone)
            for t in self.stamps(rng, 700):
                checks = [
                    ("fromtimestamp", self.outcome(lambda: self.view(R.dt_from_ts(t, False))),
                     self.outcome(lambda: self.pyview(D.datetime.fromtimestamp(t)))),
                    ("utcfromtimestamp", self.outcome(lambda: self.view(R.dt_from_ts(t, True))),
                     self.outcome(lambda: self.pyview(D.datetime.utcfromtimestamp(t)))),
                    ("date.fromtimestamp", self.outcome(lambda: self.view(R.date_from_ts(t))),
                     self.outcome(lambda: self.pyview(D.date.fromtimestamp(t)))),
                ]
                for name, got, want in checks:
                    checked += 1
                    if got != want and got[:1] != ("limit",):
                        bad.append((zone, t, name, got, want))
        self.assertEqual(bad[:5], [])
        self.assertGreater(checked, 14000)

    def test_now_and_today(self):
        import datetime as D
        R = self.R
        rng = random.Random(902)
        bad = []
        for zone in ZONES:
            self.zone(zone)
            for _ in range(300):
                ns = rng.randint(0, 4 * 10 ** 18) if rng.random() < 0.7 else rng.randint(1700000000, 1900000000) * 10 ** 9 + rng.randint(0, 10 ** 9)
                self.state["ns"] = ns
                secs, us = divmod(ns // 1000, 10 ** 6)
                pairs = [
                    ("now", self.view(R.now_local()), self.pyview(D.datetime.fromtimestamp(secs).replace(microsecond=us))),
                    ("utcnow", self.view(R.now_utc()), self.pyview(D.datetime.utcfromtimestamp(secs).replace(microsecond=us))),
                    ("today", self.view(R.dt_today()), self.pyview(D.datetime.fromtimestamp(R._ail_time()))),
                    ("date.today", self.view(R.date_today()), self.pyview(D.date.fromtimestamp(R._ail_time()))),
                ]
                for name, got, want in pairs:
                    if got != want:
                        bad.append((zone, ns, name, got, want))
        self.assertEqual(bad[:5], [])

    def test_naive_timestamp(self):
        import datetime as D
        R = self.R
        rng = random.Random(903)
        bad = []
        checked = 0
        for zone in ZONES:
            self.zone(zone)
            for _ in range(900):
                base = rng.choice([1710054000, 1730613600, 1711846800, 1743296400, 1729990800, 1700000000, 0])
                t = base + rng.randint(-100000, 100000)
                dt = D.datetime(1970, 1, 1) + D.timedelta(seconds=t, microseconds=rng.choice([0, 1, 999999, rng.randint(0, 999999)]))
                rd = R.mk_datetime(dt.year, dt.month, dt.day, dt.hour, dt.minute, dt.second, dt.microsecond)
                checked += 1
                got = self.outcome(lambda: R.timestamp(rd))
                want = self.outcome(lambda: dt.timestamp())
                if got != want and got[:1] != ("limit",):
                    bad.append((zone, str(dt), got, want))
        self.assertEqual(bad[:5], [])

    def test_struct_time_functions(self):
        R = self.R
        rng = random.Random(904)
        bad = []
        formats = ["%Y-%m-%d %H:%M:%S %Z %z", "%a %A %b %B %j %U %W %w %u", "%c|%x|%X|%p|%I", "%G-W%V-%u %g %e %k %l %P",
                   "%%z %Z%%", "%z%Z", "", "%Q %q %", "plain text"]
        for zone in ZONES:
            self.zone(zone)
            for t in self.stamps(rng, 500):
                def tmv(x):
                    return (x.tm_year, x.tm_mon, x.tm_mday, x.tm_hour, x.tm_min, x.tm_sec, x.tm_wday, x.tm_yday,
                            x.tm_isdst, x.tm_zone, x.tm_gmtoff)
                for name, mine, real in (("localtime", R.tm_local, time.localtime), ("gmtime", R.tm_gm, time.gmtime)):
                    got = self.outcome(lambda: tmv(mine(t)))
                    want = self.outcome(lambda: tmv(real(t)))
                    if got != want and got[:1] != ("limit",):
                        bad.append((zone, t, name, got, want))
                        continue
                    if want[0] != "ok":
                        continue
                    f = rng.choice(formats)
                    got = self.outcome(lambda: R.tm_strftime(f, mine(t)))
                    want = self.outcome(lambda: time.strftime(f, real(t)))
                    if got != want and got[:1] != ("limit",) and not (want[0] != "ok" and got[0] != "ok"):
                        bad.append((zone, t, name, f, got, want))
                y, mo, d = rng.choice([1900, 1970, 2024, 2038, 2100, 9999, 1, 0, -5]), rng.randint(0, 13), rng.randint(0, 32)
                h, mi, s = rng.randint(-1, 25), rng.randint(-1, 61), rng.randint(-1, 62)
                dst = rng.choice([-1, 0, 1])
                got = self.outcome(lambda: R.mktime_fields(y, mo, d, h, mi, s, dst))
                want = self.outcome(lambda: time.mktime((y, mo, d, h, mi, s, 0, 0, dst)))
                if got != want and got[:1] != ("limit",):
                    bad.append((zone, "mktime", (y, mo, d, h, mi, s, dst), got, want))
        self.assertEqual(bad[:5], [])

    def test_fold_and_timestamp_roundtrip(self):
        import datetime as D
        R = self.R
        rng = random.Random(905)
        bad = []
        for zone in ZONES:
            self.zone(zone)
            for base in (1710054000, 1730613600, 1711846800, 1743296400, 1729990800, 1699164000, 1730617200):
                for _ in range(250):
                    t = base + rng.randint(-8000, 8000) + rng.choice([0, 0.25, 0.5])
                    got = self.outcome(lambda: R.timestamp(R.dt_from_ts(t, False)))
                    want = self.outcome(lambda: D.datetime.fromtimestamp(t).timestamp())
                    if got != want:
                        bad.append((zone, t, got, want))
        self.assertEqual(bad[:5], [])

    def test_sleep_checks(self):
        R = self.R
        for x in (-1, -0.5, float("nan"), float("inf"), -float("inf"), 1e300, 9.3e9, -1e-300):
            got = self.outcome(lambda: R.sleep_for(float(x)))
            want = self.outcome(lambda: time.sleep(x))
            self.assertEqual(got, want, x)
        self.slept.clear()
        R.sleep_for(1e-9)
        R.sleep_for(0.1 + 0.2)
        R.sleep_for(2.0)
        R.sleep_for(0.0)
        self.assertEqual(self.slept, [1, 300000001, 2000000000, 0])


class AwareRuntimeInPlainPython(PlainBase):
    """The aware functions of dtrt.py (fixed-offset zones) against datetime.timezone on generated values."""

    def pair(self, rng, naive=False):
        """(dtrt value, datetime value, aware code) with a random fixed-offset zone; the code is 0 naive, 1 aware,
        2 aware with a named zone (the `aware` field of dtrt's AilDT)."""
        import datetime as D
        R = self.R
        y = rng.choice([1, 2, 1970, 2000, 2024, 9998, 9999, rng.randint(1, 9999)])
        m, d = rng.randint(1, 12), rng.randint(1, 28)
        hh, mi, ss, us = rng.randint(0, 23), rng.randint(0, 59), rng.randint(0, 59), rng.choice([0, 1, 999999, rng.randint(0, 999999)])
        base = R.mk_datetime(y, m, d, hh, mi, ss, us)
        dt = D.datetime(y, m, d, hh, mi, ss, us)
        if naive:
            return base, dt, 0
        off = rng.choice([0, 3600, -3600, 19800, -12600, 32400, 86399, -86399, 15, -15, rng.randint(-86399, 86399)])
        name = rng.choice([None, None, "JST", "X", "", "Zone/Name"])
        tz = D.timezone(D.timedelta(seconds=off), name) if name is not None else D.timezone(D.timedelta(seconds=off))
        named = 0 if name is None else 1
        return R.aw_set(base, off, name or "", named), dt.replace(tzinfo=tz), 1 + named

    def aview(self, x):
        return (x.kind, x.year, x.month, x.day, x.hour, x.minute, x.second, x.microsecond, x.aware, x.off)

    @staticmethod
    def pyaview(x, code):
        off = 0 if x.tzinfo is None else int(x.utcoffset().total_seconds())
        return (1, x.year, x.month, x.day, x.hour, x.minute, x.second, x.microsecond, code, off)

    def test_text_and_formats(self):
        import datetime as D
        R = self.R
        rng = random.Random(911)
        bad = []
        formats = ["%Y-%m-%d %H:%M:%S %z %Z", "%z|%Z|%%z|%%Z", "%A %d %B %Y%z", "%c %x %X %Z", "", "%f%z", "%j %U %z"]
        for _ in range(4000):
            rd, dt, _code = self.pair(rng)
            f = rng.choice(formats)
            sep = rng.choice(["T", " ", "x"])
            spec = rng.choice(["auto", "hours", "minutes", "seconds", "milliseconds", "microseconds"])
            for name, got, want in (
                    ("str", R.text_aw(rd), str(dt)),
                    ("repr", R.rep_aw(rd), repr(dt)),
                    ("iso", R.iso_aw(rd, sep, spec), dt.isoformat(sep, spec)),
                    ("fmt", R.fmt_aw(rd, f), dt.strftime(f)),
                    ("utcoffset", R.utcoffset_aw(rd).k, dt.utcoffset() // D.timedelta(microseconds=1)),
                    ("tzname", R.tzname_aw(rd), dt.tzname()),
                    ("timestamp", R.timestamp_aw(rd), dt.timestamp()),
                    ("tzstr", R.tz_name(R.aw_tz(rd)), str(dt.tzinfo)),
                    ("tzrepr", R.tz_rep(R.aw_tz(rd)), repr(dt.tzinfo))):
                if got != want:
                    bad.append((name, f, sep, spec, got, want))
            nd, ndt, _ = self.pair(rng, True)
            for name, got, want in (("nstr", R.text_aw(nd), str(ndt)), ("nrepr", R.rep_aw(nd), repr(ndt)),
                                    ("nfmt", R.fmt_aw(nd, f), ndt.strftime(f))):
                if got != want:
                    bad.append((name, got, want))
        self.assertEqual(bad[:5], [])

    def test_arithmetic_and_comparison(self):
        import datetime as D
        R = self.R
        rng = random.Random(912)
        bad = []
        e = self.outcome
        unit = D.timedelta(microseconds=1)
        for _ in range(5000):
            a, da, ca = self.pair(rng)
            b, db, cb = self.pair(rng)
            n, dn, _ = self.pair(rng, True)
            td = D.timedelta(days=rng.randint(-3000, 3000), seconds=rng.randint(-10 ** 5, 10 ** 5), microseconds=rng.randint(-10 ** 6, 10 ** 6))
            rtd = R.from_k(2, (td.days * 86400 + td.seconds) * 1000000 + td.microseconds)
            checks = [
                ("sub", e(lambda: R.sub_aw(a, b).k), e(lambda: (da - db) // unit)),
                ("add", e(lambda: self.aview(R.add_aw(a, rtd))), e(lambda: self.pyaview(da + td, ca))),
                ("sub td", e(lambda: self.aview(R.sub_aw(a, rtd))), e(lambda: self.pyaview(da - td, ca))),
                ("td + a", e(lambda: self.aview(R.add_aw(rtd, a))), e(lambda: self.pyaview(td + da, ca))),
                ("lt", e(lambda: R.cmp_lt(a, b)), e(lambda: da < db)),
                ("le", e(lambda: R.cmp_le(a, b)), e(lambda: da <= db)),
                ("gt", e(lambda: R.cmp_gt(a, b)), e(lambda: da > db)),
                ("ge", e(lambda: R.cmp_ge(a, b)), e(lambda: da >= db)),
                ("eq", e(lambda: R.cmp_eq(a, b)), e(lambda: da == db)),
                ("ne", e(lambda: R.cmp_ne(a, b)), e(lambda: da != db)),
                ("mixed eq", e(lambda: R.cmp_eq(a, n)), e(lambda: da == dn)),
                ("max", R.ukey(R.pick_max_aw(a, b)), R.ukey(b) if db > da else R.ukey(a)),
                ("min", R.ukey(R.pick_min_aw(a, b)), R.ukey(b) if db < da else R.ukey(a)),
            ]
            for name, got, want in checks:
                if got != want and got[:1] != ("limit",) and not (got[0] == "OverflowError" and want[0] == "OverflowError"):
                    bad.append((name, got, want))
            # naive and aware do not mix (CPython: TypeError; here a RuntimeError with its text)
            for name, call, real in (("mixed lt", lambda: R.cmp_lt(a, n), lambda: da < dn),
                                     ("mixed sub", lambda: R.sub_aw(a, n), lambda: da - dn)):
                want = e(real)
                try:
                    call()
                    got = ("ok",)
                except RuntimeError as exc:
                    got = ("RuntimeError", str(exc))
                if want[0] != "TypeError" or got != ("RuntimeError", "TypeError: " + want[1]):
                    bad.append((name, got, want))
        self.assertEqual(bad[:5], [])

    def test_tz_make(self):
        import datetime as D
        R = self.R
        rng = random.Random(913)
        bad = []
        for _ in range(2000):
            secs = rng.choice([0, 1, -1, 3600, 86399, 86400, -86400, -86399, rng.randint(-90000, 90000)])
            name = rng.choice([None, "", "N", "JST"])
            td = D.timedelta(seconds=secs)
            got = self.outcome(lambda: (lambda z: (z.off, R.tz_name(z), R.tz_rep(z)))(
                R.tz_make(R.from_k(2, secs * 1000000), name or "", 0 if name is None else 1)))
            want = self.outcome(lambda: (lambda z: (int(z.utcoffset(None).total_seconds()), z.tzname(None), repr(z)))(
                D.timezone(td, name) if name is not None else D.timezone(td)))
            if got != want:
                bad.append((secs, name, got, want))
        self.assertEqual(bad[:5], [])

    def test_clock_and_conversion(self):
        import datetime as D
        R = self.R
        rng = random.Random(914)
        bad = []
        for zone in ZONES:
            self.zone(zone)
            for _ in range(250):
                ns = rng.randint(0, 4 * 10 ** 18) if rng.random() < 0.5 else rng.randint(1700000000, 1900000000) * 10 ** 9 + rng.randint(0, 10 ** 9)
                self.state["ns"] = ns
                off = rng.choice([0, 3600, -18000, 19800, 32400, rng.randint(-86399, 86399)])
                tz = D.timezone(D.timedelta(seconds=off))
                z = R.tz_make(R.from_k(2, off * 1000000), "", 0)
                secs, us = divmod(ns // 1000, 10 ** 6)
                t = rng.choice([0.0, 1.5, -1.25, 1700000000.123456, rng.uniform(-3e9, 5e9), float(rng.randint(-10 ** 9, 4 * 10 ** 9))])
                nd, ndt, _ = self.pair(rng, True)
                local = self.outcome(lambda: ndt.astimezone())
                for name, got, want in (
                        ("now_tz", self.outcome(lambda: self.aview(R.now_tz(z))),
                         self.outcome(lambda: self.pyaview(D.datetime.fromtimestamp(secs, tz).replace(microsecond=us), 1))),
                        ("fromts_tz", self.outcome(lambda: self.aview(R.fromts_tz(t, z))),
                         self.outcome(lambda: self.pyaview(D.datetime.fromtimestamp(t, tz), 1))),
                        ("astimezone naive", self.outcome(lambda: self.aview(R.astimezone_to(nd, z))),
                         self.outcome(lambda: self.pyaview(ndt.astimezone(tz), 1))),
                        ("astimezone()", self.outcome(lambda: (lambda x: (self.aview(x), R.tzname_aw(x)))(R.astimezone_local(nd))),
                         ("ok", (self.pyaview(local[1], 2), local[1].tzname())) if local[0] == "ok" else local)):
                    if got != want and got[:1] != ("limit",):
                        bad.append((zone, name, got, want))
        self.assertEqual(bad[:5], [])

    def test_fromisoformat_with_offsets(self):
        import datetime as D
        R = self.R
        rng = random.Random(915)
        bad = []
        offs = ["Z", "+00:00", "-00:00", "+05:30", "-03:30", "+23:59", "-23:59:59", "+01", "+0100", "+010203", "+24:00",
                "+99:00", "+05:30:15.5", "+1", "-", "+05:", "z", "+05:30x", " +05:30", "+05:30 ", ""]
        for _ in range(3000):
            d = D.datetime(rng.randint(1, 9999), rng.randint(1, 12), rng.randint(1, 28), rng.randint(0, 23), rng.randint(0, 59),
                           rng.randint(0, 59), rng.choice([0, 5, 123456]))
            sep = rng.choice(["T", " ", "t", "_"])
            text = d.isoformat(sep) + rng.choice(offs)
            got = self.outcome(lambda: (lambda x: (self.aview(x), R.tz_rep(R.aw_tz(x)) if x.aware else ""))(R.from_iso_datetime_aw(text)))

            def want_fn():
                x = D.datetime.fromisoformat(text)
                return (self.pyaview(x, 0 if x.tzinfo is None else 1), repr(x.tzinfo) if x.tzinfo is not None else "")
            want = self.outcome(want_fn)
            if got != want and got[:1] != ("limit",):
                bad.append((text, got, want))
        self.assertEqual(bad[:5], [])


if __name__ == "__main__":
    unittest.main()

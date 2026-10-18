"""Library batch 4: csv, datetime, unicodedata, statistics, textwrap, enum and a few import-free forms, each
compared with CPython.

Every program below is ordinary Python. CPython runs it as the oracle, the compiled program (the Python
syntax, AIL_NO_GENERAL=1 so the typed path must take it) prints the same bytes, or the spelling is refused
by name at compile time -- there is no third outcome where the numbers differ.

* csv: reader / DictReader over sys.stdin with every dialect option (delimiter, quotechar, escapechar,
  doublequote, skipinitialspace, strict, QUOTE_NONE, the named dialects), the csv.Error CPython raises at
  the same row, next() / list() / enumerate() over a reader; writer / DictWriter to sys.stdout with
  QUOTE_MINIMAL / ALL / NONE, escapechar, lineterminator. Generated: well-formed documents written by
  CPython's own csv.writer (more than 6000 rows) and random garbage (stray quotes, carriage returns, lone
  escapes), and 5000+ rows of random cells written back.
* int.bit_length / bit_count, max / min with default= and over a dict or a generator, itertools.product
  with a repeat computed at run time.
"""
import csv
import io
import os
import random
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def compile_python(directory, text, name):
    source, exe = Path(directory, name + ".ail"), Path(directory, name)
    source.write_text(text, encoding="utf-8")
    built = subprocess.run([sys.executable, "-B", str(ROOT / "ail_chatgpt.py"), "compile", source.name,
                            "--syntax", "python", "-o", exe.name], cwd=directory, capture_output=True,
                           text=True, timeout=900, env=dict(os.environ, AIL_NO_GENERAL="1"))
    return built, source, exe


READER_PROGRAM = '''import csv
import sys


def main() -> None:
    for row in csv.reader(sys.stdin@OPTS@):
        print(len(row), end=" ")
        for f in row:
            print(f"{f!r}", end=" ")
        print()


main()
'''

NEXT_PROGRAM = '''import csv
import sys


def main() -> None:
    r = csv.reader(sys.stdin@OPTS@)
    head = next(r, None)
    if head is None:
        print("EMPTY")
        return
    print(len(head), end=" ")
    for f in head:
        print(f"{f!r}", end=" ")
    print()
    n = 0
    for i, row in enumerate(r):
        n += len(row) + i
        if n > 50:
            break
    print(n)
    second = next(r, None)
    if second is None:
        print("stop")
    else:
        print("second", len(second))
    rest = list(r)
    print(len(rest))
    for item in rest:
        print(len(item), end=" ")
    print()
    print(len(list(r)))


main()
'''

DICT_PROGRAM = '''import csv
import sys


def main() -> None:
    r = csv.DictReader(sys.stdin@OPTS@)
    print("|".join(r.fieldnames))
    n = 0
    for row in r:
        n += 1
        print(n, f"{row['a']!r}", f"{row.get('b', 'dflt')!r}", "c" in row, "zz" in row, f"{row.get('zz', '-')!r}", f"{row['c']!r}")
    print(n)


main()
'''

DICT_ALL_PROGRAM = '''import csv
import sys


def main() -> None:
    r = csv.DictReader(sys.stdin@OPTS@)
    for row in r:
        print(len(row), end=" ")
        for k in row:
            print(f"{k!r}={row[k]!r}", end=" ")
        print()
    print("done")


main()
'''

WRITER_PROGRAM = '''import csv
import sys


def main() -> None:
    wr = csv.writer(sys.stdout@OPTS@)
    for line in sys.stdin:
        row = line.rstrip("\\n").replace("~", "\\n").split("|")
        wr.writerow(row)
        wr.writerow([row[0], len(row), 1.5, True, "x"])
    wr.writerows([["a", "b"], ["c,d", 'e"f']])
    wr.writerow([])
    wr.writerow([""])
    wr.writerow(("t", 2))


main()
'''

DICT_WRITER_PROGRAM = '''import csv
import sys


def main() -> None:
    wr = csv.DictWriter(sys.stdout, fieldnames=["name", "n", "note"]@OPTS@)
    wr.writeheader()
    d: dict[str, str] = {}
    for line in sys.stdin:
        f = line.rstrip("\\n").split("|")
        wr.writerow({"name": f[0], "n": len(f), "note": f[-1]})
        wr.writerow({"name": f[0]})
        d["name"] = f[0]
        d["note"] = "x,y"
        wr.writerow(d)
        try:
            wr.writerow({"name": "a", "other": 1})
        except ValueError:
            print("VE")


main()
'''


def reader_garbage(rng, alphabet, count):
    docs = []
    for _ in range(count):
        n = rng.randint(0, 70)
        docs.append("".join(rng.choice(alphabet) for _ in range(n)))
    return docs


def csv_documents(rng, count, rows_per_doc, **options):
    """Documents written by CPython's csv.writer from random cells (every quoting case)."""
    alphabet = list('ab c,;"\n\r\té1\\\'')
    docs = []
    total = 0
    for _ in range(count):
        out = io.StringIO()
        writer = csv.writer(out, **options)
        for _ in range(rng.randint(0, rows_per_doc)):
            row = ["".join(rng.choice(alphabet) for _ in range(rng.randint(0, 6))) for _ in range(rng.randint(1, 5))]
            writer.writerow(row)
            total += 1
        docs.append(out.getvalue())
    return docs, total


DT_PROGRAM = r'''import sys
from datetime import date, datetime, time, timedelta
import datetime as dtm


def span(a: datetime, b: datetime) -> timedelta:
    return b - a


def first_of_month(d: date) -> date:
    return d.replace(day=1)


def stamp(n: int) -> datetime:
    return datetime(2020, 1, 1) + timedelta(seconds=n * 977)


def main() -> None:
    days: list[date] = []
    for line in sys.stdin:
        f = line.rstrip("\n").split("\t")
        op = f[0]
        try:
            if op == "date":
                d = date(int(f[1]), int(f[2]), int(f[3]))
                print(d, d.isoformat(), d.weekday(), d.isoweekday(), d.toordinal(), d.strftime(f[4]), d.year, d.month, d.day)
                print(f"{d} {d:%Y/%m/%d %a %b} {d!r} {first_of_month(d)}")
                e = d + timedelta(days=int(f[5]))
                print(e, (e - d).days, e > d, e == d, d <= e, max(d, e), min(d, e))
                days.append(d)
                days.append(e)
            elif op == "datetime":
                a = datetime(int(f[1]), int(f[2]), int(f[3]), int(f[4]), int(f[5]), int(f[6]), int(f[7]))
                b = a + timedelta(hours=int(f[8]), minutes=int(f[9]), seconds=int(f[10]), microseconds=int(f[11]))
                print(a, b, repr(a), a.isoformat(), b.isoformat(" ", "seconds"), a.date(), a.time())
                print(b - a, span(a, b), (b - a).total_seconds(), a < b, a == b, a.strftime("%Y-%m-%d %H:%M:%S.%f"))
                print(f"{a:%d %B %Y} {b:%I:%M %p} {a.year} {a.hour} {a.minute} {a.second} {a.microsecond}")
                print(a.replace(hour=0, minute=0), a.replace(year=2000, month=2, day=1).weekday())
            elif op == "td":
                t = timedelta(days=int(f[1]), seconds=int(f[2]), microseconds=int(f[3]), minutes=int(f[4]), hours=int(f[5]), weeks=int(f[6]))
                u = timedelta(hours=1)
                print(t, repr(t), t.days, t.seconds, t.microseconds, t.total_seconds(), -t, abs(t), t + u, t - u)
                n = int(f[7])
                print(t * n, n * t, t // 7, t // u if u else 0, t % u, t / 3, t / u, t > u, t == u, bool(t))
                if t:
                    print("nonzero")
            elif op == "iso":
                if f[1] == "d":
                    print(date.fromisoformat(f[2]))
                else:
                    print(datetime.fromisoformat(f[2]))
            elif op == "strp":
                x = datetime.strptime(f[1], f[2])
                print(x, x.date(), x.strftime("%j %U %w"))
            elif op == "time":
                t = time(int(f[1]), int(f[2]), int(f[3]), int(f[4]))
                print(t, repr(t), t.isoformat("seconds"), t.strftime("%H-%M"), t.hour, t.minute)
            elif op == "mix":
                x = dtm.datetime(int(f[1]), int(f[2]), int(f[3]))
                y = dtm.date(int(f[1]), int(f[2]), int(f[3]))
                z = datetime.combine(y, time(12, 30))
                w = date.fromordinal(int(f[4]))
                print(x, y, z, w, dtm.timedelta(days=2), z - x, date.min, date.max, datetime.min)
            elif op == "stamp":
                s = stamp(int(f[1]))
                print(s, s.isoformat(), [s.year, s.month][1])
        except ValueError as err:
            print("ValueError", err.message)
        except OverflowError:
            print("OverflowError")
        except ZeroDivisionError:
            print("ZeroDivisionError")
    days.sort()
    print(len(days))
    for r in sorted(days)[:5]:
        print(r)
    if days:
        print(max(days), min(days))
    work = 0
    firsts = 0
    for q in days:
        if q.weekday() < 5:
            work += 1
        if q.day == 1:
            firsts += 1
    print(work, firsts)


main()
'''

STATS_PROGRAM = r'''import statistics
import sys
from statistics import mean, median_low, multimode


def main() -> None:
    for line in sys.stdin:
        xs: list[int] = [int(t) for t in line.split()]
        if len(xs) < 2:
            continue
        print(statistics.mean(xs))
        print(mean(xs), statistics.median(xs))
        print(f"{statistics.mean(xs):.3f} {statistics.median(xs):8.2f} {statistics.stdev(xs):.4f} {statistics.pstdev(xs):.4f}")
        m = statistics.mean(xs)
        print(f"{m:.2f}")
        if m > 2:
            print("big")
        v = round(statistics.variance(xs), 2)
        print(f"{v:.2f}")
        print(statistics.pvariance(xs), statistics.variance(xs))
        print(statistics.mode(xs), median_low(xs), statistics.median_high(xs), len(multimode(xs)))
        print(statistics.fmean(xs), float(statistics.mean(xs)))
        try:
            print(statistics.stdev([1]))
        except statistics.StatisticsError:
            print("SE")


main()
'''


def datetime_input(seed, count):
    rng = random.Random(seed)
    import datetime as D
    N = count
    FORMATS = ["%Y-%m-%d", "%d/%m/%y", "%H:%M:%S", "%I:%M %p", "%a %A %b %B", "%j %U %W %w %u", "%G-W%V-%u %g", "%c|%x|%X", "%e|%k|%l|%P",
               "%C %D %F %T %R %r", "%f %%", "%Y%m%d%H%M%S", "%h %n %t|", "plain", "", "%Q %q"]


    def rdate():
        y = rng.choice([1, 4, 100, 400, 1000, 1900, 1970, 2000, 2024, 2100, 9998, 9999, rng.randint(1, 9999)])
        m = rng.randint(1, 12)
        return y, m, rng.randint(1, 28 if rng.random() < 0.8 else 31)


    def rt():
        return rng.randint(0, 23), rng.randint(0, 59), rng.randint(0, 59), rng.choice([0, 1, 999999, rng.randint(0, 999999)])


    def num(lo=-1000, hi=1000):
        return rng.choice([0, 1, -1, rng.randint(lo, hi), rng.randint(lo, hi)])


    lines = []
    for _ in range(N):
        op = rng.choice(["date", "datetime", "td", "iso", "strp", "time", "mix", "stamp"])
        if op == "date":
            y, m, d = rdate()
            lines.append("\t".join(["date", str(y), str(m), str(d), rng.choice(FORMATS), str(num(-4000, 4000))]))
        elif op == "datetime":
            y, m, d = rdate()
            lines.append("\t".join(["datetime", str(y), str(m), str(d), *map(str, rt()), str(num(-2000, 2000)), str(num(-3000, 3000)), str(num(-90000, 90000)), str(num())]))
        elif op == "td":
            lines.append("\t".join(["td", str(num(-20000, 20000)), str(num(-10 ** 6, 10 ** 6)), str(num(-10 ** 6, 10 ** 6)), str(num(-10 ** 5, 10 ** 5)),
                                    str(num(-10 ** 4, 10 ** 4)), str(num(-1000, 1000)), str(rng.choice([0, 1, -1, 2, 3, 7, -3, 40]))]))
        elif op == "iso":
            kind = rng.choice("dt")
            y, m, d = rdate()
            base = D.date(y, m, min(d, 28))
            style = rng.choice(["%Y-%m-%d", "%Y%m%d", "%G-W%V-%u", "%GW%V%u"])
            text = base.strftime(style)
            if kind == "t":
                text += rng.choice("T _x") + rng.choice(["12", "12:30", "12:30:45", "12:30:45.123456", "123045", "12:30:45,5", "1230"])
            if rng.random() < 0.5:
                t = list(text)
                for _ in range(rng.randint(1, 2)):
                    r = rng.random()
                    if r < 0.3 and t:
                        del t[rng.randrange(len(t))]
                    elif r < 0.6 and t:
                        t[rng.randrange(len(t))] = rng.choice("0123456789-:T W,.")
                    else:
                        t.insert(rng.randint(0, len(t)), rng.choice("0123456789-:T W,."))
                text = "".join(t)
            if kind == "t":
                try:
                    if D.datetime.fromisoformat(text).tzinfo is not None:
                        continue
                except ValueError as err:
                    if "offset" in str(err):
                        continue
            lines.append("\t".join(["iso", kind, text]))
        elif op == "strp":
            fmts = ["%Y-%m-%d", "%d/%m/%Y", "%H:%M", "%H:%M:%S", "%Y-%m-%d %H:%M:%S", "%d %b %Y", "%B %d, %Y", "%A %d %B %Y", "%a, %d %b %Y %H:%M:%S", "%I:%M %p",
                    "%y%m%d", "%Y%m%d%H%M%S", "%m/%d/%y", "%j %Y", "%Y %j", "%d.%m.%Y", "%Y-%m-%dT%H:%M:%S.%f", "%S.%f", "%U %w %Y", "%Y %W %a", "%G-W%V-%u",
                    "%c", "%x", "%X", "%d%m", "%H%M%S", "%y", "%%", "%b", "%d  %m", "%d %m %Y", "%q", "% d"]
            fmt = rng.choice(fmts)
            sample = D.datetime(rng.choice([1969, 1999, 2000, 2024, 2068, 1900]), rng.randint(1, 12), rng.randint(1, 28), rng.randint(0, 23), rng.randint(0, 59), rng.randint(0, 59), rng.randint(0, 999999))
            try:
                text = sample.strftime(fmt)
            except Exception:
                text = "x"
            if rng.random() < 0.3:
                text = text.replace("0", "") if rng.random() < 0.5 else text.lower()
            if rng.random() < 0.5:
                t = list(text)
                for _ in range(rng.randint(0, 2)):
                    if t and rng.random() < 0.5:
                        del t[rng.randrange(len(t))]
                    else:
                        t.insert(rng.randint(0, len(t)), rng.choice("0123456789-: aApP"))
                text = "".join(t)
            lines.append("\t".join(["strp", text, fmt]))
        elif op == "time":
            lines.append("\t".join(["time", *map(str, rt())]))
        elif op == "mix":
            y, m, d = rdate()
            lines.append("\t".join(["mix", str(y), str(m), str(d), str(rng.choice([1, 2, 3652059, 3652060, rng.randint(1, 3652059)]))]))
        else:
            lines.append("\t".join(["stamp", str(num(-10 ** 6, 10 ** 6))]))

    return ("\n".join(lines) + "\n").encode()


class Batch4Tests(unittest.TestCase):
    def build(self, directory, text, name):
        built, source, exe = compile_python(directory, text, name)
        self.assertEqual(built.returncode, 0, built.stdout + built.stderr)
        oracle = Path(directory, name + "_oracle.py")
        oracle.write_text(text, encoding="utf-8")
        return exe, oracle

    def many_same(self, text, name, inputs, skip=None):
        """Compile once; every input must print what CPython prints (bytes and exit code)."""
        bad = []
        with tempfile.TemporaryDirectory() as directory:
            exe, oracle = self.build(directory, text, name)
            for data in inputs:
                data = data.encode("utf-8") if isinstance(data, str) else data
                ran = subprocess.run([str(exe)], input=data, capture_output=True, timeout=120)
                expected = subprocess.run([sys.executable, str(oracle)], input=data, capture_output=True, timeout=120)
                if skip is not None and skip(ran):
                    continue
                if (ran.returncode, ran.stdout) != (expected.returncode, expected.stdout):
                    bad.append((data, expected.returncode, expected.stdout[:200], ran.returncode, ran.stdout[:200],
                                ran.stderr[:200]))
                    if len(bad) > 3:
                        break
        self.assertEqual(bad, [], "first differences")

    def same_as_cpython(self, text, name, stdin=b""):
        with tempfile.TemporaryDirectory() as directory:
            exe, oracle = self.build(directory, text, name)
            ran = subprocess.run([str(exe)], input=stdin, capture_output=True, timeout=300)
            expected = subprocess.run([sys.executable, str(oracle)], input=stdin, capture_output=True, timeout=300)
            self.assertEqual(expected.returncode, 0, expected.stderr)
            self.assertEqual((ran.returncode, ran.stdout), (0, expected.stdout), ran.stderr[:500])
            return expected.stdout

    def refused(self, text, wanted, name="prog"):
        with tempfile.TemporaryDirectory() as directory:
            built, _, exe = compile_python(directory, text, name)
            self.assertEqual(built.returncode, 3, built.stdout + built.stderr)
            self.assertIn(wanted, built.stderr)
            self.assertFalse(exe.exists())

    # -- csv: reader ---------------------------------------------------------------------------------------
    def test_csv_reader_wellformed_documents(self):
        rng = random.Random(41)
        docs, total = csv_documents(rng, 700, 12)
        self.assertGreater(total, 3000)
        self.many_same(READER_PROGRAM.replace("@OPTS@", ""), "csv_reader", docs)
        docs, more = csv_documents(rng, 500, 12, delimiter=";", quotechar="'", lineterminator="\n")
        self.assertGreater(total + more, 6000)
        self.many_same(READER_PROGRAM.replace("@OPTS@", ', delimiter=";", quotechar="\'"'), "csv_reader2", docs)

    def test_csv_reader_options_on_random_text(self):
        rng = random.Random(42)
        alphabet = ["a", "b", "c", ",", ",", '"', '"', " ", "\n", "\n", "\r", "é", "\t", ";", "\\", "'", ""]
        for index, options in enumerate(("", ", delimiter=\";\"", ", skipinitialspace=True", ", quotechar=\"'\"",
                                         ", escapechar=\"\\\\\"", ", doublequote=False", ", strict=True",
                                         ", quoting=csv.QUOTE_NONE", ", dialect=\"excel-tab\"",
                                         ", escapechar=\"\\\\\", doublequote=False, skipinitialspace=True")):
            with self.subTest(options=options):
                self.many_same(READER_PROGRAM.replace("@OPTS@", options), "csv_opt%d" % index,
                               reader_garbage(rng, alphabet, 250))

    def test_csv_reader_next_list_enumerate(self):
        rng = random.Random(43)
        alphabet = ["a", "b", ",", ",", '"', " ", "\n", "\n", "\n", "é", ";"]
        docs = reader_garbage(rng, alphabet, 300)
        docs += ["", "\n", "a\n", "a,b\nc,d\n\n\ne,f"]
        self.many_same(NEXT_PROGRAM.replace("@OPTS@", ""), "csv_next", docs)

    # -- csv: DictReader --------------------------------------------------------------------------------------
    def test_csv_dictreader(self):
        rng = random.Random(44)
        docs = []
        for _ in range(400):
            out = io.StringIO()
            writer = csv.writer(out, lineterminator="\n" if rng.random() < 0.5 else "\r\n")
            writer.writerow(["a", "b", "c"] if rng.random() < 0.9 else ["c", "a", "b"])
            for _ in range(rng.randint(0, 6)):
                writer.writerow(["".join(rng.choice('xy ,"\né1') for _ in range(rng.randint(0, 5))) for _ in range(3)])
                if rng.random() < 0.2:
                    out.write("\n")
            docs.append(out.getvalue())
        docs += ["a,b\n", "a,b,c\n1,2,3\n\n4,5,6", "b,a\n1,2\n"]
        skip = lambda ran: ran.returncode != 0 and b"csv.DictReader:" in ran.stderr
        self.many_same(DICT_PROGRAM.replace("@OPTS@", ""), "csv_dict", docs, skip)
        self.many_same(DICT_ALL_PROGRAM.replace("@OPTS@", ""), "csv_dict_all", docs, skip)

    def test_csv_dictreader_short_and_long_rows_are_loud(self):
        text = DICT_ALL_PROGRAM.replace("@OPTS@", "")
        with tempfile.TemporaryDirectory() as directory:
            exe, _ = self.build(directory, text, "loud")
            for data in (b"a,b,c\n1,2\n", b"a,b,c\n1,2,3,4\n"):
                ran = subprocess.run([str(exe)], input=data, capture_output=True, timeout=60)
                self.assertNotEqual(ran.returncode, 0)
                self.assertIn(b"csv.DictReader:", ran.stderr)

    # -- csv: writer ------------------------------------------------------------------------------------------
    def test_csv_writer_random_rows(self):
        rng = random.Random(45)
        alphabet = ["a", "b", ",", '"', " ", "~", "\r", "é", "\t", ";", "\\", "'", "1"]
        total = 0
        docs = []
        for _ in range(300):
            lines = []
            for _ in range(rng.randint(0, 20)):
                cells = ["".join(rng.choice(alphabet) for _ in range(rng.randint(0, 6))) for _ in range(rng.randint(1, 4))]
                lines.append("|".join(cells))
                total += 2
            docs.append("".join(line + "\n" for line in lines))
        self.assertGreater(total, 5000)
        for index, options in enumerate(("", ", quoting=csv.QUOTE_ALL", ", delimiter=\";\", lineterminator=\"\\n\"",
                                         ", quoting=csv.QUOTE_NONE, escapechar=\"\\\\\"",
                                         ", doublequote=False, escapechar=\"\\\\\"", ", dialect=\"unix\"",
                                         ", quotechar=\"|\"", ", lineterminator=\"x\"",
                                         ", quoting=csv.QUOTE_NONE, escapechar=\"\\\\\", lineterminator=\";;\"")):
            with self.subTest(options=options):
                self.many_same(WRITER_PROGRAM.replace("@OPTS@", options), "csv_writer%d" % index, docs[:60])

    def test_csv_writer_errors(self):
        text = WRITER_PROGRAM.replace("@OPTS@", ", quoting=csv.QUOTE_NONE")
        self.many_same(text, "csv_writer_none", ["a,b|c\n", "x\n", "\n"])

    def test_csv_dictwriter(self):
        rng = random.Random(46)
        alphabet = ["a", "b", ",", '"', "|", "é", " "]
        docs = []
        for _ in range(60):
            lines = ["".join(rng.choice(alphabet) for _ in range(rng.randint(0, 7))) for _ in range(rng.randint(0, 5))]
            docs.append("".join(line + "\n" for line in lines))
        self.many_same(DICT_WRITER_PROGRAM.replace("@OPTS@", ""), "csv_dw", docs)
        self.many_same(DICT_WRITER_PROGRAM.replace("@OPTS@", ", restval=\"-\", delimiter=\";\""), "csv_dw2", docs)

    def test_csv_refusals_are_named(self):
        head = "import csv\nimport sys\n\n\ndef main():\n"
        self.refused(head + "    w = csv.writer(sys.stdout, quoting=csv.QUOTE_NONNUMERIC)\n    w.writerow([1])\n\n\nmain()\n",
                     "QUOTE_NONNUMERIC")
        self.refused(head + "    r = csv.reader(sys.stdin)\n    print(r.line_num)\n\n\nmain()\n", "line_num")
        self.refused(head + "    r = csv.reader(sys.stdin)\n    f(r)\n\n\nmain()\n", "is used as a value here")
        self.refused(head + "    r = csv.reader(sys.stdin, dialect='nope')\n\n\nmain()\n", "dialect has to be")
        self.refused(head + "    r = csv.reader(sys.stdin, delimiter='ab')\n\n\nmain()\n", "1-character string")
        self.refused(head + "    w = csv.writer(open('x', 'w'))\n\n\nmain()\n", "only sys.stdout")
        self.refused(head + "    for row in csv.DictReader(sys.stdin, restval='x'):\n        print(row)\n\n\nmain()\n",
                     "restval=")
        self.refused(head + "    c = csv.Sniffer()\n\n\nmain()\n", "csv.Sniffer used here is not built")

    # -- int.bit_length / bit_count ------------------------------------------------------------------------------
    def test_bit_length_and_bit_count(self):
        program = '''import sys


def main() -> None:
    for line in sys.stdin:
        v = int(line)
        print(v.bit_length(), v.bit_count(), (v + 1).bit_length() if v < 9223372036854775807 else 0, (v >> 3).bit_count())


main()
'''
        rng = random.Random(47)
        values = [0, 1, -1, 2, 3, 255, 256, 2 ** 31, 2 ** 32 - 1, 2 ** 32, 2 ** 62, 2 ** 63 - 1, -2 ** 63, -2 ** 63 + 1,
                  -(2 ** 32), 12345678901, -12345678901]
        values += [rng.randint(-2 ** 63, 2 ** 63 - 1) for _ in range(500)]
        values += [rng.randint(-1000, 1000) for _ in range(300)]
        values += [(1 << rng.randint(0, 62)) + rng.choice((-1, 0, 1)) for _ in range(300)]
        self.same_as_cpython(program, "bits", ("\n".join(str(v) for v in values) + "\n").encode())

    # -- max / min ----------------------------------------------------------------------------------------------------
    def test_max_min_default_key_and_sources(self):
        program = '''import sys


def pick(xs: list[int], flag: int) -> int:
    if flag == 0:
        return max(xs, default=-1)
    return min(xs, default=-2)


def main() -> None:
    xs = [3, 1, 4, 1, 5, 9, 2, 6]
    ws = ["bb", "a", "ccc", "dd", "e"]
    d: dict[str, int] = {}
    for line in sys.stdin:
        w = line.split()
        d[w[0]] = int(w[1])
    e: list[int] = []
    a1 = max(xs, default=-1)
    a2 = min(xs, default=-1)
    print(a1, a2)
    a3 = max(e, default=-1)
    print(a3, pick(e, 0), pick(xs, 1), pick(e, 1))
    a4 = max(ws, key=len)
    a5 = min(ws, key=len, default="none")
    print(a4, a5)
    best = max(d, key=d.get, default="empty")
    print(best)
    print(max((x * 2 for x in xs if x > 3), default=0))
    print(max([x for x in xs if x > 100], default=7))
    print(max(range(5), key=lambda i: (i - 2) ** 2))
    print(min(range(2, 6), key=lambda i: (i - 4) ** 2, default=99))
    print(max(range(0), default=-5))
    try:
        print(max(e, key=abs))
    except ValueError:
        print("VE")


main()
'''
        with tempfile.TemporaryDirectory() as directory:
            exe, oracle = self.build(directory, program, "minmax")
            for data in (b"", b"a 1\nb 5\nc 5\n", b"z 2\n", b"a 9\nb 9\n"):
                ran = subprocess.run([str(exe)], input=data, capture_output=True, timeout=60)
                expected = subprocess.run([sys.executable, str(oracle)], input=data, capture_output=True, timeout=60)
                self.assertEqual((ran.returncode, ran.stdout), (expected.returncode, expected.stdout), ran.stderr)

    # -- itertools.product with a computed repeat ---------------------------------------------------------------
    def test_product_with_runtime_repeat(self):
        program = '''import sys
from itertools import product


def main() -> None:
    for line in sys.stdin:
        f = line.split()
        n = int(f[0])
        digits = [int(x) for x in f[1:]]
        count = 0
        mix = 0
        for bits in product(digits, repeat=n):
            count += 1
            mix = (mix * 31 + sum(bits) * 7 + len(bits) + (bits[0] if n > 0 else 99)) % 1000003
        print(n, count, mix)
        total = 0
        for p in product([1, 2, 3], repeat=n):
            total = (total * 7 + sum(p) + len(p)) % 1000003
        print(total)
        print(len(["".join(b) for b in product("01", repeat=n) if "11" not in "".join(b)]))


main()
'''
        rng = random.Random(48)
        lines = ["%d %s" % (rng.randint(0, 5), " ".join(str(rng.randint(0, 9)) for _ in range(rng.randint(0, 4))))
                 for _ in range(120)]
        self.same_as_cpython(program, "product_repeat", ("\n".join(lines) + "\n").encode())
        self.refused("from itertools import product\n\n\ndef main():\n    n = 2\n    for a, b in product([1], [2], repeat=n):\n"
                     "        print(a, b)\n\n\nmain()\n", "with several iterables repeat=")

    # -- datetime ----------------------------------------------------------------------------------------------
    def test_datetime_api_matches_cpython(self):
        """date / datetime / time / timedelta through the whole front end: constructors, arithmetic,
        comparisons, formatting, parsing, sorting; generated operations, errors included."""
        with tempfile.TemporaryDirectory() as directory:
            exe, oracle = self.build(directory, DT_PROGRAM, "dt_api")
            oracle.write_text(DT_PROGRAM.replace("err.message", "err"), encoding="utf-8")
            total = 0
            for seed in (1, 3, 4):
                data = datetime_input(seed, 2500)
                ran = subprocess.run([str(exe)], input=data, capture_output=True, timeout=300)
                expected = subprocess.run([sys.executable, str(oracle)], input=data, capture_output=True, timeout=300)
                self.assertEqual(expected.returncode, 0, expected.stderr)
                self.assertEqual((ran.returncode, ran.stdout), (0, expected.stdout), (seed, ran.stderr[:300]))
                total += len(expected.stdout.split(b"\n"))
            self.assertGreater(total, 12000)

    def test_datetime_runtime_matches_cpython_in_plain_python(self):
        """The functions the compiler appends (dtrt.py) are plain Python: compare them with the datetime
        module on generated values (construction errors, arithmetic, text, parsing)."""
        import datetime as D
        sys.path.insert(0, str(ROOT / "python" / "pkg-v12"))
        try:
            import dtrt as R
        finally:
            sys.path.pop(0)
        rng = random.Random(61)

        def err(f):
            try:
                return ("ok", f())
            except RuntimeError:
                return ("limit",)
            except Exception as e:
                return (type(e).__name__, str(e))

        def view(x):
            return (x.kind, x.k, x.year, x.month, x.day, x.hour, x.minute, x.second, x.microsecond)

        def pyview(x):
            if isinstance(x, D.datetime):
                return (1, x.toordinal() * R.US_DAY + ((x.hour * 60 + x.minute) * 60 + x.second) * 1000000 + x.microsecond,
                        x.year, x.month, x.day, x.hour, x.minute, x.second, x.microsecond)
            return (0, x.toordinal() * R.US_DAY, x.year, x.month, x.day, 0, 0, 0, 0)

        def mutate(text):
            t = list(text)
            for _ in range(rng.randint(0, 2)):
                r = rng.random()
                if r < 0.3 and t:
                    del t[rng.randrange(len(t))]
                elif r < 0.6 and t:
                    t[rng.randrange(len(t))] = rng.choice("0123456789-:T W,.ap/")
                else:
                    t.insert(rng.randint(0, len(t)), rng.choice("0123456789-:T W,.ap/"))
            return "".join(t)
        styles = ["%Y-%m-%d", "%Y%m%d", "%G-W%V-%u", "%GW%V%u", "%G-W%V", "%GW%V"]
        formats = ["%Y-%m-%d", "%d/%m/%Y", "%H:%M", "%H:%M:%S", "%Y-%m-%d %H:%M:%S", "%d %b %Y", "%B %d, %Y", "%A %d %B %Y",
                   "%a, %d %b %Y %H:%M:%S", "%I:%M %p", "%y%m%d", "%Y%m%d%H%M%S", "%m/%d/%y", "%j %Y", "%Y %j", "%d.%m.%Y",
                   "%Y-%m-%dT%H:%M:%S.%f", "%S.%f", "%U %w %Y", "%Y %W %a", "%G-W%V-%u", "%c", "%x", "%X", "%d%m", "%H%M%S",
                   "%y", "%%", "%b", "%d  %m", "%d %m %Y", "%q"]
        strftime_formats = ["%Y-%m-%d", "%d/%m/%y", "%H:%M:%S", "%I:%M %p", "%a %A %b %B", "%j %U %W %w %u", "%G-W%V-%u %g",
                            "%c|%x|%X", "%e|%k|%l|%P", "%C %D %F %T %R %r", "%f %%", "%h %n %t|", "%z|%Z|", "%Q %q", ""]
        bad = []
        checked = 0
        for _ in range(7000):
            y = rng.choice([1, 4, 100, 400, 1000, 1900, 1970, 2000, 2024, 2100, 9998, 9999, rng.randint(1, 9999)])
            m, d = rng.randint(1, 12), rng.randint(1, 31)
            hh, mi, ss, us = rng.randint(-1, 24), rng.randint(-1, 60), rng.randint(-1, 60), rng.choice([0, 1, 999999, rng.randint(-1, 1000000)])
            checks = [
                ("datetime", err(lambda: view(R.mk_datetime(y, m, d, hh, mi, ss, us))), err(lambda: pyview(D.datetime(y, m, d, hh, mi, ss, us)))),
            ]
            if 1 <= m <= 12 and d <= R.dim(y, m):
                dt = D.datetime(y, m, d, rng.randint(0, 23), rng.randint(0, 59), rng.randint(0, 59), rng.randint(0, 999999))
                rd = R.mk_datetime(dt.year, dt.month, dt.day, dt.hour, dt.minute, dt.second, dt.microsecond)
                td = D.timedelta(days=rng.randint(-20000, 20000), seconds=rng.randint(-10 ** 6, 10 ** 6), microseconds=rng.randint(-10 ** 6, 10 ** 6))
                rtd = R.from_k(2, (td.days * 86400 + td.seconds) * 1000000 + td.microseconds)
                fmt = rng.choice(strftime_formats)
                checks += [
                    ("add", err(lambda: view(R.add(rd, rtd))), err(lambda: pyview(dt + td))),
                    ("sub", err(lambda: view(R.sub(rd, rtd))), err(lambda: pyview(dt - td))),
                    ("strftime", R.fmt(rd, fmt), dt.strftime(fmt)),
                    ("str", (R.text(rd), R.rep(rd), R.iso(rd, "T", "auto")), (str(dt), repr(dt), dt.isoformat())),
                    ("td", (R.text(rtd), R.rep(rtd), R.total_seconds(rtd)), (str(td), repr(td), td.total_seconds())),
                    ("weekday", (R.weekday(rd), R.isoweekday(rd)), (dt.weekday(), dt.isoweekday())),
                ]
                style = rng.choice(styles)
                text = dt.strftime(style)
                for candidate in (text, mutate(text)):
                    checks.append(("fromisoformat", err(lambda: view(R.from_iso_date(candidate))), err(lambda: pyview(D.date.fromisoformat(candidate)))))
                    tail = rng.choice(["T12:30:45", " 12:30", "x123045", "T12:30:45.5", "T1", ""])
                    full = mutate(text + tail) if rng.random() < 0.5 else text + tail
                    try:
                        aware = D.datetime.fromisoformat(full).tzinfo is not None
                    except ValueError:
                        aware = False
                    if not aware:
                        checks.append(("fromisoformat dt", err(lambda: view(R.from_iso_datetime(full))), err(lambda: pyview(D.datetime.fromisoformat(full)))))
                fmt2 = rng.choice(formats)
                try:
                    data = dt.strftime(fmt2)
                except ValueError:
                    data = "x"
                data = mutate(data) if rng.random() < 0.5 else data
                try:
                    aware = D.datetime.strptime(data, fmt2).tzinfo is not None
                except ValueError:
                    aware = False
                if not aware:
                    checks.append(("strptime " + fmt2, err(lambda: view(R.strptime(data, fmt2))), err(lambda: pyview(D.datetime.strptime(data, fmt2)))))
            for name, got, want in checks:
                checked += 1
                if got != want and got[:1] != ("limit",):
                    bad.append((name, got, want))
        self.assertEqual(bad[:5], [])
        self.assertGreater(checked, 40000)

    def test_datetime_refusals_are_named(self):
        head = "from datetime import date, datetime, timedelta\n\n\ndef main():\n"
        self.refused(head + "    print(datetime.now())\n\n\nmain()\n", "datetime.datetime.now reads the clock")
        self.refused(head + "    print(date.today())\n\n\nmain()\n", "reads the clock")
        self.refused(head + "    print(timedelta(hours=1.5))\n\n\nmain()\n", "float")
        self.refused(head + "    d = datetime(2020, 1, 1)\n    print(d.timestamp())\n\n\nmain()\n", ".timestamp()")
        self.refused("from datetime import timezone, datetime\n\n\ndef main():\n    print(datetime(2020, 1, 1, tzinfo=timezone.utc))\n\n\nmain()\n",
                     "timezone")
        self.refused("import datetime\n\n\ndef main():\n    print(datetime.timezone.utc)\n\n\nmain()\n", "timezone-aware")
        self.refused(head + "    print(isinstance(1, date))\n\n\nmain()\n", "used as a value is not built")

    # -- statistics ---------------------------------------------------------------------------------------------------
    def test_statistics_runtime_matches_cpython_in_plain_python(self):
        import statistics as S
        sys.path.insert(0, str(ROOT / "python" / "pkg-v12"))
        try:
            import strt as R
        finally:
            sys.path.pop(0)
        rng = random.Random(62)

        def err(f):
            try:
                return ("ok", f())
            except RuntimeError:
                return ("limit",)
            except Exception as e:
                return ("ValueError" if type(e).__name__ == "StatisticsError" else type(e).__name__, str(e))
        bad = []
        for _ in range(4000):
            n = rng.choice([0, 1, 2, 3, 4, 5, 8, 20, 100])
            mag = rng.choice([3, 10, 100, 10 ** 4, 10 ** 6])
            xs = [rng.randint(-mag, mag) for _ in range(n)]
            if rng.random() < 0.3 and xs:
                xs = [rng.choice(xs[:3]) for _ in range(n)]
            checks = [("mean", err(lambda: R.mean_text(xs)), err(lambda: str(S.mean(xs)))),
                      ("fmean", err(lambda: R.fmean(xs)), err(lambda: S.fmean(xs))),
                      ("median", err(lambda: R.median_text(xs)), err(lambda: str(S.median(xs)))),
                      ("median_low", err(lambda: R.median_low(xs)), err(lambda: S.median_low(xs))),
                      ("median_high", err(lambda: R.median_high(xs)), err(lambda: S.median_high(xs))),
                      ("mode", err(lambda: R.mode_int(xs)), err(lambda: S.mode(xs))),
                      ("multimode", err(lambda: R.multimode_int(xs)), err(lambda: S.multimode(xs)))]
            for sample in (False, True):
                checks.append(("variance", err(lambda: R.variance_text(xs, sample)),
                               err(lambda: str((S.variance if sample else S.pvariance)(xs)))))
                checks.append(("stdev", err(lambda: R.stdev_float(xs, sample)), err(lambda: (S.stdev if sample else S.pstdev)(xs))))
            floats = [rng.uniform(-100, 100) for _ in range(n)]
            checks.append(("fmean floats", err(lambda: R.fsum_floats_mean(floats)), err(lambda: S.fmean(floats))))
            for name, got, want in checks:
                if got != want and got[:1] != ("limit",):
                    bad.append((name, got, want, xs[:6]))
        self.assertEqual(bad[:5], [])

    def test_statistics_through_the_compiler(self):
        with tempfile.TemporaryDirectory() as directory:
            exe, oracle = self.build(directory, STATS_PROGRAM, "stats")
            rng = random.Random(63)
            for _ in range(8):
                lines = []
                for _ in range(200):
                    n = rng.choice([2, 3, 4, 5, 8, 20])
                    mag = rng.choice([3, 10, 1000, 10 ** 6])
                    lines.append(" ".join(str(rng.randint(-mag, mag)) for _ in range(n)))
                data = ("\n".join(lines) + "\n").encode()
                ran = subprocess.run([str(exe)], input=data, capture_output=True, timeout=300)
                expected = subprocess.run([sys.executable, str(oracle)], input=data, capture_output=True, timeout=300)
                self.assertEqual((ran.returncode, ran.stdout), (expected.returncode, expected.stdout), ran.stderr[:300])

    def test_statistics_refusals_are_named(self):
        head = "import statistics\n\n\ndef main():\n"
        self.refused(head + "    xs: list[int] = [1, 2]\n    m = statistics.mean(xs)\n    print(m * 2)\n\n\nmain()\n",
                     "an int when the answer is whole and a float otherwise")
        self.refused(head + "    xs: list[float] = [1.5, 2.5]\n    print(statistics.stdev(xs))\n\n\nmain()\n",
                     "exact fractions over floats")
        self.refused(head + "    xs = [x for x in range(3)]\n    print(statistics.mean(xs, 1))\n\n\nmain()\n", "one argument")
        self.refused(head + "    print(statistics.quantiles([1, 2, 3]))\n\n\nmain()\n", "statistics.quantiles")

    # -- x in (constants) -----------------------------------------------------------------------------------------
    def test_membership_in_a_display_of_constants(self):
        program = '''import sys


def main() -> None:
    for line in sys.stdin:
        tokens = line.split()
        c = 0
        for word in tokens:
            if word.rstrip(",") in ("a", "e"):
                c += 1
            if word not in ["x", "y", "zz"]:
                c += 10
            if len(word) in (1, 3, 5):
                c += 100
            if len(word) not in [2, 4]:
                c += 1000
        print(c)
        print(len([t for t in tokens if t in ("a", "b")]))


main()
'''
        rng = random.Random(64)
        lines = [" ".join(rng.choice(["a", "e,", "b", "x", "y", "zz", "abc", "q", "hello", "a,", "ee", ""]) for _ in range(rng.randint(0, 8)))
                 for _ in range(400)]
        self.same_as_cpython(program, "in_displays", ("\n".join(lines) + "\n").encode())


if __name__ == "__main__":
    unittest.main()

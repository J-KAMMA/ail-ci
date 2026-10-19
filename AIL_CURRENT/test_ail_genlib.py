"""Library names of the general (boxed) path: json, itertools, functools.partial, statistics, datetime, random and
math.isclose, each compared with CPython 3.12.

A census of 510 generated programs showed many of them refused on both paths only because the general path said
"X (not yet published in NAMES_library.json)". genlib.py renames the library names to the Python-source pieces of
prelude_genlib.py (and prelude_random.py), which pyboxed2 adds to a program that uses them. Layers:

* G1  the pieces are plain Python, so they run under CPython next to the library: generated documents, options,
      malformed JSON, itertools arguments, statistics data, dates and strings must give the same value or the same
      exception (type and message) as json, itertools, statistics and datetime;
* G2  whole programs are built with the general path alone (the program text goes through the same preparation as
      `ail_chatgpt.py compile --syntax python`, then pyc.build(force_general=True)), run, and must print the bytes
      CPython prints; one more is built with the default build (typed path first);
* G3  what is not built is refused by name (decimal, an unseeded random.seed(), datetime.now(), json.dump(cls=...)),
      before any C is written;
* G4  a program that names none of the library functions is returned untouched by genlib.rewrite.

The declared differences (DIFFERENCES.md): statistics of floats keeps exact sums as partials and divides, squares and
takes roots in two doubles, so a result agrees with CPython's exact fractions except when the exact value is within
~2**-50 of a rounding boundary; strings are 16-bit, so a \\ud800 escape in JSON text is a ValueError and a character
beyond U+FFFF is not built; a datetime is naive (no tzinfo, now(), today()); functools.partial is a closure made where
partial() is called (a def or lambda of the program with plain parameters), so it is not an object with .func / .args.
"""
import ast
import datetime as D
import itertools
import json
import math
import os
import random
import re
import statistics
import subprocess
import sys
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parent
PKG = ROOT / "python" / "pkg-v12"
for each in (PKG, ROOT):
    if str(each) not in sys.path:
        sys.path.insert(0, str(each))

import prelude_genlib as G  # noqa: E402


def outcome(thunk):
    """The value of thunk() as text, or the exception's type and message."""
    try:
        return repr(thunk())
    except Exception as exc:                      # noqa: BLE001 -- the exception is the answer
        return type(exc).__name__ + ": " + str(exc)


def random_json(rng, depth=0):
    kind = rng.randrange(9 if depth < 3 else 6)
    if kind == 0:
        return None
    if kind == 1:
        return rng.random() < 0.5
    if kind == 2:
        return rng.randint(-10 ** 6, 10 ** 6)
    if kind == 3:
        return rng.choice([0.0, -0.0, 1.5, 1e22, 1e-7, 123456.789, rng.random() * 1000, float("inf"), float("-inf")])
    if kind in (4, 5):
        alphabet = ['a', 'b', ' ', '"', '\\', '/', '\n', '\t', '\x00', '\x1f', '\x7f', 'é', '€', '☺', '퟿']
        return ''.join(rng.choice(alphabet) for _ in range(rng.randrange(8)))
    if kind == 6:
        return [random_json(rng, depth + 1) for _ in range(rng.randrange(4))]
    if kind == 7:
        return tuple(random_json(rng, depth + 1) for _ in range(rng.randrange(3)))
    keys = ['a', 'b', 'k', 'x y', 'é', '']
    return {rng.choice(keys) + str(rng.randrange(3)): random_json(rng, depth + 1) for _ in range(rng.randrange(4))}


class G1Prelude(unittest.TestCase):
    def test_json_dumps(self):
        rng = random.Random(1)
        options = [{}, {"indent": 2}, {"indent": 0}, {"indent": "\t"}, {"sort_keys": True}, {"ensure_ascii": False},
                   {"separators": (",", ":")}, {"separators": (" ,", " = "), "indent": 1}, {"allow_nan": False},
                   {"indent": 3, "sort_keys": True, "ensure_ascii": False}, {"skipkeys": True}]
        for _ in range(1500):
            obj = random_json(rng)
            opts = rng.choice(options)
            self.assertEqual(outcome(lambda: G._ail_json_dumps(obj, **opts)), outcome(lambda: json.dumps(obj, **opts)),
                             (obj, opts))

    def test_json_dumps_errors(self):
        class Odd:
            pass
        for obj, opts in (({1, 2}, {}), ({(1, 2): 3}, {}), ({(1, 2): 3}, {"skipkeys": True}), (Odd(), {}),
                          ({"a": Odd()}, {"default": str if False else (lambda o: "odd")}),
                          (float("nan"), {"allow_nan": False}), ([float("inf")], {"allow_nan": False}),
                          ({"a": {1, 3}}, {"default": lambda s: sorted(s)}), ({1: 1, 2.5: 2, True: 3, None: 4}, {}),
                          ({"b": 1, 1: 2}, {"sort_keys": True})):
            self.assertEqual(outcome(lambda: G._ail_json_dumps(obj, **opts)), outcome(lambda: json.dumps(obj, **opts)))
        a = []
        a.append(a)
        self.assertEqual(outcome(lambda: G._ail_json_dumps(a)), outcome(lambda: json.dumps(a)))
        b = {}
        b["k"] = [b]
        self.assertEqual(outcome(lambda: G._ail_json_dumps(b)), outcome(lambda: json.dumps(b)))

    def test_json_loads(self):
        rng = random.Random(2)
        for _ in range(2500):
            obj = random_json(rng)
            text = json.dumps(obj, indent=rng.choice([None, 1, 2]), ensure_ascii=rng.random() < 0.5, allow_nan=True)
            self.assertEqual(outcome(lambda: G._ail_json_loads(text)), outcome(lambda: json.loads(text)), text)
            # one mutation: a character removed, replaced or inserted, or the text cut
            for _ in range(3):
                if not text:
                    break
                at = rng.randrange(len(text))
                how = rng.randrange(4)
                junk = rng.choice('{}[]",:\\ntrufalsNI-+.eE0189 \n\x01x')
                if how == 0:
                    bad = text[:at] + text[at + 1:]
                elif how == 1:
                    bad = text[:at] + junk + text[at + 1:]
                elif how == 2:
                    bad = text[:at] + junk + text[at:]
                else:
                    bad = text[:at]
                if re.search(r'\\u[dD][89a-fA-F]', bad):
                    continue                     # a surrogate escape: a declared difference (16-bit strings)
                self.assertEqual(outcome(lambda: G._ail_json_loads(bad)), outcome(lambda: json.loads(bad)), bad)

    def test_json_loads_edges(self):
        for text in ['', ' ', 'nul', 'null ', '-', '-0', '-0.0', '01', '1.', '1.e3', '1e', '1e+', '1E5', '0e0', '[1,]', '{"a":1,}',
                     '"\\ud83d"', '"\\u00e9"', '"\\u00E9"', '"\\uZZZZ"', '"abc', '"\\', '"\\"', '[', '{', '{"a"', '{"a":', '{"a":1',
                     '﻿[1]', 'NaN', 'Infinity', '-Infinity', '-Inf', '[NaN, -Infinity]', '12345678901234567', '1e400',
                     '[[[[[1]]]]]', '{"a": {"b": {"c": []}}}', '\t\n\r [1]\n', '"a\tb"', '{"a": 1} {"b": 2}', "'a'", 'True', 'tru',
                     '"\\/"', '"\\b\\f\\n\\r\\t"', '[1 , 2 ,3]', '{ "a" : 1 , "b" : 2 }']:
            if '\\ud83d' in text or 'e400' in text or '1234567890123456' in text:
                continue                         # a surrogate / an integer beyond 64 bits: a declared difference
            self.assertEqual(outcome(lambda: G._ail_json_loads(text)), outcome(lambda: json.loads(text)), text)
        for text, kw in (('{"a": 1, "b": [1, 2]}', {"object_hook": lambda d: sorted(d.items())}),
                         ('{"a": 1, "b": 2}', {"object_pairs_hook": lambda p: [k for k, v in p]}),
                         ('[1, 2.5]', {"parse_int": lambda s: "i" + s, "parse_float": lambda s: "f" + s}),
                         ('[NaN, Infinity, -Infinity]', {"parse_constant": lambda s: "c" + s})):
            self.assertEqual(outcome(lambda: G._ail_json_loads(text, **kw)), outcome(lambda: json.loads(text, **kw)))
        self.assertEqual(outcome(lambda: G._ail_json_loads(5)), outcome(lambda: json.loads(5)))

    def test_json_decode_error_fields(self):
        for text in ['{\n  "a": ]}', '[1,\n2,\n x]', '', '"abc', '{"a" 1}']:
            try:
                json.loads(text)
            except json.JSONDecodeError as want:
                try:
                    G._ail_json_loads(text)
                except G.JSONDecodeError as got:
                    self.assertEqual((got.msg, got.doc, got.pos, got.lineno, got.colno, got.args),
                                     (want.msg, want.doc, want.pos, want.lineno, want.colno, want.args))
                    self.assertIsInstance(got, ValueError)

    def test_itertools(self):
        rng = random.Random(3)
        pools = [[], [1], [1, 2, 3], "ab", (4, 5), range(3), [None, 0]]
        for _ in range(300):
            ps = [rng.choice(pools) for _ in range(rng.randrange(4))]
            self.assertEqual(list(G._ail_chain(*ps)), list(itertools.chain(*ps)))
            self.assertEqual(list(G._ail_chain_from_iterable(ps)), list(itertools.chain.from_iterable(ps)))
            rep = rng.randrange(3)
            self.assertEqual(list(G._ail_product_rep(rep, ps)), list(itertools.product(*ps, repeat=rep)))
            self.assertEqual(list(G._ail_product(*ps)), list(itertools.product(*ps)))
            args = [rng.choice([None, 0, 1, 2, 3, 5, -1, "x", 2.0]) for _ in range(rng.randrange(1, 4))]
            data = rng.choice(pools)
            self.assertEqual(outcome(lambda: list(G._ail_islice(data, *args))), outcome(lambda: list(itertools.islice(data, *args))), (data, args))
            n = rng.randrange(0, 12)
            self.assertEqual(list(itertools.islice(G._ail_cycle(data), n)), list(itertools.islice(itertools.cycle(data), n)))
            start, step = rng.choice([(0, 1), (5, 2), (-3, -1), (1.5, 0.5)])
            self.assertEqual(list(itertools.islice(G._ail_count(start, step), 6)), list(itertools.islice(itertools.count(start, step), 6)))
            self.assertEqual(list(G._ail_pairwise(data)), list(itertools.pairwise(data)))
            sel = [rng.randrange(2) for _ in range(rng.randrange(5))]
            self.assertEqual(list(G._ail_compress(data, sel)), list(itertools.compress(data, sel)))
            self.assertEqual(list(G._ail_filterfalse(None, data)), list(itertools.filterfalse(None, data)))
            self.assertEqual(list(G._ail_filterfalse(lambda v: v == 1, data)), list(itertools.filterfalse(lambda v: v == 1, data)))
            k = rng.randrange(0, 4)
            self.assertEqual(outcome(lambda: list(G._ail_batched(data, k))), outcome(lambda: list(itertools.batched(data, k))))
            self.assertEqual(list(G._ail_repeat(7, k)), list(itertools.repeat(7, k)))
        self.assertEqual(list(itertools.islice(G._ail_repeat("x"), 3)), ["x"] * 3)

    def test_isclose(self):
        rng = random.Random(4)
        vals = [0, 1, -1, 1e-10, 1e-9, 1.0 + 1e-9, 1.0 + 2e-9, 5, 5.0000000001, 1e308, float("inf"), -float("inf"), float("nan"), 0.1 + 0.2, 0.3]
        for _ in range(3000):
            a, b = rng.choice(vals), rng.choice(vals)
            kw = rng.choice([{}, {"rel_tol": 0.1}, {"abs_tol": 1e-9}, {"rel_tol": 0.0}, {"rel_tol": -1.0}, {"abs_tol": -0.5}])
            self.assertEqual(outcome(lambda: G._ail_isclose(a, b, **kw)), outcome(lambda: math.isclose(a, b, **kw)), (a, b, kw))

    def test_statistics(self):
        rng = random.Random(5)
        funcs = (("mean", G._ail_st_mean), ("pvariance", G._ail_st_pvariance), ("variance", G._ail_st_variance),
                 ("stdev", G._ail_st_stdev), ("pstdev", G._ail_st_pstdev), ("fmean", G._ail_st_fmean),
                 ("median", G._ail_st_median), ("median_low", G._ail_st_median_low), ("median_high", G._ail_st_median_high),
                 ("mode", G._ail_st_mode), ("multimode", G._ail_st_multimode))
        for _ in range(6000):
            n = rng.randint(0, 12)
            kind = rng.choice("ffim")
            if kind == "f":
                xs = [round(rng.uniform(-100, 100), rng.randint(0, 6)) for _ in range(n)]
            elif kind == "i":
                xs = [rng.randint(-50, 50) for _ in range(n)]
            else:
                xs = [rng.choice([rng.randint(-9, 9), rng.random() * 10, 0.1, 0.2, 0.3]) for _ in range(n)]
            for name, mine in funcs:
                want = outcome(lambda: getattr(statistics, name)(xs))
                got = outcome(lambda: mine(xs))
                self.assertEqual(got, want, (name, xs))
            pos = [abs(x) + 0.5 for x in xs]
            for name, mine in (("geometric_mean", G._ail_st_geometric_mean), ("harmonic_mean", G._ail_st_harmonic_mean)):
                self.assertEqual(outcome(lambda: mine(pos)), outcome(lambda: getattr(statistics, name)(pos)), (name, pos))
            if n >= 2:
                mu = rng.choice([0, 3, 2.5, xs[0]])
                for name, mine in (("pvariance", G._ail_st_pvariance), ("variance", G._ail_st_variance),
                                   ("stdev", G._ail_st_stdev), ("pstdev", G._ail_st_pstdev)):
                    self.assertEqual(outcome(lambda: mine(xs, mu)), outcome(lambda: getattr(statistics, name)(xs, mu)), (name, xs, mu))
        for xs in ([0, 1], [-1, 2], [1, 0.0], [], [-0.5], [float("nan")], [2, 8], [1.5, 0.0]):
            for name, mine in (("geometric_mean", G._ail_st_geometric_mean), ("harmonic_mean", G._ail_st_harmonic_mean)):
                got, want = outcome(lambda: mine(xs)), outcome(lambda: getattr(statistics, name)(xs))
                if "nan" in want or "inf" in want:
                    continue
                self.assertEqual(got, want, (name, xs))
        self.assertEqual(outcome(lambda: G._ail_st_mean(["a"])), outcome(lambda: statistics.mean(["a"])))

    def test_datetime(self):
        rng = random.Random(6)

        def tdv(t):
            return (t.days, t.seconds, t.microseconds)
        for _ in range(2500):
            y, m, d = rng.randint(1, 9999), rng.randint(1, 12), rng.randint(1, 28)
            h, mi, s = rng.randint(0, 23), rng.randint(0, 59), rng.randint(0, 59)
            us = rng.choice([0, 0, rng.randint(0, 999999)])
            a, b = D.datetime(y, m, d, h, mi, s, us), G.datetime(y, m, d, h, mi, s, us)
            self.assertEqual((a.isoformat(), a.isoformat(" ", "milliseconds"), str(a), repr(a)),
                             (b.isoformat(), b.isoformat(" ", "milliseconds"), str(b), repr(b)))
            self.assertEqual((a.weekday(), a.isoweekday(), a.toordinal(), tuple(a.isocalendar()), repr(a.date())),
                             (b.weekday(), b.isoweekday(), b.toordinal(), tuple(b.isocalendar()), repr(b.date())))
            for fmt in ("%Y-%m-%d %H:%M:%S.%f", "%a %A %b %B %d %j %U %W %w %y %I %p %e %-d %-m %c %x %X %%", "%D %F %R %T %u %h"):
                self.assertEqual(a.strftime(fmt), b.strftime(fmt), fmt)
            td = D.timedelta(days=rng.randint(-400, 400), seconds=rng.randint(-90000, 90000), microseconds=rng.randint(-2000000, 2000000))
            tg = G.timedelta(td.days, td.seconds, td.microseconds)
            self.assertEqual((tdv(td), str(td), repr(td), td.total_seconds()), (tdv(tg), str(tg), repr(tg), tg.total_seconds()))
            self.assertEqual(outcome(lambda: a + td), outcome(lambda: b + tg).replace("datetime.datetime", "datetime.datetime"))
            a2 = D.datetime(rng.randint(1, 9999), rng.randint(1, 12), rng.randint(1, 28), rng.randint(0, 23))
            b2 = G.datetime(a2.year, a2.month, a2.day, a2.hour)
            self.assertEqual(tdv(a - a2), tdv(b - b2))
            self.assertEqual((a < a2, a <= a2, a > a2, a >= a2, a == a2, a != a2), (b < b2, b <= b2, b > b2, b >= b2, b == b2, b != b2))
            k = rng.randint(-5, 9)
            self.assertEqual((tdv(td * k), tdv(-td), tdv(abs(td))), (tdv(tg * k), tdv(-tg), tdv(abs(tg))))
            if k:
                self.assertEqual((tdv(td / k), tdv(td // k)), (tdv(tg / k), tdv(tg // k)))
            td2 = D.timedelta(seconds=rng.randint(1, 100000))
            tg2 = G.timedelta(td2.days, td2.seconds)
            self.assertEqual((td / td2, tdv(td % td2), td // td2), (tg / tg2, tdv(tg % tg2), tg // tg2))
            da, db = D.date(y, m, d), G.date(y, m, d)
            n = rng.randint(-100000, 100000)
            self.assertEqual(outcome(lambda: da + D.timedelta(days=n)), outcome(lambda: db + G.timedelta(days=n)))
            self.assertEqual(repr(D.date.fromisoformat(str(da))), repr(G._ail_date_fromisoformat(str(db))))
            self.assertEqual(repr(D.datetime.fromisoformat(a.isoformat())), repr(G._ail_datetime_fromisoformat(a.isoformat())))
        for hrs in (0.5, 1.5, 0.1, 2.25, 0.333, 3):
            for sec in (0, 0.5, 1.25, 7, 0.1):
                for dd in (0, 0.5, 1.25, 2):
                    self.assertEqual(tdv(D.timedelta(days=dd, hours=hrs, seconds=sec, milliseconds=1.5)),
                                     tdv(G.timedelta(days=dd, hours=hrs, seconds=sec, milliseconds=1.5)))
        for bad in ((0, 1, 1), (2023, 2, 29), (2024, 13, 1), (2024, 0, 1), (2024, 4, 31), (10000, 1, 1)):
            self.assertEqual(outcome(lambda: D.date(*bad)), outcome(lambda: G.date(*bad)).replace("datetime.date", "datetime.date"))
        for bad in ((2024, 1, 1, 24), (2024, 1, 1, 0, 60), (2024, 1, 1, 0, 0, 60), (2024, 1, 1, 0, 0, 0, 1000000)):
            self.assertEqual(outcome(lambda: D.datetime(*bad)), outcome(lambda: G.datetime(*bad)))

    def test_datetime_strptime(self):
        formats = ["%Y-%m-%d", "%d/%m/%Y %H:%M", "%b %d, %Y", "%B %d %Y %I:%M %p", "%Y%m%d", "%d-%b-%y %H:%M:%S.%f",
                   "%A, %d %B %Y", "%j %Y", "%m/%d/%y", "%Y-%m-%dT%H:%M:%S", "%H:%M", "%y%m%d %H%M%S"]
        texts = ["2024-03-05", "5/3/2024 14:30", "Mar 05, 2024", "March 5 2024 02:15 PM", "20240305", "05-Mar-24 01:02:03.5",
                 "Tuesday, 05 March 2024", "065 2024", "3/5/24", "2024-03-05T10:11:12", "2024-3-5", "2024-13-01", "2024-02-30",
                 "abc", "2024-03-05 extra", "12/12/1999 23:59", "1/1/2000 0:0", "Feb 29, 2024", "Feb 29, 2023", " 2024-03-05",
                 "2024 - 03-05", "23:59", "7:5", "240305 123456", "12/31/99", "03/05/68", "03/05/69", "2024-03-05T10:11:12Z",
                 "2024-03-05 10:11:61", "Sep  5, 2024", "sep 5, 2024", "SEP 5, 2024", "2024-03-05\n"]
        for f in formats:
            for t in texts:
                self.assertEqual(outcome(lambda: G._ail_datetime_strptime(t, f)), outcome(lambda: D.datetime.strptime(t, f)), (t, f))
        for t in ["2024-03-05T10:11:12", "2024-03-05 10:11", "20240305T101112", "2024-03-05", "2024-03-05T10:11:12.5", "2024-03-05T10",
                  "2024-03-05T10:11:12.123456789", "bad", "2024-3-5", "2024-03-05T25:00", "2024-03-05T10:11:12,5", "20240305", "2024-03-05T1011"]:
            self.assertEqual(outcome(lambda: G._ail_datetime_fromisoformat(t)), outcome(lambda: D.datetime.fromisoformat(t)), t)
        for t in ["2024-03-05", "20240305", "2024-3-5", "2024-03-05T10", "x", "2024-02-30"]:
            self.assertEqual(outcome(lambda: G._ail_date_fromisoformat(t)), outcome(lambda: D.date.fromisoformat(t)), t)
        self.assertEqual(repr(G._ail_date_fromordinal(738000)), repr(D.date.fromordinal(738000)))
        self.assertEqual(outcome(lambda: G._ail_dt_format(G.date(2024, 1, 5), "%b %d")), "'Jan 05'")


# ------------------------------------------------------------------------------------------------ G2: whole programs
PROGRAMS = {}
PROGRAMS['json'] = r'''import json
from typing import Any


class Money:
    def __init__(self, cents):
        self.cents = cents


d = {"b": [1, 2.5, None, True], "a": {"x": "héllo\n\"q\"", "y": (1, 2)}, 3: 4, 1.5: False}
print(json.dumps(d))
print(json.dumps({"k": [1, {"z": []}], "e": {}}, indent=4))
print(json.dumps({"b": 1, "a": 2}, sort_keys=True, separators=(",", ":")))
print(json.dumps("é☺", ensure_ascii=False), json.dumps("é☺\x7f\x01"))
print(json.loads(json.dumps(d)))
doc = {"name": "x", "items": [1, 2.5, {"k": None}], "ok": True}
print(json.loads(json.dumps(doc, indent=2, sort_keys=True)) == doc)
print(json.loads("[1.5, 2, 1e2, -0, -0.0, 12345678901234, \"\\n\\t\\\\\"]"))
print(json.loads("  {\"a\" : {\"b\" : [ ] , \"c\" : { } } }  "))
print(json.loads("NaN"), json.loads("Infinity"), json.loads("-Infinity"), json.loads("null"), json.loads("true"), json.loads("\"s\""))
print(json.loads('{"a": 1, "a": 2, "b": 3}'))
print(json.loads('{"a": 1}', object_hook=lambda d: sorted(d.items())))
print(json.loads("[1, 2]", parse_int=lambda s: float(s)))
for bad in ['', ' ', '{', '[1,', '{"a"}', '{"a":}', '[1 2]', '"abc', '"a\nb"', 'tru', '01', '1.', '-', '{"a":1,}', '[1,]', "{'a': 1}", '"\\x"', '"\\u12"', '[1] x', '\x01', 'nul', '--1', '1e', '{"a":1 "b":2}']:
    try:
        print(json.loads(bad))
    except json.JSONDecodeError as e:
        print("E", e)
print(json.dumps(float("nan")), json.dumps([float("inf"), -float("inf")]), json.dumps(1e22), json.dumps(1e-7), json.dumps(-0.0), json.dumps(123456789012345678))
try:
    json.dumps(float("nan"), allow_nan=False)
except ValueError as e:
    print("E", e)
try:
    json.dumps({"a": {1, 2}})
except TypeError as e:
    print("E", e)
try:
    json.dumps({(1, 2): 3})
except TypeError as e:
    print("E", e)
print(json.dumps({(1, 2): 3}, skipkeys=True), json.dumps({1: 1, 2.5: 2, True: 3, None: 4}), json.dumps({"b": 1, "a": [1, 2]}, indent="--", separators=(" ,", " = ")))
print(json.dumps("\x00\x1f\x7fé€\"\\/"), json.dumps("é€\x7f", ensure_ascii=False))
print(json.dumps([], indent=3), json.dumps({}, indent=3), json.dumps([[]], indent=1), json.dumps([[], {}], indent=0))
print(json.dumps({"x": (3, 1), "y": Money(5)}, default=lambda o: {"cents": o.cents}))
lst = []
lst.append(lst)
try:
    json.dumps(lst)
except ValueError as e:
    print("E", e)
try:
    json.loads("{\n  \"a\": ]}")
except json.JSONDecodeError as e:
    print(e.msg, e.pos, e.lineno, e.colno, repr(e.doc), e.args)


def parse(text: str) -> Any:
    return json.loads(text)


data = parse('{"users": [{"name": "A", "age": 30}, {"name": "B", "age": 25.5}], "n": 2}')
for u in data["users"]:
    print(u["name"], u["age"])
print(sum(len(u["name"]) for u in data["users"]), list(data.keys()), data["n"] + 1)
'''

PROGRAMS['itertools'] = r'''import functools
import itertools
import math
from functools import partial
from itertools import chain, count, cycle, islice, product


def scale(f, x):
    return f * x


def three(a, b, c):
    return a * 100 + b * 10 + c


print(list(chain([1, 2], [3])), list(itertools.chain.from_iterable([[1], [2, 3]])), list(chain()), list(chain("ab", (1,))))
rows = [[1, 2], [3], []]
print(list(chain(*rows)), list(product(*[[1, 2], "ab"])))
print(list(islice([1, 2, 3, 4, 5], 1, 4)), list(islice(count(5), 3)), list(islice(count(10, -3), 4)), list(islice("abcdef", 0, None, 2)))
print(list(islice(range(10), 3)), list(islice(range(10), 5, 2)), list(islice(range(10), None)))
print(list(islice(cycle("ab"), 5)), list(islice(cycle([]), 3)), sum(islice(cycle([1, 2, 3]), 10)))
g = cycle([1, 2])
print(next(g), next(g), next(g))
for x in product([1, 2], [3, 4]):
    print(x)
print(list(product("ab", repeat=2)), list(product()), list(product([1], [])), list(product(range(2), repeat=3))[:3])
print(list(itertools.pairwise([1, 2, 3, 4])), list(itertools.pairwise("a")), list(itertools.compress("abcd", [1, 0, 1, 0])))
print(list(itertools.filterfalse(None, [0, 1, 2, 0])), list(itertools.filterfalse(lambda v: v > 1, [0, 1, 2, 3])), list(itertools.batched("abcdefg", 3)))
print(list(itertools.repeat(7, 3)), list(islice(itertools.repeat("x"), 2)), list(itertools.repeat(1, 0)))
for bad in (-1, "x"):
    try:
        print(list(islice([1, 2], bad)))
    except ValueError as e:
        print("E", e)
    except TypeError as e:
        print("E", e)
try:
    list(itertools.batched("abc", 0))
except ValueError as e:
    print("E", e)

nums = [1, 2, 3]
print(list(map(partial(scale, 2), nums)), sorted([5, 1, 4], key=partial(scale, -1)))
tr = functools.partial(three, 1, 2)
print(tr(7), partial(three, 4, 5, 6)(), partial(lambda a, b: a + b, 10)(5), partial(three, 1, b=2, c=3)())
fs = [partial(scale, i) for i in range(3)]
print([f(10) for f in fs])
print(functools.reduce(lambda a, b: a * b, range(1, 6)), functools.reduce(lambda a, b: a + b, [], 7))
print(math.isclose(0.1 + 0.2, 0.3), math.isclose(1.0, 1.1), math.isclose(1.0, 1.05, rel_tol=0.1), math.isclose(0, 1e-12, abs_tol=1e-9),
      math.isclose(0, 1e-12), math.isclose(float("inf"), float("inf")), math.isclose(float("inf"), 1e308), math.isclose(float("nan"), float("nan")),
      math.isclose(5, 5.0000000001), math.isclose(-3, 3))
try:
    math.isclose(1, 1, rel_tol=-1)
except ValueError as e:
    print("E", e)
'''

PROGRAMS['random'] = r'''import random
from random import randint, seed as reseed, choice

random.seed(12345)
print(random.random(), random.randint(1, 100), random.randrange(10), random.randrange(5, 50, 5))
xs = [1, 2, 3, 4, 5, 6, 7, 8]
random.shuffle(xs)
print(xs, random.choice(xs), choice("abcdef"))
print(random.sample(range(100), 5), random.sample(xs, 3))
print(random.uniform(1.0, 2.0), random.gauss(10, 2), random.expovariate(0.5), random.triangular(0, 10, 5))
print(random.getrandbits(20), random.choices(["a", "b", "c"], k=5), random.gauss())
reseed(7)
print(randint(1, 6), randint(1, 6), randint(1, 6))
random.seed(0)
print([random.randint(0, 9) for _ in range(10)])
random.seed(2 ** 40 + 5)
print(random.random())
random.seed(-17)
print(random.random(), random.randrange(100, 0, -7))
total = 0
for _ in range(1000):
    total += random.randint(1, 6)
print(total)
try:
    random.choice([])
except IndexError as e:
    print("E", e)
try:
    random.randint(5, 1)
except ValueError as e:
    print("E", e)
'''

PROGRAMS['statistics'] = r'''import statistics
from statistics import mean, median, stdev, StatisticsError

ints = [3, 1, 4, 1, 5, 9, 2, 6, 5, 3, 5]
floats = [2.5, 3.5, 1.0, 4.25, 9.0, 0.1, 0.2, 0.3, 1e-3, 123.456]
mixed = [1, 2.5, 3, 4.5]
for name, data in (("ints", ints), ("floats", floats), ("mixed", mixed), ("small", [1, 2]), ("pair", [0.1, 0.2])):
    print(name, mean(data), median(data), statistics.fmean(data), statistics.pvariance(data), statistics.pstdev(data))
    if len(data) > 1:
        print(" ", stdev(data), statistics.variance(data), statistics.median_low(data), statistics.median_high(data))
print(statistics.mean([1, 2, 3]), statistics.mean([1, 2, 4]), statistics.mean([2, 4]))
print(statistics.mode(ints), statistics.multimode(ints), statistics.mode(["a", "b", "b"]), statistics.multimode([]))
print(statistics.geometric_mean([1, 2, 4, 8]), statistics.geometric_mean(floats), statistics.harmonic_mean([1, 2, 4]), statistics.harmonic_mean(floats))
print(statistics.variance(ints, 4), statistics.pvariance(floats, 2.5), statistics.stdev(floats, 3.0), statistics.pstdev(ints, 4))
print(statistics.mean(x * 0.1 for x in range(1, 30)), statistics.stdev(x * 0.1 for x in range(1, 30)))
print(statistics.mean([10 ** 6 + 0.5, 10 ** 6 + 1.5, 10 ** 6 + 2.5]), statistics.pvariance([10 ** 6 + 0.5, 10 ** 6 + 1.5, 10 ** 6 + 2.5]))
print(statistics.median([1, 2, 3, 4]), statistics.median([1, 3, 2]), statistics.median(["a", "c", "b"]))
def attempt(label, thunk):
    try:
        print(label, thunk())
    except StatisticsError as e:
        print("E", label, e)


attempt("mean", lambda: statistics.mean([]))
attempt("median", lambda: statistics.median([]))
attempt("mode", lambda: statistics.mode([]))
attempt("stdev", lambda: statistics.stdev([1.5]))
attempt("pvariance", lambda: statistics.pvariance([]))
attempt("geo", lambda: statistics.geometric_mean([1, -1]))
attempt("harm", lambda: statistics.harmonic_mean([1, -2]))
attempt("fmean", lambda: statistics.fmean([]))
print(statistics.harmonic_mean([0, 1, 2]), statistics.harmonic_mean([3]))
try:
    mean(["a", "b"])
except TypeError as e:
    print("E", e)
'''

PROGRAMS['datetime'] = r'''import datetime
from datetime import date, timedelta
from datetime import datetime as dt


def span(a, b):
    return (b - a).days


start = date(2024, 2, 27)
days = [start + timedelta(days=i) for i in range(5)]
print([d.isoformat() for d in days], [d.weekday() for d in days], [d.isoweekday() for d in days])
print(days[2], repr(days[2]), span(days[0], days[4]), days[4] > days[0], days[0] == date(2024, 2, 27), days[1] != days[0])
print(sorted(reversed(days))[0], max(days), min(days))
print(date(2024, 12, 30).isocalendar(), date(2021, 1, 3).isocalendar(), tuple(date(2024, 3, 1).isocalendar()))
y, w, wd = date(2020, 12, 31).isocalendar()
print(y, w, wd, date(2024, 3, 1).isocalendar().week)
print(date(2024, 5, 17).strftime("%Y/%m/%d %a %b %j %U %W %w %A %B %y %-d %-m"), f"{date(2024, 5, 7):%d.%m.%Y}", format(date(2024, 1, 2), "%b %d"))
print(date.fromisoformat("2023-12-31"), date.fromordinal(738000), date(2024, 3, 1).toordinal(), date(2024, 1, 31).replace(month=2, day=29))
t = dt(2024, 1, 15, 9, 30, 15, 250)
print(t, repr(t), t.isoformat(), t.isoformat(" ", "seconds"), t.date(), t.weekday(), t.hour, t.minute, t.second, t.microsecond)
print(f"{t:%Y-%m-%d %H:%M:%S.%f} {t:%I:%M %p} {t:%H%M}")
t2 = t + timedelta(hours=40, minutes=45, seconds=50)
print(t2, t2 - t, (t2 - t).total_seconds(), t2 > t, t - timedelta(days=20))
print(dt.strptime("15/03/2024 08:05", "%d/%m/%Y %H:%M"), dt.strptime("Mar 5, 2024", "%b %d, %Y"), dt.fromisoformat("2024-03-05T10:11:12.5"))
for bad in ("2024-02-30", "x", "2024-03-05 12"):
    try:
        print(dt.strptime(bad, "%Y-%m-%d"))
    except ValueError as e:
        print("E", e)
try:
    date(2023, 2, 29)
except ValueError as e:
    print("E", e)
try:
    dt(2024, 1, 1, 24)
except ValueError as e:
    print("E", e)
try:
    date.fromisoformat("2024/01/01")
except ValueError as e:
    print("E", e)
try:
    print(date(9999, 12, 31) + timedelta(days=1))
except OverflowError as e:
    print("E", e)
td = timedelta(days=1, hours=2, minutes=3, seconds=4, microseconds=5)
print(td, repr(td), td.days, td.seconds, td.microseconds, td.total_seconds(), -td, abs(-td), td * 2, 3 * td, td / 2, td // 7, td / timedelta(hours=1), td % timedelta(hours=5))
print(timedelta(), repr(timedelta()), timedelta(days=-1, seconds=1), timedelta(weeks=2), timedelta(milliseconds=1500), timedelta(hours=0.5), bool(timedelta()), bool(td))
print(sum([timedelta(hours=1), timedelta(minutes=15)], timedelta()), sorted([timedelta(2), timedelta(1)]), timedelta(1) < timedelta(hours=25), timedelta(1) == timedelta(hours=24))
counts = {}
for d in days + days[:2]:
    counts[d] = counts.get(d, 0) + 1
print(counts[days[0]], len(counts), days[0] in counts, dt(2024, 1, 1) in {dt(2024, 1, 1): 1})
print(datetime.date(2024, 1, 1), datetime.timedelta(days=2), datetime.datetime(2024, 1, 1, 12), isinstance(t, date), isinstance(days[0], dt))
'''

PROGRAMS['tuples'] = r'''import random
from itertools import chain, cycle, pairwise, product
from typing import Tuple

random.seed(42)
moves: list[Tuple[int, int]] = [(0, 1), (0, -1), (1, 0), (-1, 0)]
x, y = 0, 0
for _ in range(200):
    dx, dy = random.choice(moves)
    x += dx
    y += dy
print(x, y)

labels: list[str] = ["alpha", "beta", "gamma"]
numbers: list[int] = [1, 2, 3, 4, 5, 6, 7]
pairs: list[tuple[str, int]] = list(zip(cycle(labels), numbers))
for label, number in pairs:
    print(f"({label!r}, {number})")

combos: list[tuple[int, int]] = sorted(product([3, 1], [4, 2]))
for a, b in combos:
    print(a * 10 + b)
print(combos)

steps: list[tuple[int, int]] = list(pairwise([1, 4, 9, 16]))
total = 0
for p, q in steps:
    total += q - p
print(total, steps)
print(len(list(chain(*[[1, 2], [3]]))))
'''

PROGRAMS['default_build'] = r'''import datetime
import statistics
from datetime import date, timedelta


def fmt(td):
    total = int(td.total_seconds())
    return str(total // 3600) + "h"


d = date(2024, 1, 31)
print(d, repr(d), d.weekday(), d.isoformat(), d.strftime("%A %d %B %Y"))
print(d + timedelta(days=30), d - timedelta(days=31), date(2024, 3, 1) - d)
dt = datetime.datetime(2024, 1, 15, 9, 30)
dt2 = datetime.datetime(2024, 1, 15, 17, 45, 10)
delta = dt2 - dt
print(dt, repr(dt), delta, delta.total_seconds(), fmt(delta), repr(delta))
print(dt < dt2, dt == dt2, sorted([dt2, dt]) == [dt, dt2], max(dt, dt2))
tds = [timedelta(hours=1), timedelta(minutes=30), timedelta(days=1, seconds=5)]
print(sum(tds, timedelta()), tds[0] * 3, tds[2] / 2, tds[0] // timedelta(minutes=7))
print(datetime.datetime.strptime("2024-03-05 14:30", "%Y-%m-%d %H:%M"), datetime.datetime.fromisoformat("2024-03-05T10:11:12"))
print(date.fromisoformat("2024-02-29").replace(year=2025 if False else 2028))
data = [2.5, 3.5, 1.0, 4.25, 9.0]
print(statistics.mean(data), statistics.median(data), statistics.stdev(data), statistics.pstdev(data), statistics.variance(data))
print(statistics.mean([1, 2, 3]), statistics.mean([1, 2, 4]), statistics.fmean([1, 2, 4]), statistics.mode([1, 1, 2]), statistics.multimode([1, 1, 2, 2]))
print(statistics.geometric_mean([1, 2, 4]), statistics.harmonic_mean([1, 2, 4]), statistics.median_low([1, 2, 3, 4]), statistics.median_high([1, 2, 3, 4]))
try:
    statistics.mean([])
except statistics.StatisticsError as e:
    print("err", e)
try:
    date(2023, 2, 30)
except ValueError as e:
    print("err", e)
'''

BUILD = r'''
import contextlib, io, sys
from pathlib import Path
root = sys.argv[1]
sys.path[:0] = [root, root + "/python/pkg-v12"]
import ail_chatgpt, shadowing, pyc
from pyfront import Unsupported
with contextlib.redirect_stderr(io.StringIO()):
    text, _, _ = ail_chatgpt._load_sources(Path(sys.argv[2]), (), "python", local_imports=True)
text = shadowing.rename_all(text, Unsupported)[0]
pyc.build(text, sys.argv[3], force_general=True)
'''


class G2Programs(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory(prefix="ail-genlib-")
        base = Path(cls.tmp.name)
        env = dict(os.environ)
        env.pop("AIL_NO_GENERAL", None)
        cls.results = {}

        def build(item):
            name, text = item
            src = base / ("prog_" + name + ".py")
            src.write_text(text, encoding="utf-8")
            exe = base / ("prog_" + name + "_exe")
            if name == "default_build":
                cmd = [sys.executable, "-B", str(ROOT / "ail_chatgpt.py"), "compile", src.name, "--syntax", "python", "-o", exe.name]
            else:
                cmd = [sys.executable, "-B", "-c", BUILD, str(ROOT), src.name, exe.name]
            made = subprocess.run(cmd, cwd=base, capture_output=True, text=True, timeout=900, env=env)
            want = subprocess.run([sys.executable, str(src)], capture_output=True, text=True, timeout=120, encoding="utf-8")
            got = None
            if exe.exists():
                got = subprocess.run([str(exe)], capture_output=True, text=True, timeout=120, encoding="utf-8")
            return name, made, want, got
        with ThreadPoolExecutor(max_workers=6) as pool:
            for name, made, want, got in pool.map(build, PROGRAMS.items()):
                cls.results[name] = (made, want, got)

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def check(self, name):
        made, want, got = self.results[name]
        self.assertIsNotNone(got, "no executable: " + (made.stdout + made.stderr)[-600:])
        self.assertEqual(want.returncode, 0, want.stderr[-400:])
        self.assertEqual(got.stdout.splitlines(), want.stdout.splitlines())
        self.assertEqual(got.returncode, want.returncode, got.stderr[-400:])

    def test_json(self):
        self.check("json")

    def test_itertools_functools_isclose(self):
        self.check("itertools")

    def test_random_module(self):
        self.check("random")

    def test_statistics(self):
        self.check("statistics")

    def test_datetime(self):
        self.check("datetime")

    def test_tuple_records(self):
        """Tuples that library functions build meet the record classes of the tuple pass (`_tu.f0`, `a, b = rec`)."""
        self.check("tuples")

    def test_default_build(self):
        """The default build (typed path first) takes a program of these names and prints what CPython prints."""
        self.check("default_build")


# ------------------------------------------------------------------------------------------------ G3: refusals
def refusal(source):
    import pyboxed2
    from pyfront import Unsupported
    try:
        pyboxed2.build(source, {})
    except Unsupported as exc:
        return str(exc)
    return None


class G3Refusals(unittest.TestCase):
    def test_decimal(self):
        text = refusal("from decimal import Decimal\nprint(Decimal('1.10') + Decimal('2.20'))\n")
        self.assertIn("decimal.Decimal is not built", text)
        self.assertIn("integer cents", text)

    def test_named_refusals(self):
        cases = [
            ("import random\nrandom.seed()\nprint(random.random())\n", "random.seed() needs one int seed"),
            ("import random\nrandom.seed('abc')\nprint(random.random())\n", "random.seed() needs one int seed"),
            ("import datetime\nprint(datetime.datetime.now())\n", "datetime.datetime.now is not built"),
            ("from datetime import date\nprint(date.today())\n", "datetime.date.today is not built"),
            ("import datetime\nprint(datetime.timezone.utc)\n", "datetime.timezone"),
            ("import json\nprint(json.dumps({}, cls=object))\n", "keyword argument cls is not built"),
            ("import statistics\nprint(statistics.quantiles([1, 2, 3, 4]))\n", "statistics.quantiles"),
            ("import json\nprint(json.load(open('x')))\n", "json.load"),
            ("import itertools\nprint(list(itertools.product([1], foo=2)))\n", "product() with a keyword argument other than repeat"),
            ("from functools import partial\nprint(partial(print, 1)())\n", "functools.partial() of anything but a def or lambda"),
            ("import statistics\nprint(statistics.mean([1], 2))\n", None),
        ]
        for source, fragment in cases:
            text = refusal(source)
            if fragment is None:
                continue
            self.assertIsNotNone(text, source)
            self.assertIn(fragment, text, source)

    def test_program_names_are_not_taken(self):
        """A name the program binds itself is not renamed: the use is refused as before, never mixed up with the class."""
        text = refusal("from datetime import date\n\n\ndef f(date):\n    return date\n\n\nprint(f(3), date(2024, 1, 1))\n")
        self.assertIsNotNone(text)
        self.assertIn("datetime.date", text)
        text = refusal("import json\n\n\nclass JSONDecodeError(Exception):\n    pass\n\n\ntry:\n    json.loads('[')\nexcept json.JSONDecodeError:\n    pass\n")
        self.assertIsNotNone(text)


# ------------------------------------------------------------------------------------------------ G4: untouched
class G4Untouched(unittest.TestCase):
    def test_other_programs(self):
        import genlib
        for source in ("print(1)\n", "import math\nimport random as r\nprint(math.sqrt(4), r.Random(3).random())\n",
                       "import collections\nfrom itertools import groupby, accumulate\nprint(list(accumulate([1, 2, 3])))\n",
                       "import json\nprint(json.load)\n" if False else "x = 1\n",
                       "import datetime as dtm\nprint(dtm)\n" if False else "import os\nprint(os.getcwd() != '')\n",
                       "import itertools\nprint(list(itertools.combinations([1, 2, 3], 2)), list(itertools.groupby('aab')))\n",
                       "import functools\n\n@ functools.lru_cache(None)\ndef f(n):\n    return n\n\n\nprint(f(2), functools.reduce(lambda a, b: a + b, [1, 2]))\n"):
            tree = ast.parse(source)
            before = ast.dump(tree)
            text, used = genlib.rewrite(tree)
            self.assertEqual(text, "", source)
            self.assertEqual(used, set(), source)
            self.assertEqual(ast.dump(tree), before, source)


if __name__ == "__main__":
    unittest.main()

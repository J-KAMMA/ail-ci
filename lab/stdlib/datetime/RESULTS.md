# datetime coverage

Twelve realistic `datetime` programs, built with the default mode:

    python3 AIL_CURRENT/ail_chatgpt.py compile lab/stdlib/datetime/<program>.py --syntax python

`typed` means the default build stayed on the typed path, `general` means it fell back to the
general path (the note in the build log says why), `refused` means the default build failed.
For every built program, the compiled binary prints exactly CPython 3.12's stdout and exits
with the same status.

| program | result | note / first refusal |
| --- | --- | --- |
| age_calculator.py | general | tuple assignment from Call; output matches CPython |
| birthday_parser.py | typed | output matches CPython |
| calendar_export.py | refused | `datetime.time.fromisoformat is not built` |
| duration_report.py | typed | output matches CPython |
| epoch_convert.py | refused | `.timetuple() returns a struct_time` |
| invoice_due.py | typed | output matches CPython |
| iso_week.py | refused | `.isocalendar() returns a named tuple: use isoweekday() and strftime("%G %V")` |
| log_timestamps.py | typed | output matches CPython |
| meeting_slots.py | typed | output matches CPython |
| sprint_plan.py | typed | output matches CPython |
| timesheet.py | typed | output matches CPython |
| workday_schedule.py | general | `_AilDT instance as a subscript` (a date as a dict key); output matches CPython |

Built: 9 of 12. The general-path programs also match CPython when the general path is forced,
and every built program matches on both the default and forced-general builds.

The full refusal text of the three refused programs (the first line is the front end's summary,
the `note:` line is the specific cause):

    calendar_export.py:1:1: not in the subset: import of 'datetime' is not available: this compiler builds only the modules it models (math, sys, collections, itertools, functools, heapq, bisect, re, json) (the general path could not build this program either); general path: time.fromisoformat (not yet published in NAMES_library.json)
    note: lab/stdlib/datetime/calendar_export.py:5: datetime.time.fromisoformat is not built

    epoch_convert.py:1:1: not in the subset: import of 'datetime' is not available: this compiler builds only the modules it models (math, sys, collections, itertools, functools, heapq, bisect, re, json) (the general path could not build this program either); general path: datetime.datetime.fromtimestamp is not built on the general path (datetime.now(), utcnow(), today(), fromtimestamp(), combine(), tzinfo and the class attributes)
    note: lab/stdlib/datetime/epoch_convert.py:8: .timetuple() returns a struct_time

    iso_week.py:1:1: not in the subset: import of 'datetime' is not available: this compiler builds only the modules it models (math, sys, collections, itertools, functools, heapq, bisect, re, json) (the general path could not build this program either); general path: datetime.date.fromisocalendar is not built on the general path (date.today(), date.fromtimestamp() and the class attributes min / max / resolution)
    note: lab/stdlib/datetime/iso_week.py:8: .isocalendar() returns a named tuple: use isoweekday() and strftime("%G %V")

## Follow-ups (big new features, out of scope here)

- `time.fromisoformat()`: would need an aware `time` value (the ISO strings with an offset)
  in addition to the naive parser. Exact refusal:
  `datetime.time.fromisoformat is not built`.
- `datetime.timetuple()` / `date.timetuple()` / `utctimetuple()`: would need a `struct_time`
  value (nine named fields). Exact refusal: `.timetuple() returns a struct_time`.
- `date.isocalendar()`: would need the named tuple `(year, week, weekday)` and attribute
  access on it; `strftime("%G %V %u")` already gives the same numbers. Exact refusal:
  `.isocalendar() returns a named tuple: use isoweekday() and strftime("%G %V")`.
- `date.fromisocalendar()`: the runtime function exists, but it is not published on the
  general path; the program above is blocked earlier by `.isocalendar()`. Exact general-path
  refusal: `datetime.date.fromisocalendar is not built on the general path`.

The documented timedelta range is smaller than CPython's (about 106,751,991 days because the
key is int64 microseconds); the duration program checks a value both implementations reject
(1,000,000,000 days) rather than a value only AIL rejects. This is the existing declared
limit, not a new difference.

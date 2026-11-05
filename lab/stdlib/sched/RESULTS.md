# `sched` coverage results

Build command for every program (default build, `-o` must not exist yet):

```
python3 AIL_CURRENT/ail_chatgpt.py compile lab/stdlib/sched/<program>.py -o /tmp/<program>.out
```

The oracle is `python3 <program>.py` (CPython 3.12.3). Every program supplies a fake clock to
`sched.scheduler(timefunc, delayfunc)`: `timefunc` reads a counter and `delayfunc` prints the
delay and adds it to the counter, so no output depends on the real clock.

## Before

`sched` was not shipped as AIL source, so `sched.scheduler` was not published and every program
that constructed a scheduler was refused at that line.

| program | default build | first refusal |
| --- | --- | --- |
| `01_enter_and_enterabs.py` | refused | `not in the subset: sched.scheduler (not yet published in NAMES_library.json)` |
| `02_priority_and_fifo.py` | refused | `not in the subset: sched.scheduler (not yet published in NAMES_library.json)` |
| `03_cancel_pending.py` | refused | `not in the subset: sched.scheduler (not yet published in NAMES_library.json)` |
| `04_cancel_already_run.py` | refused | `not in the subset: sched.scheduler (not yet published in NAMES_library.json)` |
| `05_queue_and_empty.py` | refused | `not in the subset: sched.scheduler (not yet published in NAMES_library.json)` |
| `06_blocking_false.py` | refused | `not in the subset: sched.scheduler (not yet published in NAMES_library.json)` |
| `07_reschedule_inside.py` | refused | `not in the subset: the method .enter() (on a value of unknown static kind)` |
| `08_exception_then_resume.py` | refused | `not in the subset: sched.scheduler (not yet published in NAMES_library.json)` |
| `09_float_times.py` | refused | `not in the subset: sched.scheduler (not yet published in NAMES_library.json)` |
| `10_time_beyond_int64.py` | refused | `int64 constant out of range: 9223372036854775808` |

Result before: **0 built, 0 typed, 10 refused**.

## After

_To be filled after the bundled module and test are in place._

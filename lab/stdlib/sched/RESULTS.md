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

`AIL_CURRENT/stdlib/sched.py` ships CPython 3.12's `Lib/sched.py` as AIL source. Every passing
program is built in the default build and again with `AIL_UNIFIED_FORCE=1`; stdout and the exit
status match `python3` in both. "general" means the build succeeded on the general path (the
compiler prints `note: ... built on the general path ...` on stderr).

| program | default build | result |
| --- | --- | --- |
| `01_enter_and_enterabs.py` | refused | `not in the subset: using function say as a first-class value (it has defaults, *args or **kwargs)` |
| `02_priority_and_fifo.py` | general | matches CPython (both builds) |
| `03_cancel_pending.py` | general | matches CPython (both builds) |
| `04_cancel_already_run.py` | general | matches CPython (both builds) |
| `05_queue_and_empty.py` | general | matches CPython (both builds) |
| `06_blocking_false.py` | general | matches CPython (both builds) |
| `07_reschedule_inside.py` | general | matches CPython (both builds) |
| `08_exception_then_resume.py` | general | matches CPython (both builds) |
| `09_float_times.py` | general | matches CPython (both builds) |
| `10_time_beyond_int64.py` | refused | `int64 constant out of range: 9223372036854775808` |

Result after: **8 built, 0 typed, 8 general, 2 refused; 8/10 match CPython in both builds.**

## The shipped module

`AIL_CURRENT/stdlib/sched.py` keeps CPython 3.12's `Event` as
`collections.namedtuple('Event', 'time, priority, sequence, action, argument, kwargs')`, so
`event.time`, `event.priority`, `event.sequence`, `event.action`, `event.argument`,
`event.kwargs`, indexing, unpacking and ordering by the first three fields all work.  `queue` is
a `@property` that returns a fresh ordered list, so a caller's list never aliases the scheduler
state.  `cancel` removes the event object returned by `enter`/`enterabs`; it does not match on
`sequence` alone, so cancelling another scheduler's event raises `ValueError` instead of silently
removing the wrong event.  `scheduler()` with no arguments works: the defaults are the module
wrappers `_default_time` (`time.monotonic`) and `_default_delay` (`time.sleep`), because the
compiler builds those builtins as calls but not as first-class values.

## Compiler follow-ups

These are refusals in the compiler, not in `sched`; the module is not edited for them.

1. `01_enter_and_enterabs.py`: passing a function that has defaults as a first-class value is
   refused (`using function say as a first-class value (it has defaults, *args or **kwargs)`).
   The program also passes `kwargs=`, and a `**kwargs` call argument is refused
   (`not in the subset: a **kwargs call argument`), so `sched` cannot forward keyword arguments
   to an action here; `AIL_CURRENT/stdlib/sched.py` raises `TypeError` for non-empty kwargs.
   `_invoke` dispatches positional action arguments up to 16; more than 16 raises
   `TypeError` naming the limit.
2. `10_time_beyond_int64.py`: `2 ** 63` is refused as an int64 constant out of range, as the
   brief allows (the program stops loudly).
3. Taking a bound method as a first-class value (`clock.time` passed to `sched.scheduler`) is not
   built; it raises `AttributeError: 'Clock' object has no attribute 'time'` at run time even
   though a direct call works.  The programs therefore use module-level clock functions, which
   exercise the same `sched` behaviour without touching this unrelated limitation.
4. `scheduler.__init__`, `enterabs` and `enter` keep their defaults/`argument=`/`kwargs=` in
   Python source, so the compiler builds them on the general path (it requires plain positional
   arguments for the typed path).  The general path makes two references to the same function
   compare unequal, so `cancel` matches the event object itself rather than comparing actions.

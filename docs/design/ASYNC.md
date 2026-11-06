# async / await and a small asyncio

Design for job `ffasync0`, 2026-11-06. This note is design only: the compiler is not changed
here. It defines the lowering, the event-loop order, the clock, the two feature sets
(`ffasync1` / `ffasync2`), and the exact names each one refuses. The accompanying evidence is in
`lab/asyncio/`: twelve ordinary `async def` programs, their CPython 3.12 transcripts in
`lab/asyncio/expected/`, and a generator-only reference model in `lab/asyncio/model/asyncio.py`.
The model reproduces CPython on all twelve (`python3 lab/asyncio/model/run_model.py` and
`--oracle` both print `12/12 matched`); the compiler refuses all twelve today.

## Answer in brief

1. **Lowering.** `asynclib.py` is a tree pass run by both compile paths from
   `filelib.rewrite_tree` (the effect-stage hook at
   `AIL_CURRENT/python/pkg-v12/filelib.py:145`). It turns each `async def` into an ordinary
   `def` that returns a small `_Coro` wrapper around a generator, and each `await` into an inline
   `send` loop in the same frame. Return values travel through a hidden per-coroutine cell, not
   `StopIteration.value`; cancellation travels as a `_CANCEL` sentinel, not `generator.throw`.
   That matters because the general path already has `yield`, `send`, `close`, `next`,
   `try/except StopIteration` and statement `yield from`, but does **not** have `throw`,
   `StopIteration.value`, or `yield from` as an expression (evidence below). The lowering uses
   only the existing generator machinery, so ffasync1 needs no new generator feature in the C
   runtime.
2. **Order.** One FIFO ready deque; timers in a heap ordered by `(deadline_ns, sequence)`.
   One turn moves every timer that is due at the start of the turn to the **end** of the ready
   deque, then runs exactly the handles that were ready at the start of the turn. Callbacks
   scheduled during a turn run in the next turn. `call_later(d)` is `call_at(now + d)`.
3. **Time.** The loop reads `time.time_ns()` and waits with `time.sleep(seconds)`. A28
   (`docs/spec/DIFFERENCES.md:49`) makes both program inputs: `AIL_CLOCK=...` pins every read,
   and `sleep(x)` advances the pinned clock by `x` without sleeping. With no `AIL_CLOCK`, the
   loop sleeps for real.
4. **Subset.** `ffasync1` is the twelve labs: scheduling, `sleep`, `gather`, `wait_for`, tasks,
   futures, queues, events, locks and cancellation. `ffasync2` adds `wait`, `as_completed`,
   `shield`, semaphores/conditions/barriers, priority/LIFO queues, `TaskGroup`, `timeout`, and
   `Runner`. Everything else in CPython 3.12's `asyncio.__all__` is refused by name; sockets,
   streams, transports, subprocesses, threads, policies and child watchers are permanent
   refusals (the AIL runtime has none of those as asyncio primitives).
5. **Cost.** `asynclib.rewrite_tree` is a no-op unless a source contains `AsyncFunctionDef` or
   `Await`; the shipped `asyncio` package is additionally gated in `ail_modules` on the same
   syntax. A building program that contains no `async def` therefore keeps byte-identical C.
   The gate is not
   optional: today an unused `import shlex` grows plain C from 135,355 to 870,613 bytes, and an
   unused `import asyncio` already takes the general path at 561,130 bytes. Without the gate,
   adding `AIL_CURRENT/stdlib/asyncio/` would change every program that merely imports it.

## 1. Lowering

### 1.1 What the current generator support actually is

Probes in `/tmp/gprobes/` against this tree, default build and `--strict`. "typed" means
`AIL_NO_GENERAL=1`; "general" means the boxed path.

| form | typed path | general path | gap, and the step that fixes it |
| --- | --- | --- | --- |
| `yield e` | refused by name (`yield`) | builds and runs | none on the general path; it is the suspension point. Step 2 lowers `await` onto it; the typed path is out of scope (section 10). |
| `x = yield e` (`send`) | first refusal is `yield` | builds and runs | none; `Task` and the generated await loop drive with `send`. Steps 1-2. |
| `yield from g` as a statement | refused by name (`yield from`) | builds; sub-generator's return value is discarded | gap: the value is lost. Not used; step 2 emits an inline `send` loop instead. |
| `x = yield from g` | refused by name (`yield from`) | refused: `yield from (generator functions are not modelled by the general path)` | gap: expression form unavailable. Step 2's inline `send` loop keeps the value without it. |
| `next(g)` | refused by name (`next`) | builds and runs | none; not required (steps 1-2 use `send` only). |
| `g.send(v)` | first refusal is `yield` | builds and runs | none; used by steps 1-2. |
| `g.close()` | first refusal is `yield` | builds and runs | none; step 2's await loop closes the awaited iterator on cancellation. |
| `g.throw(E)` | first refusal is `yield` | refused: `the method .throw() (on a value of unknown static kind)` | gap: no `throw`. Step 2 sends `_CANCEL` and raises `CancelledError` in the await loop instead. |
| `except StopIteration` | refused: `except StopIteration; the exceptions this language has are ...` | builds and runs (verified) | none on the general path; the refusal is a typed-path blocker only, and step 2's generated loop runs on the general path. |
| `StopIteration.value` | unreachable (the `except` clause is refused first) | runtime `AttributeError: 'instance' object has no attribute 'value'` | gap: no return value through `StopIteration`. Step 2 rewrites `return` to write a hidden one-element cell. |
| `return value` in a generator | first refusal is `yield` | builds; the value is not observable through `.value` | same gap; step 2's hidden cell carries it. |
| `async def` | refused | refused (same text) | step 2 converts it to `def` returning `_Coro`. |
| `await` | refused | not reached (no async def) | step 2 inlines the send loop. |
| `async for`, `async with` | refused by name | not reached | named refusal in step 2; stays refused in ffasync1/ffasync2. |
| `import asyncio` | refused import | refused import, then a general-path note | step 1 ships `AIL_CURRENT/stdlib/asyncio/`; step 3 gates it on async syntax so no-async C is unchanged. |

The exact current refusals that pin this down:

```
lab/asyncio/l01_call_soon_fifo.py:4:1: not in the subset: async def: this language has no coroutines or event loop.
  write instead: an ordinary `def`
```

```
yield: this language has no generators.
  write instead: build a list with `out.append(x)` and `return out`
```

```
yield from: this language has no generators.
```

```
call to next(); this compiler builds only the builtins it names, and refuses the rest by name rather than guessing at one.
  write instead: define `next` yourself with a `def` and call that, or use the builtin that does the job (len, sum, min, max, sorted, abs, range, int, float, str)
```

```
except StopIteration; the exceptions this language has are AssertionError, EOFError, Exception, FileExistsError, FileNotFoundError, IndexError, IsADirectoryError, KeyError, NotADirectoryError, OSError, OverflowError, PermissionError, RuntimeError, UnicodeDecodeError, ValueError, ZeroDivisionError
```

```
/tmp/gprobes/throw.py:3:9: not in the subset: yield: this language has no generators (the general path could not build this program either); general path: the method .throw() (on a value of unknown static kind)
```

```
/tmp/gprobes/yieldfrom_ret.py:2:5: not in the subset: yield: this language has no generators (the general path could not build this program either); general path: yield from (generator functions are not modelled by the general path)
```

```
import of 'asyncio' is not available: this compiler builds only the modules it models (math, sys, collections, itertools, functools, heapq, bisect, re, json) (the general path could not build this program either); general path: asyncio.run (not yet published in NAMES_library.json)
```

The refusal table is `AIL_CURRENT/python/pkg-v12/pyfunc.py` `_EXPR_SHAPE_REFUSALS` at
`pyfunc.py:12962` (`Await`), `12964` (`Yield`), `12966` (`YieldFrom`) and
`_STMT_SHAPE_REFUSALS` at `pyfunc.py:12991` (`AsyncFunctionDef`), `12993` (`AsyncFor`),
`12995` (`AsyncWith`). The general path has its own, identical `async def` refusal at
`AIL_CURRENT/python/pkg-v12/pyboxed2.py:12570`, so the lowering must happen before both.

### 1.2 The `asynclib` pass

`asynclib.rewrite_tree(tree, Unsupported)` is called near the top of
`filelib.rewrite_tree`, before the file/process/path lowerers. It returns `False` and leaves the
tree untouched when there is no `AsyncFunctionDef` and no `Await`. When it runs:

1. **Refuse async generators.** A `yield` or `yield from` anywhere lexically inside an
   `async def` is refused:
   `async def f: yield is an async generator; this language has no async generators.\n  write instead: build a list and return it, or put items on an asyncio.Queue`.
2. **Refuse native async statements.** `async for` and `async with` are refused:
   ```text
   async for: this language has no async iterators.
     write instead: a for loop over a list, or while True: x = await queue.get()
   ```
   ```text
   async with: this language has no async context managers.
     write instead: try/finally around the awaited call
   ```
   Async comprehensions are refused the same way.
3. **Convert `async def`.** For each async function `f` (including methods and nested defs),
   emit an ordinary function with the same name, parameters, defaults and annotations that
   creates and returns a `_Coro`:
   ```python
   def f(a, b=1):
       _ail_async_cell = [None]
       return _Coro(_ail_async_f_1(a, b, _ail_async_cell), _ail_async_cell)
   ```
   The original body moves into `_ail_async_f_1` with one hidden trailing parameter
   `_ail_async_cell` (a one-element list shared with `_Coro`). The body keeps its `def`-level
   locals, `try/finally`, closures and `return` statements, so the general path's existing
   function/closure support is unchanged. The hidden cell is how a return value survives
   `finally` and nested awaits without `StopIteration.value`.
4. **Convert `return` inside an async body.**
   - `return expr` becomes `_ail_async_cell[0] = expr; return`
   - a bare `return` becomes `_ail_async_cell[0] = None; return`
   - falling off the end leaves the cell at its initial `None`.
   A `return` in a `finally` overwrites the cell, which is CPython's rule; a `return` in an
   outer `try` is evaluated before the `finally` runs, also CPython's rule.
5. **Convert `await expr`.** The operand is coerced to the coroutine protocol once, then driven
   in a loop in the *same function frame*:
   ```python
   _ail_it = _ail_async_coerce(expr)
   _ail_send = None
   while True:
       try:
           _ail_y = _ail_it.send(_ail_send)
       except StopIteration:
           _ail_value = _ail_it.result
           break
       _ail_send = yield _ail_y
       if _ail_send is _CANCEL:
           _ail_it.close()
           raise CancelledError()
       _ail_send = None
   ```
   The loop is generated with unique `_ail_*` names per site. Because the `raise` is in the
   async function's own frame, a user `try/except asyncio.CancelledError` sees it at the await
   point, and a `finally` runs. Nothing calls `generator.throw` or reads
   `StopIteration.value`.
6. **Bind imports.** `import asyncio` and `from asyncio import ...` are left for the normal
   module loader; the shipped package is `AIL_CURRENT/stdlib/asyncio/`. Whenever async syntax
   is present, `asynclib` injects one tiny support prelude (`_Coro`, `_CANCEL`,
   `_ail_async_coerce`, `_FutureCoro`). The package does not import that prelude: it uses the
   same duck-typed protocol (`send`, `close`, `done`, `result`), so a coroutine is any object
   with those methods. The prelude is inserted once and only for a program with async syntax.

`_Coro` is a plain class in the prelude (not a generator); it holds the generator and the cell:

```python
class _Coro:
    def __init__(self, generator, cell):
        self.generator = generator
        self.cell = cell
        self._done = False
    def send(self, value):
        try:
            return self.generator.send(value)
        except StopIteration:
            self._done = True
            raise
    def close(self):
        self.generator.close()
    @property
    def result(self):
        return self.cell[0]
```

`_Coro` is created by the lowering, so the cell is filled by `return` lowering in the body. A
`Future`/`Task` is wrapped by a `_FutureCoro` adapter in the same prelude; it yields the future
until done and reports `.result`. `asyncio.create_task` can accept either a `_Coro` or a
`Future`; `ensure_future` does the coercion. Because `_Coro.send` is an ordinary method, the
general path's `send` support is enough.

**Why not `yield from`?** It would be shorter, but the general path's statement form drops the
sub-generator's return value and the expression form is refused (table above). Awaiting a
coroutine that returns a value would then either lose the value or need a compiler change.
The inline loop plus cell keeps values and `finally` correct on the compiler as it is.

**Why not `throw`?** The general path refuses `.throw` at compile time. `Task.cancel()` sets a
`must_cancel` flag and schedules the next step; the next step sends `_CANCEL` as the value of
the suspended `yield`, and the await loop above raises `CancelledError` in the async frame.
`Task.cancel()` also cancels the future the task is waiting on. If the coroutine catches
`CancelledError` and keeps going, the task continues, as in CPython. `uncancel()`/`cancelling()`
and `TaskGroup`'s cancellation-count rules are ffasync2.

`CancelledError` is `class CancelledError(BaseException)` so `except Exception` does not catch
it, as in CPython 3.8+. `TimeoutError` is an ordinary exception. `InvalidStateError` is an
ordinary exception.

## 2. Event-loop order

The reference implementation is `lab/asyncio/model/asyncio.py`; all twelve transcripts were
checked against CPython 3.12. The rules, in `_EventLoop._run_once`:

1. **Ready.** `call_soon(cb, *args)` appends a `Handle` to one FIFO `deque`. Handles execute in
   append order. `call_soon` never runs a callback synchronously.
2. **Timers.** `call_at(when, cb)` pushes `(deadline_ns, sequence, handle)` onto a heap;
   `sequence` is a monotonically increasing insertion number, so equal deadlines are FIFO.
   `call_later(delay, cb)` is `call_at(now + delay, cb)`. Cancelled timer handles are skipped
   when popped.
3. **A turn.** `_run_once`:
   - pops every scheduled timer with `deadline_ns <= now` and appends its handle to the **end**
     of the ready deque, in heap order;
   - if the ready deque is empty, sets the clock to the earliest deadline and moves those due
     timers in, then returns if there is still nothing ready;
   - snapshots `count = len(ready)` and runs exactly `count` handles from the front. Handles
     appended during the turn are behind the snapshot and run in the next turn.
4. **Consequences.** A timer that becomes due during a callback is not run in that same turn.
   A `call_soon` made by a callback runs after all callbacks already in the snapshot. A
   `call_later(0)` made by a callback is a timer, so it runs after the snapshot and after any
   already-ready work, but with the same-`now` tie broken by insertion order.
5. **Task steps.** `create_task` creates a `Task` and `call_soon(task._step)`; the coroutine's
   first step therefore runs after the current turn. A task that yields a pending future adds a
   done callback and is woken by `call_soon(_step)`. A task that yields `None` (for example
   `sleep(0)`) is rescheduled with `call_soon(_step)`.
6. **`asyncio.run`.** Refuses when a loop is already running; creates the main task with
   `call_soon`, runs until it is done, returns the coroutine's result, then cancels and drains
   the remaining tasks and closes the loop, as CPython does. Exceptions propagate from `run`.
   A second `asyncio.run` after the first is allowed.
7. **`gather`.** Children are created in argument order; results are stored in argument order
   even though completion order differs. The first uncaught child exception sets the gather
   future's exception and is re-raised at the `await`; siblings keep running (CPython 3.12 does
   not cancel them). `return_exceptions=True` stores exceptions/cancellations in place.
8. **`wait_for`.** Schedules a timeout timer, waits for either the child or the timer; on
   timeout it cancels the child and waits for its cancellation, then raises `TimeoutError`. A
   child that finishes first cancels the timer.
9. **Cancellation.** `Task.cancel()` on a not-done task cancels the future it is waiting on (if
   any) and sets `must_cancel`; the next `_step` sends `_CANCEL`. `CancelledError` raised out of
   the coroutine cancels the task's future; `await task` then raises `CancelledError` in the
   waiter. A task that is already done returns `False` from `cancel()`.
10. **Queue, Event, Lock.** Ready waiters are FIFO deques. `Event.set` resolves every current
    waiter and clears the deque; `Lock.release` wakes exactly the first live waiter; `Queue`
    with `maxsize` blocks `put` on a full queue and `get` on an empty one; `task_done`/`join`
    use an unfinished count. `qsize()` is the number of items, not waiters.

Worked examples from the labs:

* `l01`: the first turn runs only `main` (the snapshot was one handle). `call_soon` for
  `callback-1`/`callback-2` and the task's own reschedule go behind the snapshot; the next turn
  runs `callback-1`, `callback-2`, then `main`'s continuation. Hence `main`, `callback-1`,
  `callback-2`, `after-sleep-0`, `callback-3`, `after-sleep-0-again`.
* `l02`: four timers at 0.01/0.01/0.02/0.02, inserted b before d and a before c. The heap
  order at each deadline is `(deadline, sequence)`, so the output is `b d a c`.
* `l03`: completion order is `b a c`; `gather` returns `['a', 'b', 'c']` in argument order.
* `l07`: `Queue(maxsize=1)` forces the producer to resume after the consumer; the output is
  `put 0`, `got 0`, `put 1`, `got 1`, `put 2`, `got 2`, `qsize 0`.
* `l12`: cancelling a lock waiter removes its pending future; `holder` later releases and
  `locked()` is `False`.

## 3. Time: `AIL_CLOCK`

A28 is `docs/spec/DIFFERENCES.md:49`. The loop uses exactly the two clock forms A28 covers:

* `now_ns = time.time_ns()` for deadlines and `loop.time()`;
* for a wait, `time.sleep((next_deadline_ns - now_ns) / 1e9)`, then `time.time_ns()` again.

With `AIL_CLOCK=<seconds>[.<fraction>]`, every `time_ns()` read returns the pinned value and
`sleep(x)` advances it by `x` (nanoseconds, rounded away from zero) without sleeping. The
twelve programs therefore run deterministically and instantly under the same value on CPython
and in the model; `run_model.py` sets `AIL_CLOCK=1700000000` for both. A malformed `AIL_CLOCK`
is a `ValueError` at the first read, as A28 says. With no `AIL_CLOCK`, the loop really sleeps,
and the order is still the same because it always sleeps only until the earliest deadline.

Two boundaries to record in the design, not paper over:

* **Monotonic vs wall clock.** CPython's loop uses a monotonic clock. A28 exposes
  `time.time_ns()` and `time.sleep()`, not `time.monotonic_ns()`. The ffasync1 loop therefore
  follows the wall clock. A clock jump backwards can delay a timer; a jump forwards can run it
  early. The pinned-clock tests cannot see this. If a monotonic name is added to A28 later, the
  loop should switch to it; until then this is a named difference (it only shows when the OS
  clock moves).
* **`sleep(0)`.** `sleep(delay <= 0)` yields `None` once and is rescheduled with `call_soon`,
  matching CPython's "yield control to the loop" behavior; it does not read or advance the
  clock. `sleep(0.01)` uses a timer at `now + 10_000_000` ns.

Integer nanoseconds, not floats, are the deadline key, so equal delays inserted in the same
turn keep their insertion order. `loop.time()` is `now_ns / 1e9` for code that asks.

## 4. The subset

The names below are the complete public surface of the shipped package. CPython 3.12's
`asyncio.__all__` has 96 names; every one is either listed as working in `ffasync1`, listed as
`ffasync2`, or listed as refused forever, so there is no "unknown name silently behaves like
something else" path. A missing name is a named refusal, not a silently absent attribute.

### 4.1 Works in ffasync1

Module functions and classes:

`run`, `sleep`, `create_task`, `gather`, `wait_for`, `ensure_future`, `current_task`,
`all_tasks`, `get_running_loop`, `get_event_loop`, `Future`, `Task`, `CancelledError`,
`InvalidStateError`, `TimeoutError`, `Queue`, `QueueFull`, `QueueEmpty`, `Event`, `Lock`,
`Handle`, `TimerHandle`.

Methods on those objects:

* `Future` / `Task`: `done`, `cancelled`, `cancel`, `result`, `exception`, `set_result`,
  `set_exception`, `add_done_callback`, `remove_done_callback`; `Task.get_coro`,
  `Task.get_name` (the name is fixed at creation; no `set_name`).
* loop: `call_soon`, `call_at`, `call_later`, `create_future`, `create_task`, `time`,
  `run_until_complete`, `run_forever`, `stop`, `close`.
* `Queue`: `put`, `put_nowait`, `get`, `get_nowait`, `qsize`, `empty`, `full`, `task_done`,
  `join`.
* `Event`: `set`, `clear`, `is_set`, `wait`.
* `Lock`: `acquire`, `release`, `locked`.

`get_event_loop()` works only while a loop is running (`asyncio.run`); outside a loop it raises
`RuntimeError`, and `set_event_loop`/`new_event_loop` are not built. `run()` may be called once
at a time; nested `run()` is a `RuntimeError`.

`CancelledError` derives from `BaseException`; `TimeoutError` and `InvalidStateError` derive
from `Exception`. `asyncio.TimeoutError` is the package's own exception, not a subclass of the
builtin `TimeoutError` (the general path does not have the builtin class). This is recorded as
an A-number when the feature lands.

### 4.2 Works in ffasync2

These are the single-threaded, in-process pieces deliberately left out of ffasync1:

`iscoroutine`, `iscoroutinefunction`, `isfuture`, `wait`, `FIRST_COMPLETED`, `FIRST_EXCEPTION`,
`ALL_COMPLETED`, `as_completed`, `shield`, `Semaphore`, `BoundedSemaphore`, `Condition`,
`Barrier`, `BrokenBarrierError`, `PriorityQueue`, `LifoQueue`, `TaskGroup`, `Runner`, `Timeout`,
`timeout`, `timeout_at`.

In ffasync1 every one of these is refused with:
`asyncio.<name> is not in ffasync1.\n  write instead: <the ffasync1 equivalent>; ffasync2 adds <name>`.
Examples: `wait` -> `gather` with `return_exceptions=True`; `as_completed` -> `gather`;
`Semaphore` -> `Lock`; `TaskGroup` -> `gather` plus explicit `cancel`; `timeout` -> `wait_for`.

### 4.3 Refused forever (ffasync1 and ffasync2)

These need an event-loop policy, child processes, threads, sockets/streams, transports or
private internals the AIL runtime does not have. They are refused by name, never lowered to a
different meaning:

`BaseEventLoop`, `AbstractEventLoop`, `AbstractEventLoopPolicy`, `DefaultEventLoopPolicy`,
`SelectorEventLoop`, `get_event_loop_policy`, `set_event_loop_policy`, `set_event_loop`,
`new_event_loop`, `_set_running_loop`, `_get_running_loop`, `get_child_watcher`,
`set_child_watcher`, `AbstractChildWatcher`, `SafeChildWatcher`, `FastChildWatcher`,
`PidfdChildWatcher`, `MultiLoopChildWatcher`, `ThreadedChildWatcher`,
`create_eager_task_factory`, `eager_task_factory`, `_register_task`, `_unregister_task`,
`_enter_task`, `_leave_task`, `run_coroutine_threadsafe`, `wrap_future`, `to_thread`,
`Server`, `AbstractServer`, `StreamReader`, `StreamWriter`, `StreamReaderProtocol`,
`open_connection`, `start_server`, `open_unix_connection`, `start_unix_server`,
`create_subprocess_exec`, `create_subprocess_shell`, `SubprocessProtocol`, `BaseProtocol`,
`Protocol`, `DatagramProtocol`, `BufferedProtocol`, `BaseTransport`, `ReadTransport`,
`WriteTransport`, `Transport`, `DatagramTransport`, `SubprocessTransport`,
`IncompleteReadError`, `LimitOverrunError`, `SendfileNotAvailableError`.

The refusal template is:
`asyncio.<name> is not built: <threads | child processes | sockets/transports | event-loop policies | private internals> are not available in this language.\n  write instead: <a blocking call from the file/process/http layer, or one of the built names>`.

A name that is not in CPython 3.12's `asyncio.__all__` is refused as
`asyncio.<name> is not a name in CPython 3.12's asyncio; this package builds the names in its __all__ only`.

### 4.4 Syntax refusals

Even with the asyncio package, these forms stay refused:

* `async def` with `yield`/`yield from` (async generators);
* `async for`, `async with`, async comprehensions;
* `await` outside an async function;
* decorators on `async def` (the decorator would receive a `def` returning `_Coro`, not a
  coroutine function; named, not silent);
* `asyncio.run` with a non-coroutine, a second concurrent `run`, and `run` from inside a
  running loop;
* `Task.throw`, `Task.uncancel`, `Task.cancelling`, `Task.get_stack`, `Task.print_stack`
  (not in ffasync1; `throw` also hits the generator-path refusal above);
* `loop.run_in_executor`, `loop.set_default_executor`, `loop.add_reader`, `loop.add_writer`,
  `loop.create_connection`, `loop.create_server`, `loop.connect_accepted_socket`,
  `loop.create_datagram_endpoint`, `loop.subprocess_exec`, `loop.subprocess_shell`,
  `loop.add_signal_handler`.

## 5. Cost: no-async C stays byte-identical

The pass and the package are both gated on syntax, not on the import alone:

* `asynclib.rewrite_tree` immediately returns `False` when the tree has no `AsyncFunctionDef`
  and no `Await`. It does not add a prelude, a primitive, a name or a line.
* `filelib.rewrite_tree` sets `ACTIVE` only when a lowerer actually used something
  (`filelib.py:145`). An untouched async pass therefore leaves the existing file/process/URL
  behavior exactly as it was.
* `AIL_CURRENT/stdlib/asyncio/` is a bundled directory, and `ail_modules.Program` currently
  appends `BUNDLED_DIR` unconditionally (`ail_modules.py:288`). The gate is a named set in
  `ail_modules`, for example `GATED_BUNDLED = {'asyncio'}`: when `Program.spec`/`load` is
  asked for a gated top-level name, it returns `None` unless the program has an
  `AsyncFunctionDef` (checked in the entry and in every local module parsed so far; a dynamic
  import is refused by name). With the gate closed, `import asyncio` keeps today's exact
  behavior: the general path's "import of 'asyncio' is not available" note and the same C.
* The gate is deliberately **not** "does the program import asyncio". A no-async program that
  merely imports it must not grow the package's C. This is the difference between the absolute
  claim and a weaker "does not use async" claim.

Measurements on this tree (base commit `8bc4b00`), generated `program.c` with `--debug-dir`:

| source | C bytes | SHA-256 (first 16) |
| --- | ---: | --- |
| `def main(): print("hi")` | 135,355 | `71d697f5f4ee5111` |
| same plus unused `import shlex` | 870,613 | `4ea0085a0b125028` |
| same plus unused `import asyncio` (today) | 561,130 | `96186ea95455563a` |

The `shlex` row shows what an ungated bundled module costs: a program that does not use it is
merged anyway, and the C grows by 735,258 bytes. The `asyncio` row shows the current baseline
the gate must preserve for a program with no `async def`; it is already on the general path
because the import is currently refused. With the gate, the `asyncio` row stays 561,130 bytes
and its exact note, not 561,130 plus the package. After ffasync1, a program with `async def`
is expected to change C (it now has a coroutine and a loop), and a program without it is
expected not to change at all.

The regression check for ffasync1 is: compile every `lab/compare/*/main.py` and `main.ail`
with the base and the new compiler and compare `program.c` byte for byte on every build that
succeeds, exactly as `docs/design/TUPLE_REACH.md` did (17 builds). Add the twelve labs in a
second group: today all twelve fail identically; after ffasync1 all twelve build and match
CPython, and the no-async group is unchanged.

## 6. The twelve labs

Each program is ordinary Python 3.12. `expected/<name>.txt` is stdout followed by one line
`exit: N`; the model and CPython both match all twelve. "Today" is the default compiler.

| id | feature | expected stdout (last line is `exit: 0`) | today |
| --- | --- | --- | --- |
| l01 | call_soon FIFO, `sleep(0)` turns | `main`, `callback-1`, `callback-2`, `after-sleep-0`, `callback-3`, `after-sleep-0-again` | refused `async def` |
| l02 | timer heap order, ties by insertion | `b`, `d`, `a`, `c` | refused `async def` |
| l03 | gather completion vs result order | `finish b`, `finish a`, `finish c`, `results ['a', 'b', 'c']` | refused `async def` |
| l04 | gather exception, siblings continue | `ok`, `bad`, `caught boom`, `done` | refused `async def` |
| l05 | wait_for timeout cancels the child | `slow cancelled`, `timeout`, `done` | refused `async def` |
| l06 | wait_for success | `42` | refused `async def` |
| l07 | bounded Queue and join | `put 0`, `got 0`, ..., `qsize 0` | refused `async def` |
| l08 | Event broadcast | `first waiting`, `second waiting`, `set`, `first running`, `second running` | refused `async def` |
| l09 | Lock FIFO | first/second/third acquired+released | refused `async def` |
| l10 | cancel inside try/finally | `worker start`, `worker cancelled`, `worker finally`, `cancelled at main`, `done` | refused `async def` |
| l11 | int boundary at 2**63 | `[9223372036854775807, 9223372036854775808]`, `9223372036854775808` | refused `async def`; also int64 |
| l12 | cancel a lock waiter | `holder acquired`, `waiter cancelled`, `holder releasing`, `locked False` | refused `async def` |

`l11` is not an async bug. It crosses `INT64_MAX`: default AIL would stop loudly at
`9223372036854775808`, while CPython prints it. ffasync1 acceptance must either build the lab
with `--exact-int` or record that one lab as a declared loud stop; silently wrapping would be
wrong. The recommendation is `--exact-int` for l11, so the async group is eleven default
builds plus one exact-int build, and no int semantics are changed by the async work.

## 7. Implementation order for ffasync1

1. Add `AIL_CURRENT/stdlib/asyncio/` (a package: `__init__.py`, `_core.py`, `_loop.py`,
   `_tasks.py`, `_sync.py`) in the subset both paths already build. It is ordinary AIL source
   with `def` + `yield`, no `async def`. The package must not import sockets, threads or
   subprocess.
2. Add `asynclib.py` and call it from `filelib.rewrite_tree` before the path/process/url
   lowerers. It handles only `AsyncFunctionDef`, `Await`, `AsyncFor`, `AsyncWith`, async
   comprehensions and the async-generator refusal; it leaves every other tree untouched.
3. Add the gate in `ail_modules` for the `asyncio` top-level name (entry + local modules scan).
4. Add the regenerated manifest by `python3 tools/update_manifest.py` (the tool, not by hand).
5. Add `test_ail_asyncio.py`: the twelve transcripts, the no-async C byte-identity group, the
   refusal matrix in section 4, and CPython parity for each `ffasync1` name. Keep the model and
   `run_model.py` as the oracle for this note.

## 8. Open owner decisions

* **l11 and int64.** `--exact-int` for the one lab, or a declared loud stop? Recommendation:
  `--exact-int`; do not change int rules for async.
* **Monotonic clock.** Use `time.time_ns()` (A28, pinned) and document the wall-clock caveat,
  or add `time.monotonic_ns()` to A28 first? Recommendation: A28 as-is for ffasync1.
* **`get_event_loop`.** The subset returns the running loop and refuses outside one, rather
  than CPython 3.12's deprecated auto-creating behavior. Recommendation: keep the refusal.
* **`asyncio.TimeoutError`.** The package's own class (general path has no builtin
  `TimeoutError`) vs adding the builtin class. Recommendation: package class, recorded as an
  A-number; `except asyncio.TimeoutError` is the supported spelling.
* **Streams and subprocess.** Keep them permanent refusals (no socket/transport layer in AIL)
  rather than promise them in ffasync2. Recommendation: permanent, as section 4.3.

## 9. Evidence

Model and CPython:

```
$ python3 lab/asyncio/model/run_model.py
ok l01_call_soon_fifo.py (model)
...
12/12 matched

$ python3 lab/asyncio/model/run_model.py --oracle
ok l01_call_soon_fifo.py (CPython)
...
12/12 matched
```

Current compiler, default and strict:

```
$ python3 -B AIL_CURRENT/ail_chatgpt.py compile lab/asyncio/l01_call_soon_fifo.py -o /tmp/l01
lab/asyncio/l01_call_soon_fifo.py:4:1: not in the subset: async def: this language has no coroutines or event loop.
  write instead: an ordinary `def`

$ python3 -B AIL_CURRENT/ail_chatgpt.py compile lab/asyncio/l01_call_soon_fifo.py -o /tmp/l01 --strict
lab/asyncio/l01_call_soon_fifo.py:1:1: not in the subset: import of 'asyncio' is not available: ...
```

The generator-form table in section 1.1 was taken by compiling `/tmp/gprobes/*.py` both ways;
the exact texts are quoted there. The C measurements in section 5 used
`--debug-dir` on `/tmp/cost/plain.py`, `/tmp/cost/unused.py` and `/tmp/gprobes/impasyncio.py`.

## 10. What this note does not claim

* It does not change the compiler, add `asynclib.py`, or add `AIL_CURRENT/stdlib/asyncio/`.
* It does not claim the typed path builds generators: `--strict` and `AIL_NO_GENERAL=1` still
  refuse the lowered programs. The default build (typed first, general fallback) is the
  ffasync1 target.
* It does not cover threads, sockets, streams, subprocesses, signals, child watchers, event
  loop policies, async generators or async context managers. Those are named refusals.
* It does not make l11 pass without an int decision (section 6).
* It does not reproduce CPython's "Task exception was never retrieved" warning; an unawaited
  task's exception is discarded when the loop closes. If that warning is wanted, it is an
  ffasync2 addition.

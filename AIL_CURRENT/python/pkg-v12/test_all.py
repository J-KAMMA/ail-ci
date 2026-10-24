"""One suite over the whole thing: the back end, both front ends, the arithmetic, the boundary.

Three kinds of check, and the third is the one that matters most.

  correctness   compiled answers against CPython running the same source, because the claim is
                "it means what Python means" and only Python can settle that
  boundaries    empty input, a filter that rejects everything, a fold with no elements, the values
                where Python's arithmetic and C's part company -- the places an implementation's own
                types and loop bounds break, which the prose never mentions
  refusals      everything outside the subset must be refused by name. A compiler that guesses is
                worse than one that stops.

    python3 test_all.py
"""
import array, ctypes, os, subprocess, sys, tempfile, pathlib

from pipeline import PipelineError, compiler, pipe
from pyfront import Unsupported, pipe_py
from pyfunc import compile_fn, to_c as pyfunc_to_c
import pyc

# The unary spelling now emits an in-range C expression. Positive 2**63 remains a compile-time
# refusal, while these cases exercise the run-time guards on INT64_MIN (`ck_neg`, `pydiv`).
INT64_MIN_SRC = '-9223372036854775808'

FAILED = []
DIVERGES = []       # inputs where Python raises and the compiled code answers instead


def check(what, got, want):
    if got != want:
        FAILED.append('%-52s got %r, wanted %r' % (what, got, want))


def refuses(what, fn):
    try:
        fn()
    except Unsupported:
        return
    except PipelineError as e:
        FAILED.append('%-52s raised %s, wanted Unsupported' % (what, type(e).__name__))
        return
    except Exception as e:
        FAILED.append('%-52s raised %s, wanted Unsupported' % (what, type(e).__name__))
        return
    FAILED.append('%-52s was accepted, wanted Unsupported' % what)


def like_python(src, *inputs, strict=False):
    """CPython is the oracle; a single disagreement is a failure."""
    ns = {}
    if src.lstrip().startswith('def '):
        exec(src, ns)
        name = src.split('(')[0].split('def ')[1].strip()
        ref, compiled = ns[name], compile_fn(src, strict=strict)
        oracle, run, label = (lambda d: ref(list(d))), (lambda d: compiled(list(d))), name
    else:
        f = pipe_py(src, strict=strict)
        oracle = lambda d: int(eval(src, {'xs': list(d)}))
        run = lambda d: f(array.array('q', d))
        label = src
    for d in inputs:
        try:
            want = oracle(d)
        except Exception as e:
            # Python refuses; there is no reference to compare against, and answering anyway is a
            # divergence that belongs in the report rather than in silence.
            DIVERGES.append('%-34s on %-12s python raises %-18s this returns %s'
                            % (label, repr(list(d)[:5]), type(e).__name__, run(d)))
            continue
        check('%s over %r' % (label, list(d)[:8]), run(d), want)


EDGE = ([], [0], [1], [-1], [5, 5, 5], [-3, -3], [1, -1, 1, -1], [0, 5, 0, -5],
        [1, 2, 3, 4, 5], [5, 4, 3, 2, 1], [-7, -1, 5], [2, 2, 3, 3, 1, 1])


def expressions():
    for src in ('sum(xs)', 'min(xs)', 'max(xs)',
                'sum(v*v for v in xs if v % 2)',
                'sum(v for v in xs if -50 <= v <= 50)',
                'sum(1 for v in xs if v < 0)',
                'sum(3*v + 1 for v in xs if not v % 2)',
                'int(0 in xs)',
                'int(all(v < 10000 for v in xs))',
                'sum(v < 0 for v in xs)'):
        like_python(src, *EDGE)
    # max/min of nothing have no answer; the sentinel is documented, not invented
    check('max of an empty source', pipe_py('max(xs)')(array.array('q', [])), -2 ** 63)
    check('min of an empty source', pipe_py('min(xs)')(array.array('q', [])), 2 ** 63 - 1)


def functions():
    like_python('''def run(xs):
    best = cur = 0
    for v in xs:
        cur = cur + 1 if v < 0 else 0
        if cur > best:
            best = cur
    return best''', *EDGE)
    like_python('''def run(xs):
    if not xs:
        return 0
    total = 0
    for v in xs[1:]:
        total += v
    return total''', *EDGE)
    like_python('''def run(xs):
    total = 0
    for v in xs:
        if v == 0:
            break
        total += v
    return total''', *EDGE)
    like_python('''def run(xs):
    if not xs:
        return -1
    best = 0
    for i in range(len(xs)):
        if xs[i] > xs[best]:
            best = i
    return best''', *EDGE)
    like_python('''def run(xs):
    a, b = 0, 1
    for i, v in enumerate(xs):
        a, b = b, a + v
    return b''', *EDGE)
    like_python('''def run(xs):
    n = 0
    i = 0
    while i < len(xs):
        if xs[i] > 0:
            n += 1
        i += 1
    return n''', *EDGE)


def arithmetic():
    """Where C and Python part company, strict mode must follow Python."""
    for src in ('sum(v % 3 for v in xs)', 'sum(v // 3 for v in xs)',
                'sum(-v for v in xs)', 'max(abs(v) for v in xs)'):
        like_python(src, [-7, -1, 5], [-1], [3, 3], strict=True)
    # and without it, C's rules are what you get -- stated, not hidden
    check('C rules on (-7) % 3', pipe_py('sum(v % 3 for v in xs)')(array.array('q', [-7])), -1)
    check('Python rules on (-7) % 3',
          pipe_py('sum(v % 3 for v in xs)', strict=True)(array.array('q', [-7])), 2)


def overflow():
    """Under strict, a wrong number becomes an error instead."""
    src = pyc.to_c('sum(v for v in xs)', strict=True) + '''
#include <stdio.h>
int main(void){ int64_t a[3] = {4611686018427387904LL, 4611686018427387904LL,
                                4611686018427387904LL};
    printf("%lld\\n", (long long)run(a, 3)); return 0; }
'''
    with tempfile.TemporaryDirectory() as d:
        c = pathlib.Path(d) / 'a.c'
        c.write_text(src)
        exe = pathlib.Path(d) / 'a'
        subprocess.run([compiler(), '-O2', '-o', str(exe), str(c)], check=True, capture_output=True)
        r = subprocess.run([str(exe)], capture_output=True, text=True)
        check('overflow exits non-zero', r.returncode != 0, True)
        check('overflow says why', 'overflow' in r.stderr, True)


def containers():
    """A list, a set and a dict, and the two-argument shape. All of these allocate."""
    like_python('''def run(xs):
    seen = set()
    for v in xs:
        seen.add(v)
    return len(seen)''', *EDGE)
    like_python('''def run(xs):
    counts = {}
    for v in xs:
        counts[v] = counts.get(v, 0) + 1
    best = 0
    for k in counts:
        if counts[k] > best:
            best = counts[k]
    return best''', *EDGE)
    like_python('''def run(xs):
    out = []
    for v in xs:
        if v > 0:
            out.append(v)
    return len(out)''', *EDGE)
    like_python('''def run(xs):
    s = sorted(xs)
    if not s:
        return 0
    return s[len(s) // 2]''', *EDGE)
    like_python('''def run(xs):
    seen = set()
    best = 0
    for v in xs:
        if v in seen:
            seen.remove(v)
        else:
            seen.add(v)
        if len(seen) > best:
            best = len(seen)
    return best''', *EDGE)
    like_python('''def run(xs):
    counts = {}
    for v in xs:
        counts[v] = counts.get(v, 0) + 1
    return sum(k for k, c in counts.items() if c == 1)''', *EDGE)
    like_python('''def run(xs):
    best = None
    for v in xs:
        if best is None or v < best:
            best = v
    if best is None:
        return 0
    return best''', *EDGE)
    # two parameters, and one of them an int rather than an array
    f = compile_fn('''def run(xs, k):
    n = 0
    for v in xs:
        if v > k:
            n += 1
    return n''')
    check('two parameters', f([1, 5, 9], 4), 2)
    g = compile_fn('''def run(xs, ys):
    return len(set(xs) & set(ys))''')
    check('two arrays and a set intersection', g([1, 2, 3, 3], [3, 2, 9]), 2)


def floats_and_calls():
    """Two types and several functions -- and `/` is the one that would have been silently wrong."""
    like_python('''def mean(xs):
    if not xs:
        return 0.0
    return sum(xs) / len(xs)''', *EDGE)
    # a function that calls another, which is how the mean gets reused
    src = '''def mean(xs):
    if not xs:
        return 0.0
    return sum(xs) / len(xs)


def variance(xs):
    if not xs:
        return 0.0
    m = mean(xs)
    return sum((x - m) ** 2 for x in xs) / len(xs)'''
    ns = {}
    exec(src, ns)
    f = compile_fn(src, entry='variance')
    for d in EDGE:
        check('variance over %r' % d[:6], f(list(d)), ns['variance'](list(d)))
    # an int local that later holds a float is a float, as it is in Python
    like_python('''def run(xs):
    smoothed = 0.0
    first = 1
    for v in xs:
        if first:
            smoothed = float(v)
            first = 0
        else:
            smoothed = 0.3 * v + 0.7 * smoothed
    return smoothed''', *EDGE)
    check('int // stays an int', compile_fn(
        'def run(xs):\n    if not xs:\n        return 0\n    return sum(xs) // len(xs)')([7, 8]), 7)
    check('but / is a float', compile_fn(
        'def run(xs):\n    if not xs:\n        return 0.0\n    return sum(xs) / len(xs)')([7, 8]),
        7.5)


def floor_and_width():
    """Two places an outside audit found the compiler disagreeing with its own SEMANTICS.md, both
    on values this suite had never made: `%` and `//` truncated toward zero instead of flooring
    whenever the operands' signs differed (the existing `arithmetic()` test above only ever mixed
    a negative dividend with a positive divisor under the *filter* `v % 3`, and every other case
    used same-sign operands), and a small integer literal was emitted as a 32-bit C `int`, so a
    wide shift was undefined behaviour rather than a 64-bit value. Both are permanent from here,
    for every sign combination and in the default (non-strict) mode -- unlike overflow-trapping
    for `+ - *`, flooring is not gated behind `strict`."""
    f_mod = compile_fn('def run(x, y):\n    return x % y\n')
    f_div = compile_fn('def run(x, y):\n    return x // y\n')
    for a, b in ((-7, 3), (7, -3), (-7, -3), (7, 3), (-8, 3), (-1, 3), (1, -3),
                 (0, 5), (0, -5), (-1, 1), (1, -1), (-1, -1)):
        check('def-compiled %d %% %d floors' % (a, b), f_mod(a, b), a % b)
        check('def-compiled %d // %d floors' % (a, b), f_div(a, b), a // b)

    # Division/modulo by zero, and the one overflow flooring introduces: INT64_MIN // -1 has no
    # int64 answer (the exact result is 2**63), so it traps rather than silently wrapping -- the
    # same rule section 1 already applies to + - * and abs(INT64_MIN).
    _traps('modulo by zero', 'def run(xs):\n    for v in xs:\n        pass\n    return 7 % 0\n',
           'modulo by zero')
    _traps('floor division by zero',
           'def run(xs):\n    for v in xs:\n        pass\n    return 7 // 0\n', 'division by zero')
    _traps('INT64_MIN // -1 overflows',
           'def run(xs):\n    for v in xs:\n        pass\n    return (%s) // -1\n' % INT64_MIN_SRC,
           'overflow')

    # A literal small enough to be a C `int` must still act as a 64-bit value: `1 << 40` was
    # computed in 32 bits (undefined behaviour in the generated C) and answered 0.
    shift = compile_fn('def run(n):\n    return 1 << n\n')
    check('1 << 31 (literal is 64-bit)', shift(31), 1 << 31)
    check('1 << 40 (literal is 64-bit)', shift(40), 1 << 40)
    check('1 << 62 (literal is 64-bit)', shift(62), 1 << 62)
    lit_shift = compile_fn('def run(xs):\n    for v in xs:\n        pass\n    return 1 << 40\n')
    check('1 << 40 with no variable operand', lit_shift([0]), 1 << 40)


def boundary():
    """Outside the subset, refused by name. This is the design, not a gap in it."""
    # `a = [1]; return a[0]` -- a list literal WITH CONTENTS -- left this list on 2026-09-14,
    # alongside `list.pop()` / `list.pop(i)`, added the same day. SEMANTICS.md section 5 has the
    # trade: what changed, and what a nested literal, a float element, and `pop()` with more than
    # one argument still refuse, by name, after the change. This was not a standalone itch --
    # sealed blind list C tasks #24 (printer simulation), #29 (FIFO share matching), #36
    # (flood-fill over a grid) and #40 (balanced brackets via a stack) were blocked on exactly
    # these two constructs together, named in BLIND_TASKS_40_C_SEALED.md. What used to be a
    # `refuses(...)` entry here is now a `check(...)` entry: the assertion this suite makes about
    # this exact source changed direction, and is not silently dropped -- see `test_pop.py` at the
    # top of `probe26/` for the full judge (CPython-oracle correctness, the empty-pop and
    # out-of-range traps, and the boundary cases that are still refused).
    check('a list literal with contents is accepted and reads back correctly',
          compile_fn('def run(xs):\n    a = [1]\n    return a[0]')(0), 1)
    # a dict has no .remove and no .discard; accepting them was found by an audit, not by this
    refuses('dict.remove', lambda: compile_fn(
        'def run(xs):\n    d = {}\n    for v in xs:\n        d[v] = 1\n    d.remove(1)\n'
        '    return len(d)'))
    refuses('dict.discard', lambda: compile_fn(
        'def run(xs):\n    d = {}\n    for v in xs:\n        d[v] = 1\n    d.discard(1)\n'
        '    return len(d)'))
    # a scalar parameter used only as min/max's second argument is a number, not a sequence
    f = compile_fn('def run(xs, k):\n    m = 0\n    for v in xs:\n        m = m + min(v, k)\n'
                   '    return m')
    check('a scalar second argument to min', f([5, 1], 3), 4)
    g = compile_fn('def run(xs, k):\n    m = 0\n    for v in xs:\n        m = m + max(v, k)\n'
                   '    return m')
    check('a scalar second argument to max', g([5, 1], 3), 8)
    # 2026-09-14, owner decision: a `str` is no longer refused -- see SEMANTICS.md section 29,
    # and `test_str.py` at the top of `probe26/` for the full judge (CPython as the oracle on
    # len/index/slice/compare/concat, non-ASCII throughout, plus a named negative case for every
    # operation that stays refused). This line used to be `refuses('a string', ...)`; the same
    # treatment the recursion lines below already got is applied here rather than deleting it --
    # the construct that now works becomes a correctness check, and the half of the old guarantee
    # that did NOT change keeps a refusal of its own.
    check('a str literal is accepted and does not disturb the answer',
          compile_fn('def run(xs):\n    a = "x"\n    return 0')(0), 0)
    check('len() of a str literal is the CODE POINT count, as CPython\'s is',
          compile_fn('def run(xs):\n    return len("caf\u00e9")')(0), len('caf\u00e9'))
    refuses('a str as a container element',
            lambda: compile_fn('def run(xs):\n    a = ["x"]\n    return len(a)'))
    refuses('a str used as a number',
            lambda: compile_fn('def run(xs):\n    a = "x"\n    return a + 1'))
    refuses('a float', lambda: pipe_py('sum(v * 1.5 for v in xs)'))
    refuses('a second array in an expression', lambda: pipe_py('sum(v for v in ys)'))
    refuses('two for-clauses', lambda: pipe_py('sum(a*b for a in xs for b in xs)'))
    refuses('a free variable', lambda: pipe_py('sum(v * k for v in xs)'))
    refuses('reading before assigning', lambda: compile_fn('def run(xs):\n    return q'))
    # AIL_TASK_callconv_20260915.md: a function with no return VALUE anywhere -- a bare `return`
    # or no `return` at all -- is no longer refused; it is NORET, compiled as a `void` C function
    # (see test_callconv.py for the full judge). These two lines used to assert `refuses(...)`;
    # the guarantee got stronger, not smaller, so they are now a correctness check instead of
    # being deleted, the same treatment recursion got just below. Called through `compile_fn`'s
    # ctypes wrapper, whose `restype = None` for a NORET function is ctypes' own spelling of "no
    # value" -- exactly what a call returns here.
    noret_bare = compile_fn('def run(xs):\n    return')
    check('a bare return, now accepted (NORET)', noret_bare(0), None)
    noret_none = compile_fn('def run(xs):\n    a = 1')
    check('no return at all, now accepted (NORET)', noret_none(0), None)
    # 2026-09-14, owner decision: recursion is no longer refused -- see SEMANTICS.md section 2.
    # These two lines used to assert `refuses(...)` here; the guarantee got stronger, not smaller,
    # so they are now a correctness check on the accepted construct instead of being deleted --
    # the full behavioural judge, over many more programs and CPython as the oracle throughout,
    # is test_recursion.py.
    rec = compile_fn('def run(n):\n    if n <= 1:\n        return 1\n'
                     '    return n * run(n - 1)')
    check('self-recursion (factorial), now accepted', rec(10), 3628800)
    mrec = compile_fn(
        'def a(n):\n    if n == 0:\n        return 1\n    return b(n - 1)\n'
        'def b(n):\n    if n == 0:\n        return 0\n    return a(n - 1)', entry='a')
    check('mutual recursion, now accepted (a(7))', mrec(7), 0)
    check('mutual recursion, now accepted (a(8))', mrec(8), 1)
    refuses('not an expression', lambda: pipe_py('sum(xs'))
    refuses('a slice with a step', lambda: compile_fn(
        'def run(xs):\n    t = 0\n    for v in xs[::2]:\n        t += v\n    return t'))
    refuses('a name that changes type', lambda: compile_fn(
        'def run(xs):\n    a = 0\n    a = set()\n    return 0'))
    refuses('a list of lists', lambda: compile_fn(
        'def run(xs):\n    a = []\n    a.append([])\n    return 0'))
    # `None` can be held but not returned: the result of a compiled function is an int and nothing
    # else. This runs in its own process, because the trap stops the program rather than raising.
    # each of these touches `xs`, because a parameter a function never uses cannot be told from an
    # int and would compile to a different signature than the harness calls
    _traps('returning None',
           'def run(xs):\n    a = None\n    for v in xs:\n        a = v\n    return a', 'None')
    _traps('a missing key',
           'def run(xs):\n    d = {}\n    for v in xs:\n        d[v] = 1\n    return d[7]',
           'key error')
    _traps('remove of an absent element',
           'def run(xs):\n    s = set()\n    for v in xs:\n        s.add(v)\n'
           '    s.remove(7)\n    return 0', 'key error')
    _traps('max of nothing',
           'def run(xs):\n    d = {}\n    for v in xs:\n        if v > 99:\n            d[v] = 1\n'
           '    return max(d)', 'empty')


def _traps(what, src, wanted, strict=False):
    """Compile to a standalone program and check it stops, and says why."""
    c = pyfunc_to_c(src, name='run', strict=strict) + '''
#include <stdio.h>
int main(void){ int64_t a[1] = {0}; printf("%lld\\n", (long long)run(a, 0)); return 0; }
'''
    with tempfile.TemporaryDirectory() as d:
        f = pathlib.Path(d) / 'a.c'
        f.write_text(c)
        exe = pathlib.Path(d) / 'a'
        r = subprocess.run([compiler(), '-O2', '-o', str(exe), str(f)],
                           capture_output=True, text=True)
        if r.returncode:
            FAILED.append('%-52s did not compile' % what)
            return
        out = subprocess.run([str(exe)], capture_output=True, text=True)
        check('%s stops the program' % what, out.returncode != 0, True)
        check('%s says why' % what, wanted in out.stderr, True)


def _runs_ok(what, src, want, strict=False):
    """Compile to a standalone program and check it exits *cleanly*, with the right answer.

    The mirror image of `_traps`: used where a wrong boundary constant could make the compiled
    program trap when it should not. Run in a subprocess, like `_traps`, rather than through
    `compile_fn`'s in-process ctypes call -- a boundary bug here would otherwise call `_Exit(1)`
    inside the test process itself and take the rest of the suite down with it.
    """
    c = pyfunc_to_c(src, name='run', strict=strict) + '''
#include <stdio.h>
int main(void){ int64_t a[1] = {0}; printf("%lld\\n", (long long)run(a, 0)); return 0; }
'''
    with tempfile.TemporaryDirectory() as d:
        f = pathlib.Path(d) / 'a.c'
        f.write_text(c)
        exe = pathlib.Path(d) / 'a'
        r = subprocess.run([compiler(), '-O2', '-o', str(exe), str(f)],
                           capture_output=True, text=True)
        if r.returncode:
            FAILED.append('%-52s did not compile' % what)
            return
        out = subprocess.run([str(exe)], capture_output=True, text=True)
        check('%s exits cleanly' % what, out.returncode, 0)
        check('%s answers correctly' % what, out.stdout.strip(), str(want))


def word_notation():
    """The back end's other front end. It lost the token argument and still has to work."""
    xs = array.array('q', [3, -7, 2, 9, -4, 11])
    check('word: fold', pipe('sum where odd squares over xs')(xs), 260)
    check('word: several folds', pipe('sum, count where negative, max abs over xs')(xs),
          (14, 2, 11))
    out = array.array('q', [0] * 8)
    m = pipe('sort abs over xs into ys')(xs, out=out)
    check('word: collect and sort', list(out[:m]), [2, 3, 4, 7, 9, 11])


def churn():
    """A sliding window: a small live set and a long churn.

    Growth used to be triggered by the live count alone, so a set that never held more than a few
    keys never grew while every removal left a tombstone and every new key consumed an empty slot.
    At 2,000 values the empties ran out and the probe for an absent key never terminated. Two
    smaller attempts to reproduce that had already come back clean, which is why the size here is
    not negotiable.
    """
    src = '''def run(xs):
    s = set()
    hits = 0
    for v in xs:
        s.add(v)
        if v - 3 in s:
            s.discard(v - 3)
        if v + 99999999 in s:
            hits += 1
    return hits + len(s)'''
    ns = {}
    exec(src, ns)
    f = compile_fn(src)
    for n in (200, 2000, 5000):
        d = list(range(n))
        check('a churning set over %d values' % n, f(d), ns['run'](d))


def hash_table_growth():
    """Mutation-audit gap 1: `ail_tab_grow` (cruntime.py) runs 22 times across the whole suite and
    every call has `old.n == 3, old.cap == 16` -- the capacity-doubling branch is never taken.
    `churn()` above stresses tombstone compaction at a fixed capacity of 16 (a sliding window of
    about four live keys); it never holds more than 16 keys *at once*. This inserts far more
    distinct keys than that, all of them kept live -- nothing discarded -- which forces the table
    past 3/4 of its initial capacity and into at least one real doubling, for both a set and a
    dict."""
    like_python('''def run(xs):
    seen = set()
    for v in xs:
        seen.add(v)
    return len(seen)''', list(range(50)), list(range(-100, 150)), list(range(500)), [7] * 300)
    like_python('''def run(xs):
    counts = {}
    for v in xs:
        counts[v] = counts.get(v, 0) + 1
    return len(counts)''', list(range(60)), list(range(500)))


def memory_leak_under_repeated_calls():
    """Mutation-audit gap 2: SEMANTICS.md section 3 promises "a compiled function called in a loop
    leaks nothing", and nothing in this suite could ever tell -- every check compares one return
    value from one call, and a leaked container does not change what a function returns.

    There is no way to see a leak *from the return value*, so this looks at the process instead: a
    function that builds a real list on every call is called a great many times, and the process's
    own peak resident set is read before and after with `resource.getrusage` on POSIX or
    `GetProcessMemoryInfo` on Windows. Freed memory
    is reused by the allocator, so a leak-free run's RSS is expected to stay essentially flat once
    warmed up; a per-call leak of even a few dozen bytes is designed to become tens of megabytes
    over 200,000 calls, which is far more than allocator noise, page-alignment slop or the
    interpreter's own churn can plausibly account for.

    This is a coarser instrument than a real leak detector: it cannot say *how much* a single call
    leaks, only whether calling the function 200,000 times inflates the process by an amount no
    leak-free implementation should produce. That is the question SEMANTICS.md's sentence actually
    makes a claim about, and it is the only one answerable from inside this suite without adding
    new machinery to the compiled runtime itself (the more precise alternative -- an allocation
    counter compiled into cruntime.py under a test-only flag, incremented in `ail_alloc` and
    decremented in every `_free`, read back through a second exported symbol -- would give an exact
    per-call count, but that is new runtime code, not a test, and is not added here)."""
    def peak_rss_kib():
        if os.name != 'nt':
            import resource
            return resource.getrusage(resource.RUSAGE_SELF).ru_maxrss

        class ProcessMemoryCounters(ctypes.Structure):
            _fields_ = [
                ('cb', ctypes.c_ulong),
                ('PageFaultCount', ctypes.c_ulong),
                ('PeakWorkingSetSize', ctypes.c_size_t),
                ('WorkingSetSize', ctypes.c_size_t),
                ('QuotaPeakPagedPoolUsage', ctypes.c_size_t),
                ('QuotaPagedPoolUsage', ctypes.c_size_t),
                ('QuotaPeakNonPagedPoolUsage', ctypes.c_size_t),
                ('QuotaNonPagedPoolUsage', ctypes.c_size_t),
                ('PagefileUsage', ctypes.c_size_t),
                ('PeakPagefileUsage', ctypes.c_size_t),
            ]

        counters = ProcessMemoryCounters()
        counters.cb = ctypes.sizeof(counters)
        get_process = ctypes.windll.kernel32.GetCurrentProcess
        get_process.restype = ctypes.c_void_p
        get_memory = ctypes.windll.psapi.GetProcessMemoryInfo
        get_memory.argtypes = [ctypes.c_void_p,
                               ctypes.POINTER(ProcessMemoryCounters),
                               ctypes.c_ulong]
        get_memory.restype = ctypes.c_int
        handle = get_process()
        if not get_memory(
                handle, ctypes.byref(counters), counters.cb):
            raise ctypes.WinError()
        return counters.PeakWorkingSetSize // 1024

    f = compile_fn('''def run(xs):
    out = []
    for v in xs:
        if v % 2:
            out.append(v)
    return len(out)''')
    xs = array.array('q', range(200))

    warmup = 5000
    for _ in range(warmup):
        f(xs)
    base = peak_rss_kib()

    calls = 200000
    for _ in range(calls):
        f(xs)
    grown = peak_rss_kib() - base

    limit_kib = 20 * 1024
    check('%d calls building a real list stay under %dMB of RSS growth (grew %dKiB)'
          % (calls, limit_kib // 1024, grown), grown < limit_kib, True)


def chained_comparison():
    """Mutation-audit gap 3: the multi-clause `Compare` join in pyfunc.py's `_expr` (the `def`
    function compiler) executes 18 times across the suite but always with exactly one clause --
    the suite's only chained comparison (`-50 <= v <= 50`) is written as a generator expression
    that goes through pyfront.py's separate expression front end instead, never through a `def`.
    This puts the same shape of chain inside an actual function."""
    like_python('''def run(xs):
    n = 0
    for v in xs:
        if -3 <= v <= 3:
            n += 1
    return n''', *EDGE)
    like_python('''def run(xs):
    n = 0
    for v in xs:
        if 0 <= v < 5:
            n += 1
    return n''', *EDGE)


def slice_bounds_via_assignment():
    """Mutation-audit gap 4: `_slice_bounds()` in pyfunc.py is never called at all -- the suite's
    only slice, `for v in xs[1:]`, goes through a second clamp hand-duplicated into the
    for-statement compiler (`_for`, also in pyfunc.py). The two are meant to agree; nothing checks
    that they do.

    `_slice_bounds` is reached from exactly one other place: binding a slice to a name (`trimmed =
    xs[1:]`), which SEMANTICS.md section 3 says builds a list -- `_stmt`'s assignment handler calls
    `_iter_plan`/`_slice_bounds` and pushes every element into a fresh `ail_list`. That is what
    this exercises.

    (A *third*, more direct-looking route -- `sum(xs[1:])`, or a slice as a generator's source,
    `sum(v for v in xs[1:])` -- also reaches `_iter_plan`/`_slice_bounds`, through `_inline_fold`.
    It does not work at all: see `fold_over_a_slice_is_a_real_bug` below, which is a defect this
    testing effort found, not a gap the audit named.)"""
    like_python('''def run(xs):
    trimmed = xs[1:]
    total = 0
    for v in trimmed:
        total += v
    return total''', *EDGE)


def fold_over_a_slice_is_a_real_bug():
    """Was a genuine defect this testing effort found while closing gap 4 -- not one of the
    audit's eight gaps -- now fixed, and this is the real correctness test the fix calls for.

    `sum(xs[1:])` (and equally `max(xs[1:])`, `sum(v for v in xs[1:])`, any fold over a sliced
    source) used to fail to *compile*, always, regardless of the slice's bounds. `_inline_fold`
    calls `_iter_plan(src, ctx)`, which for a slice returns through `_slice_bounds` -- and
    `_slice_bounds` reports what it needs as *statements* (`pre`), declaring temporaries
    `_slN`/`_shN`, meant to run before the loop they bound. `_inline_fold` used to route that
    `pre` through `ctx.pre`, a bucket it only flushed *after* opening the `for` loop -- inside
    the loop body, and after the header had already used `lo`/`n` (== `_slN`/`_shN`) to build
    itself. For every other iterable `pre` is always empty, which is why this was never noticed:
    nothing before this suite ever folded over a slice. Not a wrong answer -- a C compile error,
    every time:

        pyfunc.py   lo, n, elem, pre = _iter_plan(src, ctx)
                     ctx.pre.extend(pre)              # not used until inside the loop body
                     body.append('for (int64_t %s = %s; %s < %s; %s++) {' % (idx, lo, idx, n, idx))
                     # ^ already uses `lo`/`n` == `_slN`/`_shN`, declared only once `ctx.pre` is
                     #   flushed into `body`, further down -- inside the loop this header opens.

    Fixed by folding `_iter_plan`'s `pre` directly into the statement expression's own `head`
    (which runs once, in the same C block scope, before the `for` header is even built) instead
    of leaving it on `ctx.pre` to be swept into the loop body:
        python3 -c "from pyfunc import compile_fn; compile_fn('def run(xs):\\n    return sum(xs[1:])')"
        now returns a working function instead of raising pipeline.PipelineError.

    So this no longer just checks that the known defect is still there to report -- it checks,
    the same way every other fold in this suite is checked, that a fold over a slice compiles
    AND agrees with CPython, element by element, for `sum`, a generator-expression `sum`, a
    filtered generator-expression `sum`, `max` and `min` alike.

    `max`/`min` over a `def`-style fold that turns out empty does not raise in this compiler the
    way `sum` does -- it TRAPS (`ail_die`, an in-process abort; see `'max of nothing'` above,
    which checks that trap out-of-process via `_traps`). `like_python`'s own divergence branch
    calls the compiled function even when Python raises, so feeding it an `xs` whose `xs[1:]` is
    empty would abort this very test process instead of recording a result -- not a compiler bug,
    but a reason to keep `max`/`min` here to inputs whose slice is never empty, the same
    seatbelt `_traps`/`_runs_ok` wear on purpose elsewhere in this file."""
    like_python('''def run(xs):
    return sum(xs[1:])''', *EDGE)
    like_python('''def run(xs):
    return sum(v for v in xs[1:])''', *EDGE)
    like_python('''def run(xs):
    return sum(v for v in xs[1:] if v > 0)''', *EDGE)
    non_empty_slice = [d for d in EDGE if len(d) >= 2]      # xs[1:] must have at least one element
    like_python('''def run(xs):
    return max(xs[1:])''', *non_empty_slice)
    like_python('''def run(xs):
    return min(xs[1:])''', *non_empty_slice)


def negative_and_variable_slice_bounds():
    """Mutation-audit gap 5: the suite's only slice is `xs[1:]` -- a constant lower bound, the
    upper bound omitted, never negative. Python's slice clamping has several more cases; this
    exercises a negative lower bound, a negative upper bound, both at once, and bounds that are
    ordinary variables rather than literals -- through both places a slice is compiled: the
    for-statement's own inline clamp (`_for`) and `_slice_bounds` (through binding the slice to a
    name, the one other place that reaches it -- see `slice_bounds_via_assignment` above)."""
    for src in (
            '''def run(xs):
    total = 0
    for v in xs[-3:]:
        total += v
    return total''',
            '''def run(xs):
    total = 0
    for v in xs[:-1]:
        total += v
    return total''',
            '''def run(xs):
    total = 0
    for v in xs[2:-1]:
        total += v
    return total''',
            '''def run(xs):
    trimmed = xs[-3:]
    total = 0
    for v in trimmed:
        total += v
    return total''',
            '''def run(xs):
    trimmed = xs[:-1]
    total = 0
    for v in trimmed:
        total += v
    return total''',
            '''def run(xs):
    trimmed = xs[2:-1]
    total = 0
    for v in trimmed:
        total += v
    return total'''):
        like_python(src, *EDGE)

    # bounds that are variables, not literals written into the source
    f = compile_fn('''def run(xs, i, j):
    total = 0
    for v in xs[i:j]:
        total += v
    return total''')
    g = compile_fn('''def run(xs, i, j):
    trimmed = xs[i:j]
    total = 0
    for v in trimmed:
        total += v
    return total''')
    xs = [10, 20, 30, 40, 50, 60]
    for i, j in ((1, 4), (-4, -1), (0, -1), (-100, 100), (3, 1), (-2, 100), (6, 6)):
        want = sum(xs[i:j])
        check('for-loop slice xs[%d:%d] (variable bounds)' % (i, j), f(xs, i, j), want)
        check('slice-to-list xs[%d:%d] (variable bounds)' % (i, j), g(xs, i, j), want)


def enumerate_index_counts_from_zero():
    """Was a genuine defect this testing effort found, in `_inline_pair_fold` (the shared engine
    behind `sum`/`max`/`min`/`any`/`all` over a generator with a two-name target -- `enumerate(e)`,
    `d.items()`, `zip(a, b)`):

        sum(i for i, v in enumerate(range(3, 8)))      CPython 10    compiled (was) 25
        sum(i * v for i, v in enumerate(range(3, 8)))  CPython 60    compiled (was) 135

    `_pair_plan`'s `enumerate` branch handed back the raw loop counter itself (`'@'`) as the index
    expression. That counter runs from the underlying sequence's own first position, not from
    zero -- for an array or a list, or `range()` with no start, those coincide by luck (both are
    0), which is exactly why `sum(i for i, v in enumerate(range(0, 5)))` was never wrong and never
    exposed this. `range(3, 8)`, or any slice that does not start at 0 (`xs[2:]`, `xs[-3:]`), gave
    the raw position instead of a count from zero. Fixed by measuring the index back from the
    source's own start (`@ - lo`) rather than reading it off the counter directly -- see
    `_pair_plan`'s docstring.

    A second, independent defect in the same function is why the first stayed hidden: a slice
    source made `_pair_plan` route `_iter_plan`'s `pre` (the `_slN`/`_shN` declarations
    `_slice_bounds` needs) through `ctx.pre`, which `_inline_pair_fold` only flushed into the loop
    *body* -- after the `for (...)` header had already used `_slN`/`_shN` to build itself. That is
    the exact header-ordering bug `fold_over_a_slice_is_a_real_bug` above documents for the
    single-value `_inline_fold`; `_inline_pair_fold` never got the matching fix, so
    `enumerate(xs[2:])` inside a fold did not silently answer wrong -- it *failed to compile*,
    every time, which is what actually kept the index bug from being noticed here: nothing before
    this suite ever folded a pair over a slice. Fixed the same way `_inline_fold` was: `pre` now
    comes back from `_pair_plan` and is folded into the statement expression's own `head`, which
    runs once, before the loop header is even built.

    Every source shape the compiler supports for a pair fold is exercised here: an array
    parameter, a list, `range()` with and without a start (including variable bounds), and a
    slice (including a negative, non-literal start) -- so a regression in any one of them, not
    just the shape that first showed the bug, is caught."""
    # `xs` is not otherwise used by these four -- `for _ in xs: pass` is filler that gives the
    # compiler evidence to type it as an array, the same way `like_python`'s def-style calling
    # convention (`compiled(list(d))`) already expects, without changing what each source computes
    filler = 'for _ in xs:\n        pass\n    '
    # range() with an actual start -- the shape that showed the bug
    like_python('def run(xs):\n    %sreturn sum(i for i, v in enumerate(range(3, 8)))'
                % filler, *EDGE)
    like_python('def run(xs):\n    %sreturn sum(i * v for i, v in enumerate(range(3, 8)))'
                % filler, *EDGE)
    # range(0, ...) -- unaffected by construction, kept as an explicit regression
    like_python('def run(xs):\n    %sreturn sum(i for i, v in enumerate(range(0, 5)))'
                % filler, *EDGE)
    # the value alone was always right; keep it as a control that isolates the index
    like_python('def run(xs):\n    %sreturn sum(v for i, v in enumerate(range(3, 8)))'
                % filler, *EDGE)

    # range() with variable (non-literal) bounds, including a start other than zero
    f = compile_fn('def run(a, b):\n    return sum(i for i, v in enumerate(range(a, b)))')
    g = compile_fn('def run(a, b):\n    return sum(i * v for i, v in enumerate(range(a, b)))')
    for a, b in ((0, 5), (3, 8), (-4, 3), (7, 7), (5, 6)):
        check('sum(i for i,v in enumerate(range(%d,%d))) (variable bounds)' % (a, b),
              f(a, b), sum(i for i, v in enumerate(range(a, b))))
        check('sum(i*v for i,v in enumerate(range(%d,%d))) (variable bounds)' % (a, b),
              g(a, b), sum(i * v for i, v in enumerate(range(a, b))))

    # an array parameter -- lo == 0 already, the ordinary case, kept as a regression
    like_python('def run(xs):\n    return sum(i for i, v in enumerate(xs))', *EDGE)
    like_python('def run(xs):\n    return sum(i * v for i, v in enumerate(xs))', *EDGE)

    # a list value (not an array parameter) -- also lo == 0, a different code path to the same
    # answer (`_seq` on a LIST rather than the `Name`/RANGE branch of `_iter_plan`)
    like_python('''def run(xs):
    lst = [v for v in xs]
    return sum(i for i, v in enumerate(lst))''', *EDGE)

    # a slice that does not start at zero -- the shape that combined both defects: it used to fail
    # to compile at all (the header-ordering bug), and produced the wrong index once it did
    # compile (the index bug), so this is the one test that would have caught either defect alone
    like_python('def run(xs):\n    return sum(i for i, v in enumerate(xs[2:]))', *EDGE)
    like_python('def run(xs):\n    return sum(i * v for i, v in enumerate(xs[2:]))', *EDGE)
    # a negative, non-literal slice start -- `_slice_bounds` clamps this at run time, not compile
    # time, so `lo` here is a temporary the index has to subtract, not a literal
    like_python('def run(xs):\n    return sum(i for i, v in enumerate(xs[-3:]))', *EDGE)

    # `max`/`min` take the other branch inside `_inline_pair_fold` (no `FOLD_INIT`); a source
    # whose slice is empty has no answer in Python either, so this is restricted to inputs where
    # xs[1:] is non-empty (the same seatbelt `fold_over_a_slice_is_a_real_bug` uses above)
    non_empty_slice = [d for d in EDGE if len(d) >= 2]
    like_python('def run(xs):\n    return max(i for i, v in enumerate(xs[1:]))', *non_empty_slice)
    like_python('def run(xs):\n    return min(i for i, v in enumerate(xs[1:]))', *non_empty_slice)

    # a filter clause must not renumber: Python's enumerate assigns positions before any `if` in
    # the generator gets to see them, so this must keep the *original* index of the elements that
    # pass, not a fresh count of how many have passed so far -- exercised over both a zero-start
    # and a non-zero-start source
    like_python('def run(xs):\n    return sum(i for i, v in enumerate(xs) if v > 0)', *EDGE)
    like_python('''def run(xs):
    return sum(i for i, v in enumerate(range(3, 3 + len(xs))) if v % 2 == 0)''', *EDGE)

    # `.items()` and `zip()` share `_inline_pair_fold` with `enumerate()` -- both already return a
    # real element (a dict key, or the other sequence's own element) rather than a position, so
    # neither had the index defect; these are regressions confirming the shared refactor left them
    # alone, including `zip()` reaching the header-ordering fix through a `sorted()` temporary
    # (`_pair_plan`'s `pre` for `zip` was routed through `ctx.pre` exactly like `enumerate`'s was)
    like_python('''def run(xs):
    counts = {}
    for v in xs:
        counts[v] = counts.get(v, 0) + 1
    return sum(k for k, c in counts.items() if c == 1)''', *EDGE)
    like_python('def run(xs):\n    return sum(a * b for a, b in zip(xs, xs))', *EDGE)
    like_python('def run(xs):\n    return sum(a * b for a, b in zip(sorted(xs), xs))', *EDGE)
    # zip() over a source that does not start at zero is refused by name, not mis-compiled --
    # unaffected by this fix, kept here as a boundary of the same feature
    refuses('zip() over a non-zero-start range', lambda: compile_fn(
        'def run(xs):\n    return sum(i for i, v in zip(range(3, 8), xs))'))


def integer_power():
    """Mutation-audit gap 6: the suite's only `**` (`(x - m) ** 2` in `variance`) has a float
    base, so `x ** k` with an *integer* base -- constant or variable exponent alike, and
    `ail_ipow`'s overflow check with it -- is dead by construction. The audit calls this the one
    that matters most: that exact path (SEMANTICS.md section 8) was changed on the same day this
    suite was last touched, and nothing here compiled it even once."""
    f = compile_fn('def run(n):\n    return 2 ** n')
    for n in range(0, 63):                    # 2**62 fits in int64_t; 2**63 does not
        check('2 ** %d (integer base, variable exponent)' % n, f(n), 2 ** n)

    g = compile_fn('def run(n):\n    return n ** 3')
    for n in (-5, -1, 0, 1, 2, 5, 100):
        check('%d ** 3 (variable base, constant exponent)' % n, g(n), n ** 3)

    # `ail_ipow` is exact where pow()'s double route is not: 7**20 needs 57 bits and pow() rounds
    check('7 ** 20 is exact (ail_ipow), not pow()-rounded',
          compile_fn('def run(xs):\n    for v in xs:\n        pass\n    return 7 ** 20')([0]),
          7 ** 20)

    # the overflow check inside ail_ipow itself: an exact integer power that does not fit traps,
    # for both a constant exponent and a variable one (SEMANTICS.md section 8)
    _traps('2 ** 63 overflows (constant integer exponent)',
           'def run(xs):\n    for v in xs:\n        pass\n    return 2 ** 63\n', 'overflow')
    _traps('2 ** n overflows (variable integer exponent, n == 63)',
           'def run(xs):\n    for v in xs:\n        pass\n    n = 63\n    return 2 ** n\n',
           'overflow')
    # a *variable* exponent that turns out negative at run time traps (SEMANTICS.md section 4);
    # a *constant* negative exponent instead takes the float pow() path and is unaffected
    _traps('2 ** n traps when n is a variable that turns out negative',
           'def run(xs):\n    for v in xs:\n        pass\n    n = -1\n    return 2 ** n\n',
           'negative exponent')
    like_python('def run(xs):\n    for v in xs:\n        pass\n    return 2 ** -1',
                [0])                                # constant exponent: the float path


def bare_division_return():
    """Mutation-audit gap 7: every division-returning test in this suite also has an
    unconditional early `return 0.0` (see `mean` and `variance` above), which independently forces
    the function's return type to float regardless of what `_etype`'s `Div -> FLT` rule decides --
    so flipping that one rule to INT would go unnoticed and every such function would truncate. A
    function whose *only* return is a bare division has no such independent evidence."""
    like_python('''def ratio(xs):
    return sum(xs) / len(xs)''', [1], [7, 8], [-7, -1, 5], [3, 3], [1, 2, 3, 4, 5], [5, 4, 3, 2, 1])
    check('a bare division return is a float (not truncated to int64_t)',
          compile_fn('def ratio(xs):\n    return sum(xs) / len(xs)')([7, 8]), 7.5)


def int64_min_boundary():
    """Mutation-audit gap 8: INT64_MIN never appears in any test vector, so a wrong boundary
    constant in `ck_neg` (pyfront.py's strict negation guard, shared by unary `-` and `abs()`)
    would be invisible. This puts INT64_MIN itself, and its immediate neighbour, through both."""
    _traps('negating INT64_MIN under strict overflows',
           'def run(xs):\n    for v in xs:\n        pass\n    n = (%s)\n    return -n\n'
           % INT64_MIN_SRC, 'overflow', strict=True)
    _traps('abs(INT64_MIN) under strict overflows',
           'def run(xs):\n    for v in xs:\n        pass\n    n = (%s)\n    return abs(n)\n'
           % INT64_MIN_SRC, 'overflow', strict=True)
    # the boundary is exact, not just "some large negative number": INT64_MIN's immediate
    # neighbour must NOT trap, and must still answer correctly (a wrong constant that is
    # off-by-one would either miss INT64_MIN itself above, or wrongly trap here instead). Run
    # out-of-process (like the traps above), not through compile_fn -- a wrong boundary here
    # would otherwise call _Exit(1) inside this very test process.
    _runs_ok('negating INT64_MIN + 1 under strict does not overflow',
             'def run(xs):\n    for v in xs:\n        pass\n    n = (%d)\n    return -n\n'
             % (-2 ** 63 + 1), 2 ** 63 - 1, strict=True)
    _runs_ok('abs(INT64_MIN + 1) under strict does not overflow',
             'def run(xs):\n    for v in xs:\n        pass\n    n = (%d)\n    return abs(n)\n'
             % (-2 ** 63 + 1), 2 ** 63 - 1, strict=True)


def end_to_end():
    """The command line, the way a person uses it."""
    with tempfile.TemporaryDirectory() as d:
        d = pathlib.Path(d)
        def artifact(name):
            p = d / name
            return pathlib.Path(str(p) + '.exe') if os.name == 'nt' else p

        data = d / 'data.bin'
        array.array('q', [3, -7, 2, 9, -4, 11]).tofile(data.open('wb'))
        rc = pyc.main(['sum(v*v for v in xs if v % 2)', str(d / 'tool')])
        check('pyc returns 0', rc, 0)
        out = subprocess.run([str(artifact('tool')), str(data)], capture_output=True, text=True)
        check('the built tool prints the answer', out.stdout.strip(), '260')
        rc = pyc.main(['sum(v * 1.5 for v in xs)', str(d / 'nope')])
        check('pyc refuses cleanly', rc, 3)

        # a function, not an expression, and one that takes more than the file
        rc = pyc.main(['def run(xs, k):\n    m = 0\n    for v in xs:\n        if v > k:\n'
                       '            m += 1\n    return m', str(d / 'over')])
        check('pyc builds a two-parameter function', rc, 0)
        out = subprocess.run([str(artifact('over')), str(data), '2'], capture_output=True, text=True)
        check('and passes the extra argument', out.stdout.strip(), '3')
        out = subprocess.run([str(artifact('over')), str(data)], capture_output=True, text=True)
        check('and says so when it is missing', out.returncode, 2)

        # A literal mutated by a top-level method call is a script local,
        # not a read-only module constant.  This is the Python shape emitted
        # for JS `let a = [1]; a.push(2)`.
        rc = pyc.main(['a = [1]\na.append(2)\nprint(len(a))',
                       str(d / 'mutable-script')])
        check('pyc builds a top-level mutable literal script', rc, 0)
        out = subprocess.run([str(artifact('mutable-script'))], capture_output=True,
                             text=True)
        check('and preserves its mutation', out.stdout, '2\n')

        # a function that returns a float prints one
        rc = pyc.main(['def run(xs):\n    if not xs:\n        return 0.0\n'
                       '    return sum(xs) / len(xs)', str(d / 'mean')])
        check('pyc builds a float-returning function', rc, 0)
        out = subprocess.run([str(artifact('mean')), str(data)], capture_output=True, text=True)
        check('and prints a float', out.stdout.strip(), '2.33333')

        # --emit-c and --file are paths nothing exercised
        rc = pyc.main(['--emit-c', 'sum(xs)', str(d / 'unused')])
        check('--emit-c returns 0', rc, 0)
        p = d / 'src.py'
        p.write_text('def run(xs):\n    return len(xs)\n')
        rc = pyc.main(['--file', str(p), str(d / 'fromfile')])
        check('--file returns 0', rc, 0)
        out = subprocess.run([str(artifact('fromfile')), str(data)], capture_output=True, text=True)
        check('and the tool it built works', out.stdout.strip(), '6')


def main():
    for part in (expressions, functions, containers, floats_and_calls, churn, arithmetic, overflow,
                 floor_and_width, boundary, word_notation,
                 hash_table_growth, memory_leak_under_repeated_calls, chained_comparison,
                 slice_bounds_via_assignment, fold_over_a_slice_is_a_real_bug,
                 negative_and_variable_slice_bounds, enumerate_index_counts_from_zero,
                 integer_power,
                 bare_division_return, int64_min_boundary,
                 end_to_end):
        part()
    if DIVERGES:
        print('where Python refuses and this answers anyway (documented, not silent):')
        for d in sorted(set(DIVERGES)):
            print('   ' + d)
        print()
    if FAILED:
        print('%d FAILED' % len(FAILED))
        for f in FAILED:
            print('   ' + f)
        return 1
    print('all checks passed')
    return 0


if __name__ == '__main__':
    sys.exit(main())

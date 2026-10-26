"""G3: module-level variables that functions rebind with `global` run on the typed path and in the IR.

Before G3 a function that said `global x` (or that the module merge gave a `global` line for
`m.x = v` / `m.x += 1`) made the whole program build on the general path, several times slower.
Now a module-level int, float or bool variable is one C static; every function reads and writes
that one variable (CPython's semantics: one variable, set once at the top of the module, changed
in call order).

* Programs are built with AIL_NO_GENERAL=1 (the typed path alone must take them) with AIL_IR=0
  and AIL_IR=1 (the IR path, every function it can take) and print what CPython prints:
  counters, accumulators, flags, recursion, loops whose test or bound is a variable, exceptions,
  methods, `+= -= *= //= %= <<= >>= &= |= ^= **=` on a variable, a variable read by a function that
  never says `global`, a `global` line that only reads.
* Statements whose result depends on an evaluation order the C code does not fix (a variable read
  in the same statement as a call that changes it) are refused by name on the typed path with a
  `write instead:` hint; the default build then takes the general path and still prints what CPython
  prints. So are a variable that changes kind, a local that shadows a variable, a loop variable or a
  tuple target that is a variable, a bool variable assigned a number and a number assigned a bool.
* Several modules: a state module's `global` functions and `m.x += 1` from other modules share
  one variable (typed, both IR modes).
* The IR has `global.load` / `global.store` with the effect `Global(m,x)`: they print, parse and
  verify; the function summary lists the reads and writes (so a caller knows which variables a call
  changes); a pass never moves a load across a store or a call that may store, never removes a
  store, never merges two loads that have a store between them.
* Programs without `global` build to the same C as before (the codegen pins, and the module-level
  constants that are never rebound, are untouched).
"""
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path[:0] = [str(ROOT / "python" / "pkg-v12"), str(ROOT)]
CLI = str(ROOT / "ail_chatgpt.py")

from ir import ir as I                       # noqa: E402
from ir import effects as E                  # noqa: E402
from ir import text, verify                  # noqa: E402
from ir.passes import mem2reg, simplify, ranges, licm   # noqa: E402


def write(directory, files):
    for name, body in files.items():
        path = Path(directory) / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(body, encoding="utf-8")


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="ail-globals-")
        self.dir = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def cpython(self, entry="main.py"):
        ran = subprocess.run([sys.executable, "-B", entry], cwd=self.dir, capture_output=True, timeout=60)
        self.assertEqual(ran.returncode, 0, ran.stderr.decode())
        return ran.stdout

    def build(self, entry="main.py", ir="0", typed=True, out="out"):
        exe = self.dir / ("%s_ir%s" % (out, ir))
        if exe.exists():
            exe.unlink()
        env = dict(os.environ, AIL_IR=ir, AIL_IR_STATS=str(self.dir / ("stats_" + ir)))
        env.pop("AIL_NO_GENERAL", None)
        if typed:
            env["AIL_NO_GENERAL"] = "1"
        built = subprocess.run([sys.executable, "-B", CLI, "compile", entry, "-o", str(exe)], cwd=self.dir,
                               capture_output=True, text=True, timeout=600, env=env)
        return built, exe

    def same(self, source, irs=("0", "1"), typed=True, entry="main.py"):
        """`source` is one program text (or a dict of files); both builds print what CPython prints."""
        files = {entry: source} if isinstance(source, str) else source
        write(self.dir, files)
        expected = self.cpython(entry)
        for ir in irs:
            built, exe = self.build(entry, ir, typed)
            self.assertEqual(built.returncode, 0, "AIL_IR=%s: %s" % (ir, built.stderr))
            ran = subprocess.run([str(exe)], capture_output=True, timeout=60)
            self.assertEqual(ran.stdout, expected, "AIL_IR=%s" % ir)
            self.assertEqual(ran.returncode, 0)
        return expected.decode()

    def ir_paths(self, ir="1"):
        """{function: path} for the last build with this AIL_IR."""
        rows = [json.loads(line) for line in (self.dir / ("stats_" + ir)).read_text().splitlines() if line.strip()]
        return {row["fn"]: row["path"] for row in rows}

    def refused(self, source, *needles, entry="main.py", hint=True):
        """The typed path refuses by name (with a `write instead:` hint); the default build falls back
        to the general path and still prints what CPython prints."""
        write(self.dir, {entry: source})
        built, exe = self.build(entry, "0", typed=True)
        self.assertIn(built.returncode, (2, 3), built.stdout + built.stderr)
        for needle in needles:
            self.assertIn(needle, built.stderr)
        if hint:
            self.assertIn("write instead", built.stderr)
        self.assertNotIn("Traceback", built.stderr)
        expected = self.cpython(entry)
        built, exe = self.build(entry, "0", typed=False, out="general")
        self.assertEqual(built.returncode, 0, built.stderr)
        self.assertIn("general path", built.stderr)
        ran = subprocess.run([str(exe)], capture_output=True, timeout=60)
        self.assertEqual(ran.stdout, expected)
        return built.stderr


class ScalarVariables(Base):
    def test_counters_accumulators_and_loop_tests(self):
        out = self.same('''count = 0
limit = 5
rate = 0.5
total = 0
seen = 0


def tick():
    global count
    count += 1


def reset():
    global count
    count = 0


def add(x):
    global total, seen
    total += x
    seen += 1


def main():
    for i in range(7):
        tick()
    print(count)
    reset()
    while count < limit:
        tick()
    print(count, limit, rate * count)
    xs = [3, 1, 4, 1, 5, 9, 2, 6]
    for i in range(len(xs)):
        add(xs[i])
    for x in xs:
        add(x * 2)
    print(total, seen, total / seen)


main()
''')
        self.assertEqual(out.splitlines()[:2], ["7", "5 5 2.5"])

    def test_a_range_bound_is_read_once_and_a_while_test_every_time(self):
        self.same('''n = 5
pos = 0
size = 10
idx = 2


def shrink():
    global n
    n -= 1


def adv():
    global pos
    pos += 3


def main():
    s = 0
    for i in range(n):
        shrink()
        s += i
    print(s, n)
    steps = 0
    while pos < size:
        adv()
        steps += 1
    print(steps, pos)
    a = [0, 0, 0, 0, 0]
    for k in range(10):
        a[idx] += k
        a[idx + 1] = a[idx] - 1
    print(a[2], a[3])


main()
''')

    def test_recursion_and_chains_of_calls_that_change_a_variable(self):
        self.same('''depth = 0
best = 0
calls = 0
g1 = 1


def go(n):
    global depth, best
    depth += 1
    if depth > best:
        best = depth
    if n > 0:
        go(n - 1)
        go(n - 2)
    depth -= 1


def fib(n):
    global calls
    calls += 1
    if n < 2:
        return n
    return fib(n - 1) + fib(n - 2)


def a():
    global g1
    g1 = g1 * 2
    b()


def b():
    global g1
    g1 += 3


def main():
    go(6)
    print(depth, best)
    print(fib(15), calls)
    for i in range(4):
        a()
    print(g1)


main()
''')

    def test_floats_negative_and_large_starts_and_every_operator(self):
        self.same('''acc = 1.0
k = 2
a = -5
b = 4611686018427387904
c = 1e-3
d = 7
e = 2


def step(x):
    global acc, k
    acc = acc * 1.5 + x
    k = k * 2 + 1
    k %= 1000
    acc /= 2.0


def go():
    global a, b, c, d, e
    a //= 2
    b = b // 1024 + 1
    c = c * 3 - 0.5
    d %= 5
    d <<= 3
    e **= 5
    e |= 3
    e ^= 1
    e &= 0xff
    e >>= 1


def main():
    for i in range(10):
        step(i * 0.5)
    print(acc, k)
    go()
    go()
    print(a, b, c, d, e)
    print(f"{k} and {acc:.3f}", min(k, 10), max(acc, 1.0), abs(k - 10))


main()
''')

    def test_a_returned_variable_keeps_the_exact_value_past_int64(self):
        self.same('''x = 4611686018427387904


def get():
    return x


def wrap():
    return get() + 1


def main():
    global x
    x *= 4
    print(get())
    print(wrap())


main()
''', irs=("1",))

    def test_bit_operations_on_a_variable_past_int64(self):
        self.same('''x = 4611686018427387904
n = -4611686018427387904


def main():
    global x, n
    x *= 4
    n *= 4
    print(x & 255, x | 1, x ^ 3)
    print(n & 255, n | 1, n ^ 3)
    print(~x, ~n)


main()
''', irs=("1",))

    def test_exceptions_methods_and_a_parameter_with_the_variable_name(self):
        self.same('''hits = 0
total = 0
v = 10


class Acc:
    def __init__(self, k):
        self.k = k

    def add(self, x):
        global total
        total += x * self.k
        return 0


def risky(i):
    global hits
    hits += 1
    if i == 3:
        raise ValueError("boom")
    return i


def f(v):
    return v + 1


def g():
    global v
    v = f(v) * 2
    return 0


def work(i):
    global hits
    try:
        hits += 1
        if i == 2:
            raise ValueError("x")
        hits += 10
    finally:
        hits += 100


def main():
    t = 0
    for i in range(6):
        try:
            t += risky(i)
        except ValueError:
            t += 100
    print(t, hits)
    a = Acc(3)
    for i in range(5):
        a.add(i)
    print(total)
    g()
    g()
    print(v, f(3))
    for i in range(4):
        try:
            work(i)
        except ValueError:
            print("caught", hits)
    print(hits)


main()
''')

    def test_bool_variables_print_as_bool_and_count_as_ints(self):
        out = self.same('''done = False
verbose = True
n = 0
flag = False
cnt = 0
seen = False


def check(x):
    global done, n
    n += 1
    done = x > 3
    return n


def toggle():
    global verbose
    verbose = not verbose


def show(flag2: bool):
    print(flag2, done, verbose)


def mark(v):
    global flag, cnt
    flag = v > 0
    cnt += flag


def see():
    global seen
    seen = True


def main():
    for i in range(6):
        check(i)
        if done:
            toggle()
    show(done)
    print(done, verbose, n, done and verbose, not done)
    t = done
    print(t)
    for i in range(-2, 4):
        mark(i)
    print(flag, cnt, flag + 1)
    before = seen
    see()
    after = seen
    print(before, after, before == after)


main()
''')
        self.assertIn("True", out)

    def test_a_global_line_that_only_reads_leaves_a_constant(self):
        self.same('''LIMIT = 10
count = 0
steps = 0
outer = 4


def f(x):
    global LIMIT
    return x + LIMIT


def g():
    global count
    count += 1


def tick():
    global steps
    steps += 1


def main():
    g()
    g()
    print(f(5), count, LIMIT)
    t = 0
    for i in range(outer):
        for j in range(3):
            tick()
            t += steps
    print(t, steps)


main()
''')

    def test_a_variable_in_a_print_after_the_call_that_changes_it(self):
        # print's arguments are evaluated in order, each into its own temporary: the call first
        self.same('''c = 0


def bump():
    global c
    c += 1
    return c


def main():
    print(bump(), c, bump(), c)
    b = bump()
    print(c + b)
    d = bump() + bump()
    print(d, c)


main()
''')

    def test_module_variables_from_a_script_without_main(self):
        self.same('''hits = 0


def hit(n):
    global hits
    hits += n


for i in range(4):
    hit(i)
print(hits)
''')

    def test_str_variables_hold_literals_for_the_whole_run(self):
        self.same('''mode = "idle"
label = "x"
DEFAULT = "none"
n = 0
cur = "left"
LEFT = "left"
RIGHT = "right"


def start():
    global mode, n
    mode = "running"
    n += 1


def stop():
    global mode, label
    mode = "stopped"
    label = DEFAULT


def flip():
    global cur
    cur = RIGHT if cur == LEFT else LEFT


def setm(m):
    global mode
    if m == 0:
        mode = "idle"
    elif m == 1:
        mode = "busy"
    else:
        mode = "done"


def report():
    print(mode, label, len(mode), mode == "running", mode + "!")


def main():
    report()
    start()
    report()
    stop()
    report()
    s = mode
    start()
    print(s, mode)
    print(mode.upper(), mode[0], mode[1:3], f"{mode}:{n}")
    for ch in mode:
        print(ch, end="")
    print()
    for i in range(3):
        flip()
        print(cur)
    d = {}
    for i in range(6):
        setm(i % 3)
        if mode in d:
            d[mode] += 1
        else:
            d[mode] = 1
    print(d["idle"], d["busy"], d["done"], mode)


main()
''')

    def test_a_str_index_is_not_cached_across_a_call_that_changes_the_str(self):
        self.same('''mode = "abcdef"


def change():
    global mode
    mode = "uvwxyz"


def main():
    i = 2
    print(mode[i], mode[i + 1])
    change()
    print(mode[i], mode[i + 1])
    x = mode[i]
    change()
    print(x)


main()
''')


class Refusals(Base):
    def test_a_variable_that_changes_kind(self):
        self.refused('''x = 1.5


def f():
    global x
    x = 3


def main():
    f()
    print(x)


main()
''', "module variable holding a float", "keeps the kind of its first value")

    def test_a_local_with_the_name_of_a_variable_another_function_rebinds(self):
        self.refused('''y = 4


def f():
    y = 5
    return y


def g():
    global y
    y += 1


def main():
    g()
    print(f(), y)


main()
''', "module variable", "separate local")

    def test_a_loop_or_tuple_target_that_is_a_variable(self):
        self.refused('''count = 0


def inc():
    global count
    for count in range(3):
        pass


def main():
    inc()
    print(count)


main()
''', "module variable", "compute the value into a local")
        self.refused('''a = 1
b = 2


def swap():
    global a, b
    a, b = b, a


def main():
    swap()
    print(a, b)


main()
''', "module variable", "tuple target")

    def test_a_statement_that_reads_a_variable_and_calls_what_changes_it(self):
        self.refused('''c = 0


def bump():
    global c
    c += 1
    return c


def main():
    print(c + bump())
    print(c)


main()
''', "reads the module variable c", "bump")

    def test_numbers_and_bools_do_not_mix_in_one_variable(self):
        self.refused('''flag = 0


def toggle(x):
    global flag
    flag = x > 3


def main():
    toggle(5)
    print(flag)


main()
''', "starts as a number", "assigned a bool")
        self.refused('''ok = True


def chk(v):
    global ok
    ok = v


def main():
    chk(5)
    print(ok)


main()
''', "declared bool", "not a bool", hint=False)

    def test_other_kinds_of_module_variable_are_not_built_yet(self):
        self.refused('''items = [1]


def reset():
    global items
    items = [2]


def main():
    reset()
    print(items[0])


main()
''', "`global`", "pass the value in as a parameter")

    def test_a_str_variable_takes_only_text_that_lives_for_the_whole_run(self):
        self.refused('''name = "a"


def grow(s):
    global name
    name = name + s


def main():
    grow("b")
    print(name)


main()
''', "str module variable", "would not outlive this call")
        self.refused('''name = "a"


def put(s):
    global name
    name = s


def main():
    put("q")
    print(name)


main()
''', "str module variable", "a str literal")


class Modules(Base):
    STATE = {
        "state.py": '''counter = 0
scale = 0.5
ready = False


def bump(n=1):
    global counter
    counter += n
    return counter


def current():
    return counter


def arm():
    global ready
    ready = True
''',
        "other.py": '''import state


def live():
    return state.counter


def bump_via():
    state.counter += 10
    return state.counter


def reset():
    state.counter = 0
''',
    }

    def test_global_functions_and_attribute_writes_share_one_variable(self):
        out = self.same({
            **self.STATE,
            "main.py": '''import state
import other

hits = 0


def hit():
    global hits
    hits += 1
    state.counter = state.counter + 100
    state.scale = state.scale * 3.0
    return hits


def main():
    state.bump()
    state.bump(2)
    print(state.counter, state.current(), other.live())
    print(other.bump_via(), state.counter)
    state.counter += 1
    state.counter = state.counter * 2
    print(state.current(), other.live())
    hit()
    hit()
    print(state.counter, hits, state.scale)
    other.reset()
    print(state.counter, state.current())
    state.arm()
    print(state.ready)


main()
''',
        })
        self.assertEqual(out.splitlines()[0], "3 3 3")

    def test_from_import_of_a_changing_variable_is_a_snapshot(self):
        # (a snapshot is a module-level copy, not a literal: the general path runs this one)
        self.same({
            **self.STATE,
            "main.py": '''import state
from state import counter


def main():
    state.bump(5)
    print(counter, state.counter)


main()
''',
        }, irs=("0",), typed=False)


class TheIR(Base):
    BUMP = '''func @bump(%n: i64) -> () attrs {linkage = "extern", names = ["n"], sym = "bump"} {
  %v = global.load {name = "count"} : i64
  %t = add %v, %n {mode = "ck"} : i64
  global.store %t {name = "count"}
  return
}
'''
    LOOP = '''func @spin(%n: i64) -> (i64) attrs {linkage = "extern", names = ["n"], sym = "spin"} {
  %zero = const {value = 0} : i64
  %one = const {value = 1} : i64
  %s = local.alloc {name = "s"} : place<i64>
  store %s, %zero
  for.range %zero, %n, %one {args = 1} {
  ^(%i: i64):
    %a = global.load {name = "step"} : i64
    %b = global.load {name = "step"} : i64
    %c = add %a, %b {mode = "ck"} : i64
    %sv = load %s : i64
    %d = add %sv, %c {mode = "ck"} : i64
    store %s, %d
    global.store %d {name = "last"}
    continue
  }
  %r = load %s : i64
  return %r
}
'''

    def fn_of(self, src):
        fn = text.parse_function(src)
        program = I.Program({fn.sym: fn})
        E.summarize_program(program)
        return fn, program

    def test_the_ops_print_parse_and_verify(self):
        fn, program = self.fn_of(self.BUMP)
        verify.check(fn, program)
        printed = text.print_function(fn)
        self.assertEqual(text.print_function(text.parse_function(printed)), printed)
        self.assertIn("global.load", printed)
        self.assertIn("global.store", printed)

    def test_the_summary_names_the_variables_read_and_written(self):
        fn, program = self.fn_of(self.BUMP)
        self.assertEqual(fn.effects.reads, frozenset({"Global(m,count)"}))
        self.assertEqual(fn.effects.writes, frozenset({"Global(m,count)"}))
        loop, _ = self.fn_of(self.LOOP)
        self.assertEqual(loop.effects.reads, frozenset({"Global(m,step)"}))
        self.assertEqual(loop.effects.writes, frozenset({"Global(m,last)"}))

    def test_a_caller_sees_what_its_callee_writes(self):
        callee, program = self.fn_of(self.BUMP)
        caller = text.parse_function('''func @twice() -> () attrs {linkage = "extern", names = [], sym = "twice"} {
  %one = const {value = 1} : i64
  call %one {callee = "bump"}
  call %one {callee = "bump"}
  return
}
''')
        program.add(caller)
        summaries = E.summarize_program(program)
        self.assertIn("Global(m,count)", summaries["twice"].writes)
        self.assertIn("Global(m,count)", summaries["twice"].reads)

    def test_passes_keep_every_store_and_every_load_that_a_store_separates(self):
        fn, program = self.fn_of(self.LOOP)
        mem2reg.run(fn)
        simplify.run(fn)
        ranges.run(fn, {})
        licm.run(fn)
        simplify.run(fn)
        E.summarize_program(program)
        verify.check(fn, program)
        names = [i.op for i in I.walk(fn.body)]
        self.assertEqual(names.count("global.store"), 1)
        # two loads of one variable with no store between them are the same value only if nothing
        # in the loop can change it; here the loop stores `last` (another variable) and no call
        # may store `step`, but a pass must in any case never turn a load into a constant
        self.assertGreaterEqual(names.count("global.load"), 1)
        loop = [i for i in I.walk(fn.body) if i.op == "for.range"][0]
        self.assertIn("global.store", [i.op for i in I.walk(loop.regions[0])])

    HOIST = '''func @spin(%n: i64) -> (i64) attrs {linkage = "extern", names = ["n"], sym = "spin"} {
  %zero = const {value = 0} : i64
  %one = const {value = 1} : i64
  %s = local.alloc {name = "s"} : place<i64>
  store %s, %zero
  for.range %zero, %n, %one {args = 1} {
  ^(%i: i64):
    %a = global.load {name = "step"} : i64
    %sv = load %s : i64
    %d = add %sv, %a {mode = "ck"} : i64
    store %s, %d
    BODY
    continue
  }
  %r = load %s : i64
  return %r
}
'''

    def hoisted(self, body, summaries=None):
        fn, program = self.fn_of(self.HOIST.replace("BODY", body))
        program.externs["other"] = I.fn_type([I.I64], [])
        mem2reg.run(fn)
        simplify.run(fn)
        licm.run(fn, summaries)
        E.summarize_program(program)
        verify.check(fn, program)
        top = [i.op for i in fn.body.instrs]
        return "global.load" in top[:top.index("for.range")]

    def test_licm_hoists_a_load_out_of_a_loop_that_cannot_store_the_variable(self):
        self.assertTrue(self.hoisted('global.store %d {name = "last"}'))
        self.assertTrue(self.hoisted(
            'call %i {callee = "other"}', {"other": E.Effects(writes=["Global(m,last)"])}))

    def test_licm_keeps_a_load_inside_a_loop_that_may_store_the_variable(self):
        self.assertFalse(self.hoisted('global.store %d {name = "step"}'))
        self.assertFalse(self.hoisted(
            'call %i {callee = "other"}', {"other": E.Effects(writes=["Global(m,step)"])}))
        self.assertFalse(self.hoisted('call %i {callee = "other"}', {}))

    def test_malformed_uses_are_rejected_by_name(self):
        bad_type = self.BUMP.replace(": i64\n  %t", ": i1\n  %t", 1)
        fn = text.parse_function(bad_type)
        with self.assertRaises(I.IRError):
            verify.check(fn, I.Program({fn.sym: fn}))
        nameless = self.BUMP.replace(' {name = "count"} : i64', " : i64")
        fn = text.parse_function(nameless)
        with self.assertRaises(I.IRError):
            verify.check(fn, I.Program({fn.sym: fn}))

    def test_functions_that_use_a_variable_take_the_ir_path_and_verify(self):
        write(self.dir, {"main.py": '''count = 0
total = 1.5
step = 3


def bump(n):
    global count, total
    count += n * step
    total = total * 2.0
    return 0


def main():
    for i in range(10):
        bump(i)
    print(count, total, step)


main()
'''})
        expected = self.cpython()
        built, exe = self.build("main.py", "verify")
        self.assertEqual(built.returncode, 0, built.stderr)
        ran = subprocess.run([str(exe)], capture_output=True, timeout=60)
        self.assertEqual(ran.stdout, expected)
        paths = self.ir_paths("verify")
        self.assertEqual(paths["bump"], "ir")
        self.assertEqual(paths["main"], "ir")


class SilentDifferences(Base):
    """Two differences from CPython found while testing G3, fixed on the Python surface: an int
    `and` / `or` used as a value (`0 or 5` is 5, not 1) and a bool that crosses a function boundary
    unannotated (it printed 1 / 0)."""

    def test_an_int_and_or_gives_the_operand_that_decided_it(self):
        out = self.same('''def f(a):
    print("f", a)
    return a


def h(a):
    print("h", a)
    return a * 2


def main():
    z = f(1) and h(2) or f(3)
    print(z)
    w = f(0) and h(2) or f(3)
    print(w)
    v = f(2) or h(5)
    print(v)
    u = f(0) or h(5)
    print(u)
    t = f(4) and h(6)
    print(t)
    a = 0
    b = 5
    print(a or b, a and b, b and a, b or a, 0 or 5)
    x = a or b or 7
    y = b and 3 and 9
    print(x, y)
    n = 0
    for i in range(6):
        if i % 2 and i > 1 or i == 0:
            n += 1
        while n < 0 or n > 100:
            n = 0
    print(n, 1 if (a or b) else 2, not (a and b), len([k for k in range(5) if k % 2 or k == 4]))
    flag = a > 0 and b > 0
    print(flag, (a > 0) or (b > 0))


main()
''')
        self.assertTrue(out.startswith("f 1\nh 2\n4\n"))

    def test_and_or_on_floats_or_bools_mixed_with_numbers_is_refused_not_guessed(self):
        self.refused('''def main():
    a = 0.0
    b = 2.5
    print(a or b)


main()
''', "needs int operands")
        self.refused('''def main():
    a = 3
    b = 5
    print((a > 1) and b)


main()
''', "needs int operands")

    def test_unannotated_bool_parameters_and_results_print_as_bools(self):
        self.same('''def big(x):
    return x > 3


def both(a, b):
    return a and b


def show(flag):
    print(flag)


def pick(flag):
    return flag


def main():
    print(big(5), big(1))
    t = big(5)
    print(t)
    print(both(big(5), big(6)))
    ok = both(True, False)
    print(ok)
    d = 5 > 3
    show(d)
    show(5 > 6)
    show(True)
    print(pick(d), pick(5 > 6))
    x = pick(5 > 6)
    print(x, x + 1)


main()
''')

    def test_a_parameter_that_gets_a_bool_and_a_number_is_refused(self):
        self.refused('''def show(flag):
    print(flag)


def main():
    show(True)
    show(3)


main()
''', "gets a bool from some calls and a number from others")


if __name__ == "__main__":
    unittest.main()

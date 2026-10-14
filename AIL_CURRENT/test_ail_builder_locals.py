"""Builder locals: a str local used as an accumulator (`w += x` in a loop) is compiled as an
exclusively owned growable buffer (pyfunc `_builder_locals`, cruntime `ail_bl_*`) and the program
prints exactly what Python prints.

A read of the variable is a VIEW of the buffer only where the consumer finishes before any write
(len, comparisons, dict keys, print, int, find/count/startswith, the addend of a self-append); every
other read copies into the function arena. The program below snapshots the variable into locals,
lists, struct fields, user-function arguments and returns, then keeps writing to it, appends it to
itself and to slices of itself, resets it, reassigns it, raises mid-loop (caught by the caller and
inside the function, with and without `finally`) and builds 300,000 characters. The generated C is
checked to use the builder path where the variable qualifies and not where it does not (a
parameter, a loop or tuple target, a name captured by a comprehension, a variable that is never
extended or extended outside any loop, and one snapshotted in the loop that extends it, which costs
more as a builder than as an arena string). A raise out of a function that holds a large buffer
must free it: 400 such calls stay under 20 MB.
"""
import re
import subprocess
import sys
import unittest
import test_ail_c_objects as support
from test_ail_map_fields import build

sys.path[:0] = [str(support.ROOT / 'python' / 'pkg-v12'), str(support.ROOT)]
import pyfunc  # noqa: E402
from ail_syntax import translate  # noqa: E402

SOURCE = r'''struct Box { s: str; n: int; }

fn keep(w: str) -> str { return w; }
fn store(b: Box, w: str) -> str { b.s = w; return w + "|"; }
fn show(w: str) -> str { return "[" + w + "]"; }

fn build(n: int) -> str {
    let w = "";
    for i in range(n) { w += str(i); w += ","; }
    return w;
}

fn tokens(text: str) -> int {
    let w = "";
    let counts: dict[str, int] = {};
    let longest = 0;
    for c in text {
        if c == " " {
            if len(w) > 0 {
                counts[w] = counts.get(w, 0) + 1;
                if w == "the" { print("the!"); }
                if len(w) > longest { longest = len(w); }
                w = "";
            }
        } else {
            w += c;
        }
    }
    if len(w) > 0 { counts[w] = counts.get(w, 0) + 1; }
    for k, v in sorted(counts.items(), key=lambda kv: (-kv[1], kv[0])) { print(k, v); }
    print("w" in counts, "é日" in counts, longest);
    return len(counts);
}

fn snapshots() -> int {
    let w = "";
    let xs: list[str] = [];
    let b = Box("", 0);
    for j in range(5) { w += "ab"; w += "é"; }
    let v = w;
    xs.append(w);
    let r = keep(w);
    let q = store(b, w);
    let t = w + w;
    let u = w.upper();
    let parts = w.split("b");
    for j in range(3) { w += "!"; }
    print(v, r, q, b.s, w, len(v), len(w));
    print(t, u, len(parts), parts[1], f"{w}-{len(w)}");
    w = "reset";
    print(v, w, xs[0], b.s, r, q, t);
    for j in range(2) { w += "?"; }
    for c in w { w += c; w += c; }
    print(w, len(w), xs[0], show(w), w[1], w[1:3], w[-1]);
    let d: dict[str, int] = {};
    d[w] = 1;
    w += "more";
    for j in range(2) { d[w] = j; w += "x"; }
    print(len(d), w in d, d.get("reset??", -1), d.get(w, -2));
    return 0;
}

fn selfs() -> int {
    let w = "日本";
    for rep in range(2) {
        w += w;
        print(w, len(w));
        w += w[1:3];
        print(w, len(w));
        w = w[2:5];
        print(w, len(w));
        w = w;
        w += w;
        print(w, len(w));
        let u = "abcdefghijklmnopqrstuvwxyz";
        w = u;
        w += w;
        w += w;
        w += w[3:60];
        print(w, len(w));
        w = w[10:12];
        print(w, len(w));
        w = "";
        w += "q";
        print(w, len(w));
        w = "é";
        w += "a";
        print(w, len(w));
        w = w[1:];
    }
    return 0;
}

fn selfs2() -> int {
    let w = "日本";
    for rep in range(2) {
        w += w;
        w = w + w + "z";
        print(w, len(w));
        w = w[1:] + w[:2];
        print(w, len(w));
        w += w + w;
        print(w, len(w), w[1], w.find("z"));
    }
    return 0;
}

fn flags() -> int {
    let w = "";
    for r in range(3) {
        w = "";
        for c in "aé日b" { w += c; print(len(w), w); }
        w = "xyz";
        for j in range(2) { w += "é"; print(len(w)); }
        w = w[3:];
        print(len(w), w);
        w = "";
        w += "ab";
        print(len(w), w == "ab", w < "b", w != "");
    }
    return 0;
}

fn resets() -> int {
    let w = "start";
    let t = "";
    for i in range(40) {
        w = "";
        for j in range(i % 7) { w += chr(97 + j); }
        if i % 5 == 0 { w = t; }
        if i % 4 == 0 { w = "other-" + str(i); }
        t = w;
        w = "-" + w;
        if i % 3 == 0 { print(i, w, t, len(w)); }
    }
    let big = "";
    for i in range(20000) { big += "xy"; if i % 7000 == 0 { big = ""; } }
    print(len(big), big[:3], big[-3:]);
    return 0;
}

fn ret_early(n: int) -> str {
    let w = "";
    for i in range(n) {
        w += str(i);
        if i == 3 { return w; }
    }
    return w + "end";
}

fn fail_mid(n: int) -> int {
    let w = "";
    for i in range(n) {
        w += "ab";
        if i == 3 { raise ValueError; }
    }
    return len(w);
}

fn guarded(n: int) -> int {
    let w = "";
    let total = 0;
    for i in range(n) {
        try {
            w += "x";
            if i % 3 == 2 { raise ValueError; }
            w += "y";
        } except ValueError {
            total += len(w);
            w += "!";
        }
    }
    print(w, total);
    return total;
}

fn finals(n: int) -> str {
    let w = "";
    for i in range(n) {
        try {
            w += "a";
            if i == 2 and n == 3 { raise ValueError; }
            if i == 4 { return w; }
        } finally {
            w += "f";
        }
    }
    return w;
}

fn digits(n: int) -> int {
    let w = "";
    for i in range(n) { w += str(i % 10); }
    let v = int(w[:5]) + int(w) % 1000;
    print(v, int(w) % 10, w.find("45"), w.count("3"), w.startswith("01"), w.isdigit());
    return v;
}

fn main() -> int {
    print(build(5), build(0), len(build(100)));
    print(tokens("the quick  brown the fox é日 é日 the w "));
    snapshots();
    selfs();
    selfs2();
    flags();
    resets();
    print(ret_early(3), ret_early(10));
    for i in range(3) {
        try { print(fail_mid(i + 2)); } except ValueError { print("caught", i); }
    }
    print(guarded(8));
    try { print(finals(2)); print(finals(3)); } except ValueError { print("finals raised"); }
    print(finals(2), finals(5));
    print(digits(12));
    let big = "";
    for i in range(300000) { big += "x"; }
    print(len(big), big[299995:]);
    return 0;
}
'''

PYTHON = r'''class Box:
    def __init__(self, s, n): self.s = s; self.n = n

def keep(w): return w
def store(b, w): b.s = w; return w + "|"
def show(w): return "[" + w + "]"

def build(n):
    w = ""
    for i in range(n): w += str(i); w += ","
    return w

def tokens(text):
    w = ""
    counts = {}
    longest = 0
    for c in text:
        if c == " ":
            if len(w) > 0:
                counts[w] = counts.get(w, 0) + 1
                if w == "the": print("the!")
                if len(w) > longest: longest = len(w)
                w = ""
        else:
            w += c
    if len(w) > 0: counts[w] = counts.get(w, 0) + 1
    for k, v in sorted(counts.items(), key=lambda kv: (-kv[1], kv[0])): print(k, v)
    print("w" in counts, "é日" in counts, longest)
    return len(counts)

def snapshots():
    w = ""
    xs = []
    b = Box("", 0)
    for j in range(5):
        w += "ab"; w += "é"
    v = w
    xs.append(w)
    r = keep(w)
    q = store(b, w)
    t = w + w
    u = w.upper()
    parts = w.split("b")
    for j in range(3): w += "!"
    print(v, r, q, b.s, w, len(v), len(w))
    print(t, u, len(parts), parts[1], f"{w}-{len(w)}")
    w = "reset"
    print(v, w, xs[0], b.s, r, q, t)
    for j in range(2): w += "?"
    for c in w:
        w += c; w += c
    print(w, len(w), xs[0], show(w), w[1], w[1:3], w[-1])
    d = {}
    d[w] = 1
    w += "more"
    for j in range(2):
        d[w] = j; w += "x"
    print(len(d), w in d, d.get("reset??", -1), d.get(w, -2))
    return 0

def selfs():
    w = "日本"
    for rep in range(2):
        w += w
        print(w, len(w))
        w += w[1:3]
        print(w, len(w))
        w = w[2:5]
        print(w, len(w))
        w = w
        w += w
        print(w, len(w))
        u = "abcdefghijklmnopqrstuvwxyz"
        w = u
        w += w
        w += w
        w += w[3:60]
        print(w, len(w))
        w = w[10:12]
        print(w, len(w))
        w = ""
        w += "q"
        print(w, len(w))
        w = "é"
        w += "a"
        print(w, len(w))
        w = w[1:]
    return 0

def selfs2():
    w = "日本"
    for rep in range(2):
        w += w
        w = w + w + "z"
        print(w, len(w))
        w = w[1:] + w[:2]
        print(w, len(w))
        w += w + w
        print(w, len(w), w[1], w.find("z"))
    return 0

def flags():
    w = ""
    for r in range(3):
        w = ""
        for c in "aé日b":
            w += c; print(len(w), w)
        w = "xyz"
        for j in range(2):
            w += "é"; print(len(w))
        w = w[3:]
        print(len(w), w)
        w = ""
        w += "ab"
        print(len(w), w == "ab", w < "b", w != "")
    return 0

def resets():
    w = "start"
    t = ""
    for i in range(40):
        w = ""
        for j in range(i % 7): w += chr(97 + j)
        if i % 5 == 0: w = t
        if i % 4 == 0: w = "other-" + str(i)
        t = w
        w = "-" + w
        if i % 3 == 0: print(i, w, t, len(w))
    big = ""
    for i in range(20000):
        big += "xy"
        if i % 7000 == 0: big = ""
    print(len(big), big[:3], big[-3:])
    return 0

def ret_early(n):
    w = ""
    for i in range(n):
        w += str(i)
        if i == 3: return w
    return w + "end"

def fail_mid(n):
    w = ""
    for i in range(n):
        w += "ab"
        if i == 3: raise ValueError
    return len(w)

def guarded(n):
    w = ""
    total = 0
    for i in range(n):
        try:
            w += "x"
            if i % 3 == 2: raise ValueError
            w += "y"
        except ValueError:
            total += len(w)
            w += "!"
    print(w, total)
    return total

def finals(n):
    w = ""
    for i in range(n):
        try:
            w += "a"
            if i == 2 and n == 3: raise ValueError
            if i == 4: return w
        finally:
            w += "f"
    return w

def digits(n):
    w = ""
    for i in range(n): w += str(i % 10)
    v = int(w[:5]) + int(w) % 1000
    print(v, int(w) % 10, w.find("45"), w.count("3"), w.startswith("01"), w.isdigit())
    return v

print(build(5), build(0), len(build(100)))
print(tokens("the quick  brown the fox é日 é日 the w "))
snapshots()
selfs()
selfs2()
flags()
resets()
print(ret_early(3), ret_early(10))
for i in range(3):
    try: print(fail_mid(i + 2))
    except ValueError: print("caught", i)
print(guarded(8))
try:
    print(finals(2)); print(finals(3))
except ValueError:
    print("finals raised")
print(finals(2), finals(5))
print(digits(12))
big = ""
for i in range(300000): big += "x"
print(len(big), big[299995:])
'''

BUILDERS = ('build', 'tokens', 'snapshots', 'selfs', 'flags', 'resets', 'ret_early', 'fail_mid',
            'guarded', 'finals', 'digits')
NOT_BUILDERS = ('keep', 'store', 'show', 'selfs2')

SOURCE_PLAIN = r'''fn grow_param(p: str, n: int) -> str {
    for i in range(n) { p += "x"; }
    return p;
}

fn for_target() -> int {
    for w in ["a", "bc"] { w += "!"; print(w); }
    return 0;
}

fn no_extension() -> int {
    let t = "";
    for i in range(3) { t = str(i) + "é"; print(t); }
    return 0;
}

fn no_loop() -> int {
    let w = "a";
    w += "b";
    w = w + "c";
    print(w, len(w));
    return 0;
}

fn snapshot_loop() -> int {
    let w = "";
    let xs: list[str] = [];
    for c in "abc" { w += c; xs.append(w); }
    for s in xs { print(s); }
    return 0;
}

fn captured() -> int {
    let w = "";
    for i in range(3) { w += "ab"; }
    let ys = [len(w) + i for i in range(3)];
    let zs = [w for i in range(2)];
    print(ys[0], ys[2], zs[1]);
    return 0;
}

fn tuple_target() -> int {
    let a = "x";
    let b = "y";
    for i in range(3) { a, b = b, a + "1"; a += "z"; }
    print(a, b);
    return 0;
}

fn main() -> int {
    print(grow_param("é", 3), grow_param("", 0));
    for_target();
    no_extension();
    no_loop();
    snapshot_loop();
    captured();
    tuple_target();
    return 0;
}
'''

PYTHON_PLAIN = r'''def grow_param(p, n):
    for i in range(n): p += "x"
    return p

def for_target():
    for w in ["a", "bc"]:
        w += "!"; print(w)
    return 0

def no_extension():
    t = ""
    for i in range(3):
        t = str(i) + "é"; print(t)
    return 0

def no_loop():
    w = "a"
    w += "b"
    w = w + "c"
    print(w, len(w))
    return 0

def snapshot_loop():
    w = ""
    xs = []
    for c in "abc":
        w += c; xs.append(w)
    for s in xs: print(s)
    return 0

def captured():
    w = ""
    for i in range(3): w += "ab"
    ys = [len(w) + i for i in range(3)]
    zs = [w for i in range(2)]
    print(ys[0], ys[2], zs[1])
    return 0

def tuple_target():
    a = "x"
    b = "y"
    for i in range(3):
        a, b = b, a + "1"; a += "z"
    print(a, b)
    return 0

print(grow_param("é", 3), grow_param("", 0))
for_target()
no_extension()
no_loop()
snapshot_loop()
captured()
tuple_target()
'''

LEAK = r'''fn leaky(n: int) -> int {
    let w = "";
    for i in range(n) { w += "xy"; }
    if len(w) > 0 { raise ValueError; }
    return len(w);
}

fn guarded_leaky(n: int) -> int {
    let w = "";
    for i in range(n) {
        try { w += "xy"; if i == n - 1 { raise ValueError; } } except ValueError { w += "!"; }
    }
    if len(w) > 0 { raise ValueError; }
    return len(w);
}

fn main() -> int {
    let caught = 0;
    for i in range(400) {
        try { leaky(25000); } except ValueError { caught += 1; }
        try { guarded_leaky(25000); } except ValueError { caught += 1; }
    }
    print(caught);
    return 0;
}
'''


def function_body(c, name):
    match = re.search(r'^[^\n(]*\b%s\([^\n]*\) \{\n(.*?)(?=^\S[^\n]*\) \{\n|^static void ail_unwind_|\Z)' % re.escape(name), c, re.M | re.S)
    assert match, name
    return match.group(1)


def unwind(c, name):
    match = re.search(r'^static void ail_unwind_%s\(void \*\*p\) \{[^\n]*' % re.escape(name), c, re.M)
    assert match, name
    return match.group(0)


def run(case, name, source):
    program = build(case, name, source)
    result = subprocess.run(['/usr/bin/time', '-f', '%M', str(program)], capture_output=True, timeout=120)
    return result, int(result.stderr.decode().split()[-1])


LITERALS = ['"a"', '"bc"', '"é"', '"日本"', '"x y"', '"0"', '"zz9"']
SLICES = ['[1:3]', '[:2]', '[2:]', '[-3:]', '[1:-1]', '[0:1]', '[:-2]', '[3:9]', '[-5:-1]']


def _random_function(rng, index):
    """One function with a builder local `w`: loops that extend it (with only borrowing reads in
    them), and straight-line statements that snapshot, reset, reassign and print it."""
    def lit():
        return rng.choice(LITERALS)

    def slc():
        return rng.choice(SLICES)

    def loop_statement(depth):
        kind = rng.randrange(14)
        if kind == 0: return 'w += %s' % lit()
        if kind == 1: return 'w += str(k)'
        if kind == 2: return 'w += t'
        if kind == 3: return 'if len(w) < 60 { w += w; }' if depth == 'ail' else 'if len(w) < 60: w += w'
        if kind == 4: return 'w += w%s' % slc()
        if kind == 5: return 'w = w%s' % slc()
        if kind == 6: return 'w = %s' % lit()
        if kind == 7: return 'w = ""'
        if kind == 8: return 'w = t'
        if kind == 9: return 'd[w] = k'
        if kind == 10: return 'd[w] = d.get(w, 0) + len(w)'
        if kind == 11: return 'if w == %s { w += "!"; }' % lit() if depth == 'ail' else 'if w == %s: w += "!"' % lit()
        if kind == 12: return 'if len(w) > 7 { w = w%s; }' % slc() if depth == 'ail' else 'if len(w) > 7: w = w%s' % slc()
        return 'w = w + %s + str(k)' % lit() if rng.random() < 0.5 else 'w += %s + str(len(w))' % lit()

    def straight_statement(depth):
        kind = rng.randrange(15)
        if kind == 0: return 't = w'
        if kind == 1: return 'xs.append(w)'
        if kind == 2: return 'w = ""'
        if kind == 3: return 'w = %s' % lit()
        if kind == 4: return 'w = t'
        if kind == 5: return 'w = t + w'
        if kind == 6: return 'w = w + t'
        if kind == 7: return 'print(w, len(w), w == t, len(t))'
        if kind == 8: return 'w = w%s' % slc()
        if kind == 9: return 'b.s = w'
        if kind == 10: return 'u = keep(w)'
        if kind == 11: return 't = w%s' % slc()
        if kind == 12: return 'xs.append(w.upper())'
        if kind == 13: return 'print(f"{w}|{t}")'
        return 'if len(w) < 500 { w += w; }' if depth == 'ail' else 'if len(w) < 500: w += w'

    def block(language):
        lines = []
        for _ in range(rng.randrange(1, 4)):
            if rng.random() < 0.5:
                rounds = rng.randrange(1, 6)
                head = 'for k in range(%d) {' % rounds if language == 'ail' else 'for k in range(%d):' % rounds
                body = [loop_statement(language) for _ in range(rng.randrange(1, 5))]
                body.append('w += "k"')               # at least one extension in every loop
                if language == 'ail':
                    lines.append(head)
                    lines.extend('    ' + s + ('' if s.endswith('}') else ';') for s in body)
                    lines.append('}')
                else:
                    lines.append(head)
                    lines.extend('    ' + s for s in body)
            else:
                s = straight_statement(language)
                lines.append(s if language != 'ail' or s.endswith('}') else s + ';')
        return lines

    seed_state = rng.getstate()
    outputs = []
    for language in ('ail', 'py'):
        rng.setstate(seed_state)
        lines = block(language)
        for _ in range(rng.randrange(1, 4)):
            lines.extend(block(language))
        outputs.append(lines)
    ail_lines, py_lines = outputs
    ail = ['fn f%d() -> int {' % index,
           '    let w = "";', '    let t = "seed";', '    let u = "";',
           '    let xs: list[str] = [];', '    let d: dict[str, int] = {};', '    let b = Box("", 0);']
    ail.extend('    ' + line for line in ail_lines)
    ail.extend(['    print(w, t, u, b.s, len(xs), len(d));',
                '    for s in xs { print(s); }',
                '    for key, value in sorted(d.items(), key=lambda kv: (kv[1], kv[0])) { print(key, value); }',
                '    return len(w);', '}'])
    py = ['def f%d():' % index,
          '    w = ""', '    t = "seed"', '    u = ""', '    xs = []', '    d = {}', '    b = Box("", 0)']
    py.extend('    ' + line for line in py_lines)
    py.extend(['    print(w, t, u, b.s, len(xs), len(d))',
               '    for s in xs: print(s)',
               '    for key, value in sorted(d.items(), key=lambda kv: (kv[1], kv[0])): print(key, value)',
               '    return len(w)'])
    return '\n'.join(ail), '\n'.join(py)


def random_programs(seed, count):
    import random
    rng = random.Random(seed)
    ail = ['struct Box { s: str; n: int; }', 'fn keep(w: str) -> str { return w; }']
    py = ['class Box:', '    def __init__(self, s, n): self.s = s; self.n = n',
          'def keep(w): return w']
    names = []
    for index in range(count):
        a, p = _random_function(rng, index)
        ail.append(a)
        py.append(p)
        names.append('f%d' % index)
    ail.append('fn main() -> int {')
    ail.extend('    print(%s());' % name for name in names)
    ail.extend(['    return 0;', '}'])
    py.extend('print(%s())' % name for name in names)
    return '\n'.join(ail) + '\n', '\n'.join(py) + '\n', names


class BuilderLocalTests(unittest.TestCase):
    setUp = support.CObjectTests.setUp
    write = support.CObjectTests.write
    command = support.CObjectTests.command

    def test_matches_python_and_stays_small(self):
        c = pyfunc.to_c(translate(SOURCE), name='run', strict=True)
        for name in BUILDERS:
            body = function_body(c, name)
            self.assertTrue('ail_bl_append(&' in body or 'ail_bl_set(&' in body, name)
            self.assertIn('ail_bl_free(', body, name)             # freed on the return path
            self.assertIn('ail_bl_free(p[', unwind(c, name), name)
            self.assertNotIn('/*b*/', body)
        for name in NOT_BUILDERS:
            self.assertNotIn('ail_bl_', function_body(c, name), name)
        result, rss = run(self, 'builder_locals', SOURCE)
        self.assertEqual(result.returncode, 0, result.stderr.decode(errors='replace'))
        want = subprocess.run([sys.executable, '-c', PYTHON], capture_output=True, check=True).stdout
        self.assertEqual(result.stdout, want)
        self.assertLess(rss, 20000)   # KiB

    def test_ineligible_variables_compile_as_before(self):
        c = pyfunc.to_c(translate(SOURCE_PLAIN), name='run', strict=True)
        self.assertNotIn('ail_bl_', c)                  # not even the runtime part is emitted
        result, _ = run(self, 'builder_plain', SOURCE_PLAIN)
        self.assertEqual(result.returncode, 0, result.stderr.decode(errors='replace'))
        want = subprocess.run([sys.executable, '-c', PYTHON_PLAIN], capture_output=True, check=True).stdout
        self.assertEqual(result.stdout, want)

    def test_exception_out_of_a_builder_function_frees_the_buffer(self):
        c = pyfunc.to_c(translate(LEAK), name='run', strict=True)
        self.assertIn('ail_bl_free(p[', unwind(c, 'leaky'))
        self.assertIn('ail_bl_free(p[', unwind(c, 'guarded_leaky'))
        result, rss = run(self, 'builder_leak', LEAK)
        self.assertEqual(result.returncode, 0, result.stderr.decode(errors='replace'))
        self.assertEqual(result.stdout.decode(), '800\n')
        self.assertLess(rss, 20000)   # 800 leaked 64 KiB buffers would be about 50 MiB

    def test_random_programs_match_python(self):
        # 16 generated functions: loops that extend a builder with only borrowing reads inside,
        # and straight-line snapshots, resets, reassignments and prints between them.
        source, python, names = random_programs(20261012, 16)
        c = pyfunc.to_c(translate(source), name='run', strict=True)
        looped = [name for name in names if 'for k in range' in source.split('fn %s()' % name)[1].split('\nfn ')[0]]
        self.assertGreaterEqual(len(looped), 8)
        for name in looped:
            self.assertIn('ail_bl_append(&', function_body(c, name), name)
        result, _ = run(self, 'builder_random', source)
        self.assertEqual(result.returncode, 0, result.stderr.decode(errors='replace'))
        want = subprocess.run([sys.executable, '-c', python], capture_output=True, check=True).stdout
        self.assertEqual(result.stdout, want)

    def test_unrecognised_use_recompiles_the_function_as_before(self):
        # A raw use of the variable that the builder path did not emit makes `_bl_check` refuse;
        # the function is then compiled exactly as it would be without builders.
        original = pyfunc._bl_check

        def refuse(text, ctx):
            raise pyfunc._BuilderBail('forced')
        pyfunc._bl_check = refuse
        try:
            c = pyfunc.to_c(translate(SOURCE), name='run', strict=True)
        finally:
            pyfunc._bl_check = original
        self.assertNotIn('ail_bl_', c)
        self.assertIn('ail_str_cat(', c)


if __name__ == '__main__':
    unittest.main()

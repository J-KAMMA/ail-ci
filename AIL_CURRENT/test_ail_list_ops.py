"""List insert/index/count/remove, list + list, += and step slices match CPython 3.12.

Each element type (int, float, str, bytes, struct) gets one AIL program that reads a script of
operations from a file and applies them to a list kept in a local variable or a struct field, dumping
the list after every operation.  The same script is replayed by CPython on a plain list and the two
transcripts must be identical, so thousands of random operations (negative and out-of-range indexes,
negative steps, zero steps, absent values) are compared per compiled program.  Step slices of str and
bytes (non-ASCII text included) and `assert` get their own checks.

Struct lists support every operation except index/count/remove: AIL structs have no `==`.
"""
import random
import subprocess
import unittest
import test_ail_c_objects as support
from test_ail_map_fields import build


class Box:
    """CPython stand-in for the AIL struct `P { v: int; }` (identity equality, like the real one)."""

    def __init__(self, v):
        self.v = v


class Kind:
    def __init__(self, name, annotation, values, seed, convert, seed_source, show, py_value, searchable=True):
        self.name, self.annotation, self.values, self.seed = name, annotation, values, seed
        self.convert, self.seed_source, self.show, self.py_value = convert, seed_source, show, py_value
        self.searchable = searchable


KINDS = {
    'int': Kind('int', 'int', ['0', '1', '2', '3', '-1', '7'], ['5', '6'], 'int({})',
                lambda s: s, 'str(x)', int),
    'float': Kind('float', 'float', ['0.5', '1.5', '2.25', '-1.0', '4.0', '0.0', '-0.0'], ['0.5', '8.0'], 'float({})',
                  lambda s: s, 'str(x)', float),
    'str': Kind('str', 'str', ['a', 'b', 'ab', 'é', 'z'], ['a', 'q'], '{}',
                lambda s: '"%s"' % s, '"[" + x + "]"', str),
    'bytes': Kind('bytes', 'bytes', ['a', 'b', 'ab', 'é', 'z'], ['a', 'q'], 'tob({})',
                  lambda s: 'b"%s"' % s, 'x.hex()', lambda text: text.encode()),
    'struct': Kind('struct', 'P', ['0', '1', '2', '3', '7'], ['5', '6'], 'P(int({}))',
                   lambda s: 'P(%s)' % s, 'str(x.v)', lambda text: Box(int(text)), searchable=False),
}

SEARCH_OPS = ('remove', 'index', 'index2', 'index3', 'count')


def make_script(kind, rng, count):
    lines = []
    for _ in range(count):
        roll = rng.random()
        value = rng.choice(kind.values)
        index = rng.choice([0, 1, 2, 3, 5, -1, -2, -4, 9, -9, 40, -40, 2 ** 63 - 1, -2 ** 63])
        step = (rng.choice([1, 2, 3, -1, -2, -3, 5, -5, 100, -100, 2 ** 62, -2 ** 62, 2 ** 63 - 1, -2 ** 63])
                if rng.random() < 0.97 else 0)
        low, high = rng.randrange(-12, 13), rng.randrange(-12, 13)
        if rng.random() < 0.05:
            low = rng.choice([2 ** 63 - 1, -2 ** 63, 2 ** 62])
        if rng.random() < 0.05:
            high = rng.choice([2 ** 63 - 1, -2 ** 63, -2 ** 62])
        if roll < 0.20:
            lines.append('append %s' % value)
        elif roll < 0.38:
            lines.append('insert %d %s' % (index, value))
        elif roll < 0.72 and kind.searchable:
            lines.append(rng.choice([
                'remove %s' % value, 'index %s' % value, 'index2 %s %d' % (value, index),
                'index3 %s %d %d' % (value, index, low), 'count %s' % value, 'count %s' % value]))
        elif roll < 0.76:
            lines.append('pop %d' % index)
        elif roll < 0.80:
            lines.append(rng.choice(['cat', 'catself', 'pluseq', 'plusown', 'dup', 'mix', 'nest', 'insfirst %d' % index]))
        elif roll < 0.83:
            lines.append('rev')
        elif roll < 0.84:
            lines.append('clear')
        else:
            lines.append('%s %d %d %d' % (rng.choice(['s11', 's10', 's01', 's00']), low, high, step))
    return '\n'.join(lines) + '\n'


def ail_source(kind, field):
    t = kind.annotation
    target = 'box.items' if field else 'xs'
    seeds = ', '.join(kind.seed_source(s) for s in kind.seed)
    setup = 'struct P { v: int; }\n' if kind.name == 'struct' else ''
    if field:
        setup += 'struct Box { items: list[%s]; }\n' % t
    declare = 'let box = Box([]);' if field else 'let xs: list[%s] = [];' % t
    dumpx = ('let out = op + ":" + str(len(box.items)); for x in box.items { out += " " + %s; } print(out);'
             % kind.show) if field else 'dump(xs, op);'
    search = '''
        elif op == "remove" { try { %(X)s.remove(%(v1)s); } except ValueError { print("VE"); } }
        elif op == "index" { try { print(%(X)s.index(%(v1)s)); } except ValueError { print("VE"); } }
        elif op == "index2" { try { print(%(X)s.index(%(v1)s, int(p[2]))); } except ValueError { print("VE"); } }
        elif op == "index3" { try { print(%(X)s.index(%(v1)s, int(p[2]), int(p[3]))); } except ValueError { print("VE"); } }
        elif op == "count" { print(%(X)s.count(%(v1)s)); }''' if kind.searchable else ''
    template = setup + '''fn dump(xs: list[%(t)s], tag: str) -> void {
    let out = tag + ":" + str(len(xs));
    for x in xs { out += " " + %(show)s; }
    print(out);
}
fn tob(s: str) -> bytes { return s.encode(); }
fn main() -> int {
    %(declare)s
    let ys: list[%(t)s] = [%(seeds)s];
    let text = read_bytes(sys.argv[1]).decode();
    for line in text.splitlines() {
        let p = line.split(" ");
        let op = p[0];
        if op == "append" { %(X)s.append(%(v1)s); }
        elif op == "insert" { %(X)s.insert(int(p[1]), %(v2)s); }''' + search + '''
        elif op == "pop" { try { %(X)s.pop(int(p[1])); } except IndexError { print("IE"); } }
        elif op == "cat" { %(X)s = %(X)s + ys; }
        elif op == "plusown" { let c1 = ys + %(X)s; dump(c1, "c1"); }
        elif op == "dup" { %(X)s = %(X)s + %(X)s; }
        elif op == "mix" { %(X)s = %(X)s[::-1] + %(X)s[::2]; }
        elif op == "nest" { let z5 = %(X)s[::2][::-1]; dump(z5, "nest"); }
        elif op == "insfirst" { try { %(X)s.insert(int(p[1]), %(X)s[0]); } except IndexError { print("IE"); } }
        elif op == "catself" { %(X)s += %(X)s; }
        elif op == "pluseq" { %(X)s += ys; }
        elif op == "rev" { %(X)s = %(X)s[::-1]; }
        elif op == "clear" { %(X)s.clear(); }
        elif op == "s11" { try { let z1 = %(X)s[int(p[1]):int(p[2]):int(p[3])]; dump(z1, "s11"); } except ValueError { print("VE"); } }
        elif op == "s10" { try { let z2 = %(X)s[int(p[1])::int(p[3])]; dump(z2, "s10"); } except ValueError { print("VE"); } }
        elif op == "s01" { try { let z3 = %(X)s[:int(p[2]):int(p[3])]; dump(z3, "s01"); } except ValueError { print("VE"); } }
        elif op == "s00" { try { let z4 = %(X)s[::int(p[3])]; dump(z4, "s00"); } except ValueError { print("VE"); } }
        while len(%(X)s) > 30 { %(X)s.pop(); }
        %(dumpx)s
    }
    return 0;
}'''
    values = dict(t=t, show=kind.show, declare=declare, seeds=seeds, X=target,
                  v1=kind.convert.format('p[1]'), v2=kind.convert.format('p[2]'), dumpx=dumpx)
    return template % values


def reference(kind, script):
    xs = []
    ys = [kind.py_value(s) for s in kind.seed]
    out = []

    def dump(items, tag):
        parts = [tag + ':' + str(len(items))]
        for x in items:
            parts.append(eval(kind.show))
        out.append(' '.join(parts))
    for line in script.splitlines():
        p = line.split(' ')
        op = p[0]
        value = kind.py_value(p[1]) if op in ('append', 'remove', 'index', 'index2', 'index3', 'count') else None
        if op == 'append':
            xs.append(value)
        elif op == 'insert':
            xs.insert(int(p[1]), kind.py_value(p[2]))
        elif op in ('remove', 'index', 'index2', 'index3'):
            try:
                if op == 'remove':
                    xs.remove(value)
                elif op == 'index':
                    out.append(str(xs.index(value)))
                elif op == 'index2':
                    out.append(str(xs.index(value, int(p[2]))))
                else:
                    out.append(str(xs.index(value, int(p[2]), int(p[3]))))
            except ValueError:
                out.append('VE')
        elif op == 'count':
            out.append(str(xs.count(value)))
        elif op == 'pop':
            try:
                xs.pop(int(p[1]))
            except IndexError:
                out.append('IE')
        elif op == 'cat':
            xs = xs + ys
        elif op == 'plusown':
            dump(ys + xs, 'c1')
        elif op == 'dup':
            xs = xs + xs
        elif op == 'mix':
            xs = xs[::-1] + xs[::2]
        elif op == 'nest':
            dump(xs[::2][::-1], 'nest')
        elif op == 'insfirst':
            try:
                xs.insert(int(p[1]), xs[0])
            except IndexError:
                out.append('IE')
        elif op == 'catself':
            xs += xs
        elif op == 'pluseq':
            xs += ys
        elif op == 'rev':
            xs = xs[::-1]
        elif op == 'clear':
            xs.clear()
        else:
            low, high, step = int(p[1]), int(p[2]), int(p[3])
            try:
                if op == 's11':
                    z = xs[low:high:step]
                elif op == 's10':
                    z = xs[low::step]
                elif op == 's01':
                    z = xs[:high:step]
                else:
                    z = xs[::step]
                dump(z, op)
            except ValueError:
                out.append('VE')
        while len(xs) > 30:
            xs.pop()
        dump(xs, op)
    return '\n'.join(out) + '\n'


TEXT_PIECES = ['a', 'b', 'é', 'ß', '日', '本', '😀', 'x', 'z', '́', 'Ω', '1']

TEXT_SOURCE = r'''fn main() -> int {
    let text = read_bytes(sys.argv[1]).decode();
    for line in text.splitlines() {
        let p = line.split(" ");
        let s = p[0];
        let b = s.encode();
        let lo = int(p[1]); let hi = int(p[2]); let st = int(p[3]);
        try {
            let a1 = s[lo:hi:st]; let a2 = s[lo::st]; let a3 = s[:hi:st]; let a4 = s[::st];
            let b1 = b[lo:hi:st]; let b2 = b[lo::st]; let b3 = b[:hi:st]; let b4 = b[::st];
            print(a1 + "|" + a2 + "|" + a3 + "|" + a4 + "|" + str(len(a4)) + "|" + b1.hex() + "|" + b2.hex()
                  + "|" + b3.hex() + "|" + b4.hex() + "|" + s[::-1] + "|" + b[::-1].hex());
        } except ValueError { print("VE"); }
    }
    return 0;
}'''


def text_reference(lines):
    out = []
    for line in lines:
        s, lo, hi, st = line.split(' ')
        lo, hi, st = int(lo), int(hi), int(st)
        b = s.encode()
        try:
            out.append('|'.join([s[lo:hi:st], s[lo::st], s[:hi:st], s[::st], str(len(s[::st])), b[lo:hi:st].hex(),
                                 b[lo::st].hex(), b[:hi:st].hex(), b[::st].hex(), s[::-1], b[::-1].hex()]))
        except ValueError:
            out.append('VE')
    return '\n'.join(out) + '\n'


class ListOpsTests(unittest.TestCase):
    setUp = support.CObjectTests.setUp
    write = support.CObjectTests.write
    command = support.CObjectTests.command

    def run_program(self, program, script):
        path = self.root / 'script.txt'
        path.write_text(script, encoding='utf-8')
        result = subprocess.run([str(program), str(path)], capture_output=True, timeout=300)
        self.assertEqual(result.returncode, 0, result.stderr.decode(errors='replace'))
        return result.stdout.decode('utf-8')

    def check_kind(self, name, field, seed, operations):
        kind = KINDS[name]
        program = build(self, 'ops_%s_%s' % (name, 'field' if field else 'local'), ail_source(kind, field))
        rng = random.Random(seed)
        for round_number in range(3):
            script = make_script(kind, rng, operations)
            got = self.run_program(program, script)
            want = reference(kind, script)
            if got != want:
                got_lines, want_lines = got.splitlines(), want.splitlines()
                for number, (a, b) in enumerate(zip(got_lines, want_lines)):
                    if a != b:
                        self.fail('kind %s round %d line %d: got %r want %r\nscript tail: %r' % (
                            name, round_number, number, a, b, script.splitlines()[-8:]))
                self.fail('transcript length differs: %d vs %d' % (len(got_lines), len(want_lines)))

    def test_int_local(self):
        self.check_kind('int', False, 1, 1500)

    def test_int_field(self):
        self.check_kind('int', True, 2, 1000)

    def test_float_local(self):
        self.check_kind('float', False, 3, 1200)

    def test_float_field(self):
        self.check_kind('float', True, 4, 800)

    def test_str_local(self):
        self.check_kind('str', False, 5, 1200)

    def test_str_field(self):
        self.check_kind('str', True, 6, 800)

    def test_bytes_local(self):
        self.check_kind('bytes', False, 7, 1200)

    def test_bytes_field(self):
        self.check_kind('bytes', True, 8, 800)

    def test_struct_local(self):
        self.check_kind('struct', False, 9, 1200)

    def test_struct_field(self):
        self.check_kind('struct', True, 10, 800)

    def test_str_and_bytes_step_slices(self):
        program = build(self, 'text_steps', TEXT_SOURCE)
        rng = random.Random(20261012)
        lines = []
        for _ in range(3000):
            text = ''.join(rng.choice(TEXT_PIECES) for _ in range(rng.randrange(1, 14)))
            step = rng.choice([1, 2, 3, -1, -2, -3, -4, 7, -9, 100, -100, 0] if rng.random() < 0.95 else [0])
            lines.append('%s %d %d %d' % (text, rng.randrange(-16, 17), rng.randrange(-16, 17), step))
        lines += ['abc %d %d %d' % (lo, hi, st) for lo in (-2 ** 63, -2 ** 63 + 1, 2 ** 63 - 1, 0)
                  for hi in (-2 ** 63, 2 ** 63 - 1, 1) for st in (-2 ** 63, 2 ** 63 - 1, -1, 1)]
        self.assertEqual(self.run_program(program, '\n'.join(lines) + '\n'), text_reference(lines))

    def test_operations_in_expression_positions(self):
        source = r'''fn cat(a: list[int], b: list[int]) -> list[int] { return a + b; }
fn rev(a: list[int]) -> list[int] { return a[::-1]; }
fn idx(a: list[int], v: int) -> int { return a.index(v) + a.count(v); }
fn main() -> int {
    let xs = [1, 2, 3];
    let ys = cat(xs, rev(xs));
    print(len(ys), ys[3], idx(ys, 3), len(cat(ys, ys)), sum(ys + ys));
    let total = 0;
    for x in xs + ys { total += x; }
    print(total, f"{len(xs + ys)}|{xs.index(2)}");
    let n = 0;
    let zs = [3, 1, 2];
    while zs.index(2) < 5 and n < 3 { n += 1; zs.insert(0, 9); }
    print(n, len(zs));
    let ws = [3, 1, 2];
    let m = 0;
    for i in range(3) { ws = ws + [i]; ws.insert(0, i); m += ws.count(i); }
    print(m, len(ws), (xs + xs)[::-1][0], sorted(xs + [0])[0], max(xs[::-1]), len(xs[::2] + xs[1::2]));
    let words = "a b c".split();
    words.insert(0, "z");
    print(words[0], words.index("c"), len(words + words), len(words[::-1]), words[::-1][0]);
    let e: list[int] = [];
    print(len(xs + e), len(e + xs), len(e + e));
    ws.remove(ws[0]);
    print(len(ws));
    return 0;
}'''
        program = build(self, 'positions', source)
        result = subprocess.run([str(program)], capture_output=True, timeout=60)
        xs = [1, 2, 3]
        ys = xs + xs[::-1]
        zs = [3, 1, 2]
        n = 0
        while zs.index(2) < 5 and n < 3:
            n += 1
            zs.insert(0, 9)
        ws = [3, 1, 2]
        m = 0
        for i in range(3):
            ws = ws + [i]
            ws.insert(0, i)
            m += ws.count(i)
        words = 'a b c'.split()
        words.insert(0, 'z')
        e = []
        want = '%d %d %d %d %d\n' % (len(ys), ys[3], ys.index(3) + ys.count(3), len(ys + ys), sum(ys + ys))
        want += '%d %s\n' % (sum(xs + ys), '%d|%d' % (len(xs + ys), xs.index(2)))
        want += '%d %d\n' % (n, len(zs))
        want += '%d %d %d %d %d %d\n' % (m, len(ws), (xs + xs)[::-1][0], sorted(xs + [0])[0], max(xs[::-1]),
                                         len(xs[::2] + xs[1::2]))
        want += '%s %d %d %d %s\n' % (words[0], words.index('c'), len(words + words), len(words[::-1]), words[::-1][0])
        want += '%d %d %d\n' % (len(xs + e), len(e + xs), len(e + e))
        ws.remove(ws[0])
        want += '%d\n' % len(ws)
        self.assertEqual((result.returncode, result.stdout.decode(), result.stderr.decode()), (0, want, ''))


class AssertTests(unittest.TestCase):
    setUp = support.CObjectTests.setUp
    write = support.CObjectTests.write
    command = support.CObjectTests.command

    def run_source(self, name, source, *args):
        program = build(self, name, source)
        return subprocess.run([str(program), *args], capture_output=True, timeout=60)

    def test_passing_assert_is_silent_and_failure_exits_one(self):
        source = '''fn main() -> int {
    let x = 3;
    assert x == 3;
    assert x > 0, "positive";
    print("before");
    assert x == 4, "x is " + str(x);
    print("after");
    return 0;
}'''
        result = self.run_source('assert_fail', source)
        self.assertEqual((result.returncode, result.stdout, result.stderr),
                         (1, b'before\n', b'AssertionError: x is 3\n'))

    def test_bare_assert_and_numeric_messages(self):
        cases = (('assert 1 == 2;', b'AssertionError\n'), ('assert false, 42;', b'AssertionError: 42\n'),
                 ('assert false, 1.5;', b'AssertionError: 1.5\n'),
                 ('assert not true, "" ;', b'AssertionError\n'))
        for number, (body, message) in enumerate(cases):
            with self.subTest(body=body):
                result = self.run_source('assert_form%d' % number, 'fn main() -> int { %s return 0; }' % body)
                self.assertEqual((result.returncode, result.stdout, result.stderr), (1, b'', message))

    def test_assert_is_catchable_as_assertion_error_only(self):
        source = '''fn check(n: int) -> int { assert n >= 0, "negative: " + str(n); return n; }
fn main() -> int {
    let seen = 0;
    try { check(-5); } except AssertionError as e { print(e.kind, e.message); seen += 1; }
    try { assert 1 == 2; } except AssertionError as e { print(e.kind, "[" + e.message + "]"); seen += 1; }
    try { try { check(-1); } except ValueError { print("wrong handler"); } }
    except (KeyError, AssertionError) as e { print("outer", e.message); seen += 1; }
    try { raise AssertionError("raised"); } except AssertionError as e { print(e.message); seen += 1; }
    try { assert true, "never evaluated " + str([1][3]); } except IndexError { print("evaluated"); }
    print(check(7), seen);
    assert seen == 99, "seen was " + str(seen);
    return 0;
}'''
        result = self.run_source('assert_catch', source)
        self.assertEqual((result.returncode, result.stdout, result.stderr),
                         (1, b'AssertionError negative: -5\nAssertionError []\nouter negative: -1\nraised\n7 4\n',
                          b'AssertionError: seen was 4\n'))


if __name__ == '__main__':
    unittest.main()

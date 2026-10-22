"""Freestanding mode: `compile --freestanding` (python/pkg-v12/freestanding.py, docs/design/FREESTANDING.md).

The oracle for hardware code is a hosted C harness, not CPython. Covered:

* the examples in freestanding/ (ring buffer, bitmap page allocator, CRC-32, VGA text writer over a
  static array, a kernel_main with MMIO and asm) build to objects whose only undefined symbols are the
  declared @extern functions (`nm -u`), and the libc-free ones link with `ld` and nothing else;
* freestanding/harness.c links them and checks them directly (CRC-32 against the zlib constants);
* the pure-logic selftests give the same numbers on CPython through ail_freestanding.load (and the
  CRC-32 matches zlib.crc32 there too), and a plain `import` of the CRC module also runs;
* every width (u8..u64, i8..i64, usize, isize) and operator under @wrapping and @checked, at the edge
  values, gives the same result or trap in C, in the shim and in an independent formula;
* named refusals with "write instead:" hints, the CLI exit status and message, and the build's own
  `nm` check refusing a stray symbol.
"""
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
import zlib
from pathlib import Path

ROOT = Path(__file__).resolve().parent
CLI = str(ROOT / 'ail_chatgpt.py')
EXAMPLES = ROOT / 'freestanding'
CC = os.environ.get('PIPE_CC') or shutil.which('cc') or shutil.which('gcc')
sys.path[:0] = [str(ROOT), str(ROOT / 'python/pkg-v12')]
import ail_freestanding as fs  # noqa: E402
import freestanding  # noqa: E402

MODULES = ('ring', 'pagealloc', 'crc32', 'vga', 'kernel_main')
EXTERNS = {'ring': [], 'pagealloc': [], 'crc32': [], 'vga': ['vga_cursor_moved'], 'kernel_main': ['outb']}


def compile_fs(source, output, env=None):
    return subprocess.run([sys.executable, '-B', CLI, 'compile', '--freestanding', str(source), '-o', str(output)],
                          capture_output=True, text=True, timeout=120, env=env)


@unittest.skipUnless(CC and shutil.which('nm'), 'needs a C compiler and nm')
class Examples(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory(prefix='ail-fs-test-')
        cls.dir = Path(cls.tmp.name)
        for name in MODULES:
            result = compile_fs(EXAMPLES / (name + '.py'), cls.dir / (name + '.o'))
            if result.returncode:
                raise AssertionError('%s: %s' % (name, result.stderr))

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def test_only_declared_externs_are_undefined(self):
        for name in MODULES:
            out = subprocess.run(['nm', '-u', str(self.dir / (name + '.o'))], capture_output=True, text=True, check=True).stdout
            self.assertEqual(sorted(line.split()[-1] for line in out.splitlines() if line.strip()), EXTERNS[name], name)
            self.assertTrue((self.dir / (name + '.h')).is_file())

    @unittest.skipUnless(shutil.which('ld'), 'needs ld')
    def test_links_with_nothing_else(self):
        objs = [str(self.dir / (n + '.o')) for n in ('ring', 'pagealloc', 'crc32')]
        result = subprocess.run(['ld', '-o', str(self.dir / 'bare'), '-e', 'crc32_update', *objs], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_c_output_includes_only_freestanding_headers(self):
        out = self.dir / 'c'
        out.mkdir(exist_ok=True)
        for name in MODULES:
            result = compile_fs(EXAMPLES / (name + '.py'), out / (name + '.c'))
            self.assertEqual(result.returncode, 0, result.stderr)
            text = (out / (name + '.c')).read_text()
            self.assertEqual(sorted(set(re.findall(r'#include <([^>]+)>', text))), ['stdbool.h', 'stddef.h', 'stdint.h'])
            self.assertNotIn('ail_rt', text)
            self.assertNotIn('malloc', text)

    def test_harness_and_cpython_agree(self):
        exe = self.dir / 'harness'
        objs = [str(self.dir / (n + '.o')) for n in ('ring', 'pagealloc', 'crc32', 'vga')]
        build = subprocess.run([*CC.split(), '-std=c11', '-O2', '-I', str(self.dir), str(EXAMPLES / 'harness.c'), *objs,
                                '-o', str(exe)], capture_output=True, text=True)
        self.assertEqual(build.returncode, 0, build.stderr)
        run = subprocess.run([str(exe)], capture_output=True, text=True, timeout=60)
        self.assertEqual(run.returncode, 0, run.stdout + run.stderr)
        self.assertNotIn('FAIL', run.stdout)
        self.assertEqual(run.stdout.splitlines()[-1], 'OK')
        native = {tuple(line.split()[:2]): int(line.split()[2]) for line in run.stdout.splitlines()
                  if line.split()[0] in ('ring', 'pages', 'vga')}
        self.assertEqual(len(native), 36)
        ring = fs.load(EXAMPLES / 'ring.py', 'fs_ring')
        pages = fs.load(EXAMPLES / 'pagealloc.py', 'fs_pagealloc')
        vga = fs.load(EXAMPLES / 'vga.py', 'fs_vga')
        moves = []
        fs.provide('vga_cursor_moved', moves.append)
        for seed in range(3):
            self.assertEqual(ring.ring_selftest(fs.u32(seed)), native['ring', str(seed)], seed)
            self.assertEqual(pages.pa_selftest(fs.u32(seed)), native['pages', str(seed)], seed)
            self.assertEqual(vga.vga_selftest(fs.u32(seed)), native['vga', str(seed)], seed)
        self.assertTrue(moves and all(isinstance(m, fs.u16) for m in moves))

    def test_crc32_on_cpython_matches_zlib(self):
        crc = fs.load(EXAMPLES / 'crc32.py', 'fs_crc32')
        for text in (b'', b'a', b'123456789', bytes(range(256)) * 3):
            buf = fs.Array[fs.u8, max(1, len(text))](list(text))
            self.assertEqual(crc.crc32_update(fs.u32(0), fs.as_ptr(buf), fs.usize(len(text))), zlib.crc32(text))

    def test_plain_import_runs_too(self):
        code = ('import zlib, crc32, ail_freestanding as fs\n'
                'b = fs.Array[fs.u8, 9](list(b"123456789"))\n'
                'assert crc32.crc32_update(0, fs.as_ptr(b), 9) == zlib.crc32(b"123456789")\nprint("ok")\n')
        env = dict(os.environ, PYTHONPATH=os.pathsep.join([str(ROOT), str(EXAMPLES)]))
        result = subprocess.run([sys.executable, '-B', '-c', code], capture_output=True, text=True, env=env, cwd=str(EXAMPLES))
        self.assertEqual(result.stdout.strip(), 'ok', result.stderr)


# ------------------------------------------------------------------------------- arithmetic grid

TYPES = [('u8', 8, False), ('u16', 16, False), ('u32', 32, False), ('u64', 64, False), ('usize', 64, False),
         ('i8', 8, True), ('i16', 16, True), ('i32', 32, True), ('i64', 64, True), ('isize', 64, True)]
BINARY = {'add': '+', 'sub': '-', 'mul': '*', 'div': '//', 'mod': '%', 'shl': '<<', 'shr': '>>', 'and': '&',
          'or': '|', 'xor': '^'}
UNARY = {'neg': '-', 'inv': '~'}


def edges(bits, signed):
    if signed:
        lo, hi = -(1 << (bits - 1)), (1 << (bits - 1)) - 1
        return [lo, lo + 1, -7, -2, -1, 0, 1, 2, 7, bits - 1, bits, hi - 1, hi]
    hi = (1 << bits) - 1
    return [0, 1, 2, 3, 7, bits - 1, bits, hi // 2, hi - 1, hi]


def c_literal(v, bits, signed):
    if signed and bits == 64 and v == -(1 << 63):
        return '(-9223372036854775807LL - 1)'
    return '%d%s' % (v, ('LL' if signed else 'ULL') if bits == 64 else ('' if signed else 'U'))


def formula(op, mode, bits, signed, a, b=None):
    lo = -(1 << (bits - 1)) if signed else 0
    hi = (1 << (bits - 1)) - 1 if signed else (1 << bits) - 1

    def wrap(r):
        r &= (1 << bits) - 1
        return r - (1 << bits) if signed and r > hi else r
    if op in ('neg', 'inv'):
        r = -a if op == 'neg' else ~a
        if mode == 'c' and op == 'neg' and not lo <= r <= hi:
            return 'trap'
        return wrap(r)
    if op in ('shl', 'shr'):
        if not 0 <= b < bits:
            return 'trap'
        return wrap(a << b if op == 'shl' else a >> b)
    if op in ('div', 'mod') and b == 0:
        return 'trap'
    r = {'add': a + b, 'sub': a - b, 'mul': a * b, 'div': a // b if b else 0, 'mod': a % b if b else 0,
         'and': a & b, 'or': a | b, 'xor': a ^ b}[op]
    if mode == 'c' and op in ('add', 'sub', 'mul', 'div', 'mod') and not lo <= r <= hi:
        return 'trap'
    return wrap(r)


def grid_module():
    lines = ['from ail_freestanding import *', '']
    for t, _, _ in TYPES:
        for mode, deco in (('w', 'wrapping'), ('c', 'checked')):
            for op, sym in BINARY.items():
                lines += ['@%s' % deco, 'def %s_%s_%s(a: %s, b: %s) -> %s:' % (mode, op, t, t, t, t),
                          '    return a %s b' % sym, '']
            for op, sym in UNARY.items():
                lines += ['@%s' % deco, 'def %s_%s_%s(a: %s) -> %s:' % (mode, op, t, t, t), '    return %sa' % sym, '']
    return '\n'.join(lines)


def grid_harness(header):
    """One small driver per width over tables of function pointers; a trap (SIGILL/SIGTRAP) jumps back."""
    out = ['#include <inttypes.h>', '#include <setjmp.h>', '#include <signal.h>', '#include <stdio.h>',
           '#include "%s"' % header, 'static sigjmp_buf jb;', 'static void on_trap(int s) { (void)s; siglongjmp(jb, 1); }']
    mains = []
    for t, bits, signed in TYPES:
        ctype = {'usize': 'uintptr_t', 'isize': 'intptr_t'}.get(t, ('int%d_t' if signed else 'uint%d_t') % bits)
        values = edges(bits, signed)
        fmt, cast = ('PRId64', 'int64_t') if signed else ('PRIu64', 'uint64_t')
        binary = ['%s_%s_%s' % (m, op, t) for m in 'wc' for op in BINARY]
        unary = ['%s_%s_%s' % (m, op, t) for m in 'wc' for op in UNARY]
        out += [
            'static void run_%s(void) {' % t,
            '    static const %s E[] = {%s};' % (ctype, ', '.join(c_literal(v, bits, signed) for v in values)),
            '    static %s (*const B[])(%s, %s) = {%s};' % (ctype, ctype, ctype, ', '.join(binary)),
            '    static const char *const BN[] = {%s};' % ', '.join('"%s"' % f for f in binary),
            '    static %s (*const U[])(%s) = {%s};' % (ctype, ctype, ', '.join(unary)),
            '    static const char *const UN[] = {%s};' % ', '.join('"%s"' % f for f in unary),
            '    const int N = %d;' % len(values),
            '    for (int f = 0; f < %d; f++) for (int i = 0; i < N; i++) for (int j = 0; j < N; j++) {' % len(binary),
            '        if (!sigsetjmp(jb, 1)) printf("%%s %%d %%d %%" %s "\\n", BN[f], i, j, (%s)B[f](E[i], E[j]));' % (fmt, cast),
            '        else printf("%s %d %d trap\\n", BN[f], i, j);',
            '    }',
            '    for (int f = 0; f < %d; f++) for (int i = 0; i < N; i++) {' % len(unary),
            '        if (!sigsetjmp(jb, 1)) printf("%%s %%d -1 %%" %s "\\n", UN[f], i, (%s)U[f](E[i]));' % (fmt, cast),
            '        else printf("%s %d -1 trap\\n", UN[f], i);',
            '    }',
            '}']
        mains.append('    run_%s();' % t)
    out += ['int main(void) {', '    struct sigaction sa = {0}; sa.sa_handler = on_trap; sigemptyset(&sa.sa_mask);',
            '    sigaction(SIGILL, &sa, 0); sigaction(SIGTRAP, &sa, 0);'] + mains + ['    return 0;', '}', '']
    return '\n'.join(out)


@unittest.skipUnless(CC, 'needs a C compiler')
class ArithmeticGrid(unittest.TestCase):
    def test_every_width_and_operator(self):
        with tempfile.TemporaryDirectory(prefix='ail-fs-grid-') as tmp:
            tmp = Path(tmp)
            (tmp / 'arith.py').write_text(grid_module())
            result = compile_fs(tmp / 'arith.py', tmp / 'arith.o')
            self.assertEqual(result.returncode, 0, result.stderr)
            (tmp / 'grid.c').write_text(grid_harness('arith.h'))
            build = subprocess.run([*CC.split(), '-std=gnu11', '-O1', '-I', str(tmp), str(tmp / 'grid.c'), str(tmp / 'arith.o'),
                                    '-o', str(tmp / 'grid')], capture_output=True, text=True)
            self.assertEqual(build.returncode, 0, build.stderr)
            run = subprocess.run([str(tmp / 'grid')], capture_output=True, text=True, timeout=120)
            self.assertEqual(run.returncode, 0, run.stderr)
            native = {}
            for line in run.stdout.splitlines():
                f, i, j, r = line.split()
                native[f, int(i), int(j)] = r if r == 'trap' else int(r)
            shim = fs.load(tmp / 'arith.py', 'fs_arith')
        checked = 0
        traps = 0
        for t, bits, signed in TYPES:
            T = getattr(fs, t)
            values = edges(bits, signed)
            for mode in 'wc':
                for op in list(BINARY) + list(UNARY):
                    f = '%s_%s_%s' % (mode, op, t)
                    fn = getattr(shim, f)
                    pairs = [(i, -1) for i in range(len(values))] if op in UNARY else \
                        [(i, j) for i in range(len(values)) for j in range(len(values))]
                    for i, j in pairs:
                        args = (values[i],) if j < 0 else (values[i], values[j])
                        want = formula(op, mode, bits, signed, *args)
                        try:
                            got = fn(*(T(a) for a in args))
                            self.assertIs(type(got), T, f)
                            got = int(got)
                        except fs.Trap:
                            got = 'trap'
                        self.assertEqual(native[f, i, j], want, '%s%r: C' % (f, args))
                        self.assertEqual(got, want, '%s%r: shim' % (f, args))
                        checked += 1
                        traps += want == 'trap'
        self.assertGreater(checked, 4000)
        self.assertGreater(traps, 300)


RANGE_MODULE = '''from ail_freestanding import *

@wrapping
def up3_u8(a: u8, b: u8) -> u32:
    t: u32 = 0
    for i in range(a, b, 3):
        if i == 9:
            continue
        t = t * 31 + u32(i) + 1
    return t

@wrapping
def down5_i8(a: i8, b: i8) -> u32:
    t: u32 = 0
    for i in range(a, b, -5):
        t = t * 31 + u32(i) + 1
    return t

@wrapping
def up1_u8(a: u8, b: u8) -> u32:
    t: u32 = 0
    for i in range(a, b):
        if i == 200:
            break
        t = t * 31 + u32(i) + 1
    return t

@wrapping
def up7_u64(a: u64, b: u64) -> u64:
    t: u64 = 0
    for i in range(a, b, 7):
        t = t * 31 + i + 1
    return t
'''
RANGE_CASES = [('up3_u8', 'uint8_t', 8, False, [0, 1, 9, 10, 250, 252, 253, 254, 255]),
               ('down5_i8', 'int8_t', 8, True, [-128, -127, -124, -5, 0, 3, 120, 123, 127]),
               ('up1_u8', 'uint8_t', 8, False, [0, 1, 199, 200, 201, 254, 255]),
               ('up7_u64', 'uint64_t', 64, False, [(1 << 64) - k for k in (60, 30, 9, 8, 7, 2, 1)])]


def range_formula(name, a, b):
    step = {'up3_u8': 3, 'down5_i8': -5, 'up1_u8': 1, 'up7_u64': 7}[name]
    bits = 64 if name.endswith('u64') else 32
    t = 0
    for i in range(a, b, step):
        if name == 'up3_u8' and i == 9:
            continue
        if name == 'up1_u8' and i == 200:
            break
        t = (t * 31 + (i & ((1 << bits) - 1)) + 1) & ((1 << bits) - 1)
    return t


@unittest.skipUnless(CC, 'needs a C compiler')
class RangeLoops(unittest.TestCase):
    def test_steps_near_the_ends_of_the_width(self):
        """range with steps that would overflow the counter if it simply added the step."""
        lines = ['#include <inttypes.h>', '#include <stdio.h>', '#include "ranges.h"', 'int main(void) {']
        for name, ctype, bits, signed, values in RANGE_CASES:
            lit = ', '.join(c_literal(v, bits, signed) for v in values)
            lines.append('  { static const %s E[] = {%s}; for (int i = 0; i < %d; i++) for (int j = 0; j < %d; j++)'
                         ' printf("%s %%d %%d %%" PRIu64 "\\n", i, j, (uint64_t)%s(E[i], E[j])); }' % (
                             ctype, lit, len(values), len(values), name, name))
        lines += ['  return 0;', '}']
        with tempfile.TemporaryDirectory(prefix='ail-fs-range-') as tmp:
            tmp = Path(tmp)
            (tmp / 'ranges.py').write_text(RANGE_MODULE)
            result = compile_fs(tmp / 'ranges.py', tmp / 'ranges.o')
            self.assertEqual(result.returncode, 0, result.stderr)
            (tmp / 'main.c').write_text('\n'.join(lines) + '\n')
            build = subprocess.run([*CC.split(), '-O2', '-I', str(tmp), str(tmp / 'main.c'), str(tmp / 'ranges.o'), '-o', str(tmp / 'main')],
                                   capture_output=True, text=True)
            self.assertEqual(build.returncode, 0, build.stderr)
            run = subprocess.run([str(tmp / 'main')], capture_output=True, text=True, timeout=60)
            shim = fs.load(tmp / 'ranges.py', 'fs_ranges')
        native = {(f, int(i), int(j)): int(r) for f, i, j, r in (line.split() for line in run.stdout.splitlines())}
        for name, _, bits, signed, values in RANGE_CASES:
            T = getattr(fs, name.split('_')[1])
            for i, a in enumerate(values):
                for j, b in enumerate(values):
                    want = range_formula(name, a, b)
                    self.assertEqual(native[name, i, j], want, '%s(%d, %d): C' % (name, a, b))
                    self.assertEqual(getattr(shim, name)(T(a), T(b)), want, '%s(%d, %d): shim' % (name, a, b))


# ------------------------------------------------------------------------------------- refusals

REFUSALS = [
    ('def f(a: int) -> u32:\n    return 1\n', 'the annotation int has no fixed width'),
    ('def f(a: u32) -> u32:\n    return a + 1\n', 'needs a declared overflow rule; write instead: @wrapping or @checked'),
    ('@checked\ndef f(a: u32) -> u32:\n    return a / 2\n', 'write instead: a // b'),
    ('@checked\ndef f(a: u32) -> u32:\n    return a ** 2\n', 'write instead: a loop or a shift'),
    ('def f() -> None:\n    x = [1, 2]\n', 'a list needs the runtime; write instead: Array[T, N]'),
    ('def f() -> None:\n    d = {}\n', 'a dict needs the runtime; write instead:'),
    ('def f() -> None:\n    s = "hi"\n', 'a str needs the runtime; write instead:'),
    ('def f() -> None:\n    print(1)\n', 'print() needs the runtime; write instead: write bytes to a device'),
    ('def f() -> None:\n    try:\n        pass\n    except Exception:\n        pass\n', 'exceptions need the runtime; write instead: return an error code'),
    ('def f() -> None:\n    raise ValueError()\n', 'raise needs the runtime; write instead:'),
    ('def f() -> None:\n    with g():\n        pass\n', 'with needs the runtime'),
    ('def f() -> None:\n    def g() -> None:\n        pass\n', 'a nested function needs closures; write instead:'),
    ('def f() -> None:\n    g = lambda: 1\n', 'a lambda needs closures'),
    ('def f() -> None:\n    yield 1\n', 'a generator needs the runtime'),
    ('def f() -> None:\n    x = [i for i in range(3)]\n', 'a comprehension needs the runtime'),
    ('def f(x: float) -> None:\n    pass\n', 'floats are off in freestanding mode'),
    ('def f() -> None:\n    x: u32 = 1.5\n', 'floats are off in freestanding mode'),
    ('def f(s: str) -> None:\n    pass\n', 'the type str needs the runtime'),
    ('def f(s: list[u8]) -> None:\n    pass\n', 'the type list needs the runtime'),
    ('class A:\n    x: u32\n', 'class A is not a @struct; write instead: @struct'),
    ('@struct\nclass A:\n    x: u32\n@struct\nclass B(A):\n    y: u32\n', 'struct B inherits; write instead: composition'),
    ('@struct\nclass A:\n    x: u32\n    def __init__(self):\n        pass\n', 'the special method __init__ needs the object runtime'),
    ('import os\n', 'import os'),
    ('from math import gcd\n', 'importing math needs the runtime'),
    ('def f(a: u8, b: u32) -> u32:\n    return a & b\n', 'mixes u8 and u32; write instead: convert one side'),
    ('def f() -> u8:\n    return 300\n', 'the literal 300 does not fit u8; write instead: u8(300)'),
    ('def f(a: u32) -> u32:\n    if a:\n        return 1\n', 'can reach its end without returning a u32'),
    ('n: u32 = 0\ndef f() -> None:\n    n = 1\n', 'write instead: global n'),
    ('def f() -> None:\n    x = 5\n', 'gets an integer literal with no width; write instead: x: u32 = 5'),
    ('def f() -> None:\n    for x in [1, 2]:\n        pass\n', 'needs an iterator object; write instead: for i in range(len(xs))'),
    ('def f(a: Ptr[u32]) -> Ptr[u32]:\n    return a + 1\n', 'arithmetic on a pointer; write instead: p.offset(n)'),
    ('def f(a: u32) -> bool:\n    return a is a\n', 'the comparison is'),
    ('@struct\nclass R:\n    x: u32\ndef f(r: R) -> None:\n    pass\n', 'takes a R by value'),
    ('def f(a: Array[u8, 4]) -> None:\n    pass\n', 'by value'),
    ('def f() -> None:\n    a = Array[u8, 4]()\n    b = a\n', 'copying a Array[u8, 4]'),
    ('def f() -> None:\n    a = Array[u8, 4]()\n    a[4] = 1\n', 'index 4 is outside Array[u8, 4]'),
    ('def f() -> None:\n    a = Array[u8, 4]()\n    a[-1] = 1\n', 'negative indexes from the end are not part of the subset'),
    ('def f(a: u32) -> None:\n    match a:\n        case x:\n            pass\n', 'a capture pattern'),
    ('def f() -> None:\n    global q\n', 'global q does not name a static'),
    ('def int8_t() -> None:\n    pass\n', 'is reserved in the generated C'),
    ('def f(a: u32) -> u32:\n    return a << 32\n', 'shift count 32 is outside 0..31'),
    ('def f(p: Ptr[u32]) -> None:\n    q = addr_of(p[0])\n', 'CPython has no reference to an int'),
    ('def f(a: u32) -> u32:\n    return a.bit_length()\n', 'the method bit_length on a u32 needs the runtime'),
    ('def f() -> None:\n    if True:\n        r = Array[u8, 2]()\n', 'inside a block'),
    ('async def f() -> None:\n    pass\n', 'async functions need the runtime'),
    ('print(1)\n', 'runs at import time'),
    ('def f() -> None:\n    asm(1)\n', 'asm takes one string literal'),
    ('def f(x: u32) -> u32:\n    return f\n', 'a Fn[[u32], u32] value where a u32 is expected'),
    ('def f(a: u32, *rest: u32) -> None:\n    pass\n', 'defaults, *args'),
    ('def f(a: u32) -> None:\n    x, y = a, a\n', 'tuple assignment'),
    ('from ail_freestanding import u8\ndef f(a: u32) -> None:\n    pass\n', 'u32 is not imported'),
]


class Refusals(unittest.TestCase):
    def test_named_refusals(self):
        for source, expected in REFUSALS:
            text = source if 'from ail_freestanding' in source else 'from ail_freestanding import *\n' + source
            with self.subTest(source=source):
                with self.assertRaises(freestanding.Refusal) as caught:
                    freestanding.translate(text, 'm.py')
                self.assertIn(expected, caught.exception.text())

    def test_accepted_forms(self):
        source = ('from ail_freestanding import *\n'
                  'K = 1 << 4\n'
                  'table: Array[u8, 4] = Array[u8, 4]([1, 2, 3])\n'
                  'head: Ptr[u32] = Ptr[u32](0)\n'
                  '@struct\nclass Node:\n    next: Ptr["Node"]\n    value: i32\n'
                  'def walk(n: Ptr[Node]) -> i32:\n'
                  '    total: i32 = 0\n'
                  '    while addr(n) != 0:\n'
                  '        total = checked(total + n.value)\n'
                  '        n = n.next\n'
                  '    assert total >= 0\n'
                  '    return total\n'
                  'def pick(x: u8) -> u8:\n'
                  '    match x:\n        case 1 | 2:\n            return 10\n        case 3:\n            return u8(K)\n'
                  '        case _:\n            return x\n'
                  'if __name__ == "__main__":\n    print("hosted only")\n')
        c, h, externs = freestanding.translate(source, 'node.py')
        self.assertIn('struct Node {\n    Node *next;\n    int32_t value;\n};', c)
        self.assertIn('uint8_t table[4] = {((uint8_t)1u), ((uint8_t)2u), ((uint8_t)3u)};', c)
        self.assertIn('extern uint8_t table[4];', h)
        self.assertIn('int32_t walk(Node *n);', h)
        self.assertNotIn('hosted only', c)
        self.assertEqual(externs, [])


@unittest.skipUnless(CC and shutil.which('nm'), 'needs a C compiler and nm')
class Cli(unittest.TestCase):
    def test_refusal_exit_status_and_position(self):
        with tempfile.TemporaryDirectory(prefix='ail-fs-cli-') as tmp:
            src = Path(tmp) / 'bad.py'
            src.write_text('from ail_freestanding import *\n\ndef f() -> None:\n    print(1)\n')
            result = compile_fs(src, Path(tmp) / 'bad.o')
            self.assertEqual(result.returncode, 3, result.stderr)
            self.assertIn('bad.py:4: print() needs the runtime; write instead:', result.stderr)
            self.assertFalse((Path(tmp) / 'bad.o').exists())

    def test_build_refuses_a_stray_symbol(self):
        with tempfile.TemporaryDirectory(prefix='ail-fs-cli-') as tmp:
            src = Path(tmp) / 'buf.py'
            src.write_text('from ail_freestanding import *\n\ndef f(i: u32) -> u8:\n    b = Array[u8, 64]()\n'
                           '    b[i % 64] = 1\n    return b[0]\n'.replace('i % 64', 'i & 63'))
            env = dict(os.environ, AIL_FS_CFLAGS='-fstack-protector-all')
            result = compile_fs(src, Path(tmp) / 'buf.o', env=env)
            self.assertEqual(result.returncode, 2, result.stdout + result.stderr)
            self.assertIn('undeclared symbols __stack_chk_fail', result.stderr)
            self.assertFalse((Path(tmp) / 'buf.o').exists())

    def test_flag_combinations_refused(self):
        with tempfile.TemporaryDirectory(prefix='ail-fs-cli-') as tmp:
            result = subprocess.run([sys.executable, '-B', CLI, 'compile', '--freestanding', '--static',
                                     str(EXAMPLES / 'ring.py'), '-o', str(Path(tmp) / 'r.o')], capture_output=True, text=True)
            self.assertEqual(result.returncode, 2)
            self.assertIn('--freestanding builds one module alone', result.stderr)
            result = subprocess.run([sys.executable, '-B', CLI, 'compile', '--freestanding',
                                     str(EXAMPLES / 'ring.py'), '-o', str(Path(tmp) / 'r')], capture_output=True, text=True)
            self.assertIn('must end in .c', result.stderr)


class Shim(unittest.TestCase):
    def test_traps_and_hardware(self):
        a = fs.Array[fs.u8, 2]()
        with self.assertRaises(fs.Trap):
            a[2] = 1
        with self.assertRaises(fs.Trap):
            a[-1]
        with self.assertRaises(TypeError):
            a[0] = 256
        with self.assertRaises(fs.HardwareAccess):
            fs.volatile_load(fs.Ptr[fs.u16](0xB8000))
        with self.assertRaises(fs.HardwareAccess):
            fs.asm('hlt')
        self.assertEqual(fs.u8(300), 44)
        self.assertEqual(fs.i8(200), -56)
        p = fs.as_ptr(a)
        fs.volatile_store(p.offset(1), fs.u8(9))
        self.assertEqual(a[1], 9)


if __name__ == '__main__':
    unittest.main()

"""Freestanding mode, increment 2: asm operands, function pointers, @interrupt, @packed/@align, --m32, and the toy kernel.

Covered (docs/design/FREESTANDING.md sections 2.7, 2.8, 7):

* asm operands: instructions with inputs, outputs, memory operands, an immediate and clobbers run on
  the build machine (bswap, mulq against a 128-bit product, lea, rep movsb, cpuid, a Linux `syscall`
  in a static program that has no libc), and `out`/`in`/`lidt` are checked by their encoding; the
  vetted-constraint list and the operand count are refused by name;
* Fn[[...], ...] function pointers in locals, statics, struct fields, Array tables, parameters and
  results, compared between the C build, the CPython shim and a formula; the null pointer;
* @interrupt handlers: the object has iretq (and pops the error code), the CPU's frame layout is
  reproduced on the stack of an ordinary process and the handler is entered with a jump, so the frame
  fields, the error code and the return are exercised for real;
* @packed and @align(n): the checker's size and alignment of every struct is asserted against the C
  compiler in the generated code (both targets) and against the shim's size_of;
* --m32: the examples build for 32-bit x86, usize is 32 bits, and a static i386 program runs;
* the toy kernel (freestanding/kernel/): built and linked into an ELF with `gcc -ffreestanding -nostdlib
  -T linker.ld`; the multiboot headers, the entry symbol, the absence of libc references, the pure parts
  in a hosted harness, and the console and IDT code against the CPython shim. Booting it needs QEMU.
"""
import ast
import os
import re
import shutil
import struct
import subprocess
import sys
import tempfile
import textwrap
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent
CLI = str(ROOT / 'ail_chatgpt.py')
EXAMPLES = ROOT / 'freestanding'
KERNEL = EXAMPLES / 'kernel'
CC = os.environ.get('PIPE_CC') or shutil.which('cc') or shutil.which('gcc')
sys.path[:0] = [str(ROOT), str(ROOT / 'python/pkg-v12')]
import ail_freestanding as fs  # noqa: E402
import freestanding  # noqa: E402

HEAD = 'from ail_freestanding import *\narithmetic("wrapping")\n'


def with_head(source):
    return source if 'from ail_freestanding' in source else HEAD + source
NEEDS_TOOLS = unittest.skipUnless(CC and shutil.which('nm') and shutil.which('objdump'), 'needs a C compiler, nm and objdump')


def compile_fs(source, output, *flags, env=None):
    return subprocess.run([sys.executable, '-B', CLI, 'compile', '--freestanding', *flags, str(source), '-o', str(output)],
                          capture_output=True, text=True, timeout=120, env=env)


def run(cmd, **kw):
    return subprocess.run([str(c) for c in cmd], capture_output=True, text=True, timeout=120, **kw)


class Workdir(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory(prefix='ail-fs2-test-')
        cls.dir = Path(cls.tmp.name)

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def module(self, name, source, *flags, env=None):
        """Write `source` as name.py and compile it to name.o; returns the module's Path (name.py)."""
        src = self.dir / (name + '.py')
        src.write_text(source)
        result = compile_fs(src, self.dir / (name + '.o'), *flags, env=env)
        self.assertEqual(result.returncode, 0, result.stderr)
        return src

    def link_and_run(self, name, harness, *objs, flags=(), run_args=()):
        c = self.dir / (name + '_harness.c')
        c.write_text(textwrap.dedent(harness))
        exe = self.dir / (name + '_exe')
        build = run([*CC.split(), '-std=gnu11', '-O2', '-mno-red-zone', '-no-pie', '-I', self.dir, *flags, c,
                     *[self.dir / (o + '.o') for o in objs], '-o', exe])
        self.assertEqual(build.returncode, 0, build.stderr)
        out = run([exe, *run_args])
        self.assertEqual(out.returncode, 0, out.stdout + out.stderr)
        self.assertNotIn('FAIL', out.stdout)
        return out.stdout

    def disassemble(self, obj, symbol):
        out = run(['objdump', '-d', '--no-show-raw-insn', '--disassemble=' + symbol, self.dir / (obj + '.o')])
        self.assertEqual(out.returncode, 0, out.stderr)
        return out.stdout


CHECK = '#define CHECK(c) do { if (!(c)) { printf("FAIL %s:%d: %s\\n", __FILE__, __LINE__, #c); failures++; } } while (0)\n'


# ------------------------------------------------------------------------------------ asm operands

ASM_SOURCE = HEAD + '''
def bswap32(x: u32) -> u32:
    asm("bswap %0", outputs=[("+r", x)], volatile=False)
    return x

def mulhi(a: u64, b: u64) -> u64:
    lo: u64 = 0
    hi: u64 = 0
    asm("mulq %3", outputs=[("=a", lo), ("=d", hi)], inputs=[("a", a), ("r", b)], clobbers=["cc"], volatile=False)
    return hi

def lea4(a: u64, b: u64) -> u64:
    r: u64 = 0
    asm("lea (%1,%2,4), %0", outputs=[("=r", r)], inputs=[("r", a), ("r", b)], volatile=False)
    return r

def add7(x: u32) -> u32:
    asm("addl %1, %0", outputs=[("+r", x)], inputs=[("i", u32(7))], volatile=False)
    return x

def store_via_m(p: Ptr[u32], v: u32) -> None:
    asm("movl %1, %0", outputs=[("=m", p[0])], inputs=[("r", v)])

def copy_bytes(d: Ptr[u8], s: Ptr[u8], n: usize) -> None:
    asm("rep movsb", outputs=[("+D", d), ("+S", s), ("+c", n)])

def cpuid_vendor(out: Ptr[u32]) -> None:
    a: u32 = 0
    b: u32 = 0
    c: u32 = 0
    d: u32 = 0
    asm("cpuid", outputs=[("=a", a), ("=b", b), ("=c", c), ("=d", d)], inputs=[("a", u32(0)), ("c", u32(0))])
    out[0] = b
    out[1] = d
    out[2] = c

def clobbered(x: u64) -> u64:
    asm("movq $1, %%rbx", clobbers=["rbx"])
    return x

def outb_port(port: u16, value: u8) -> None:
    asm("outb %0, %1", inputs=[("a", value), ("Nd", port)])

def outb_fixed(value: u8) -> None:
    asm("outb %0, %1", inputs=[("a", value), ("N", u16(0x80))])

def inb_port(port: u16) -> u8:
    v: u8 = 0
    asm("inb %1, %0", outputs=[("=a", v)], inputs=[("Nd", port)])
    return v
'''

ASM_HARNESS = '''
#include <cpuid.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>
#include "asm_ops.h"
static int failures;
''' + CHECK + '''
int main(void) {
    CHECK(bswap32(0x12345678u) == 0x78563412u);
    uint64_t state = 88172645463325252ull;
    for (int i = 0; i < 2000; i++) {
        state ^= state << 13; state ^= state >> 7; state ^= state << 17;
        uint64_t a = state;
        state ^= state << 13; state ^= state >> 7; state ^= state << 17;
        uint64_t b = state;
        CHECK(mulhi(a, b) == (uint64_t)(((unsigned __int128)a * b) >> 64));
        CHECK(lea4(a, b) == a + b * 4);
        CHECK(bswap32((uint32_t)a) == __builtin_bswap32((uint32_t)a));
        CHECK(add7((uint32_t)a) == (uint32_t)a + 7u);
    }
    CHECK(mulhi(~0ull, ~0ull) == 0xFFFFFFFFFFFFFFFEull);
    uint32_t slot[3] = {1, 2, 3};
    store_via_m(&slot[1], 0xCAFEF00Du);
    CHECK(slot[0] == 1 && slot[1] == 0xCAFEF00Du && slot[2] == 3);
    uint8_t src[40], dst[40];
    for (int i = 0; i < 40; i++) { src[i] = (uint8_t)(i * 7 + 1); dst[i] = 0xEE; }
    copy_bytes(dst + 3, src + 5, 17);
    CHECK(memcmp(dst + 3, src + 5, 17) == 0 && dst[2] == 0xEE && dst[20] == 0xEE);
    uint32_t v[3], e[4];
    cpuid_vendor(v);
    __cpuid(0, e[0], e[1], e[2], e[3]);
    CHECK(v[0] == e[1] && v[1] == e[3] && v[2] == e[2]);
    CHECK(clobbered(77) == 77);
    puts(failures ? "FAILED" : "OK");
    return failures != 0;
}
'''

SYSCALL_SOURCE = HEAD + '''
msg: Array[u8, 14] = Array[u8, 14](b"hello, kernel\\n")

def sys_write(fd: u64, buf: Ptr[u8], n: u64) -> u64:
    ret: u64 = 0
    asm("syscall", outputs=[("=a", ret)], inputs=[("a", u64(1)), ("D", fd), ("S", buf), ("d", n)], clobbers=["rcx", "r11"])
    return ret

def ail_main() -> u32:
    return u32(sys_write(1, as_ptr(msg), u64(len(msg))))
'''

ASM_REFUSALS = [
    ('def f(x: u32) -> None:\n    asm("nop", inputs=[("zz", x)])\n', "the asm constraint 'zz' is not in the vetted list for inputs"),
    ('def f(x: u32) -> None:\n    asm("nop", outputs=[("r", x)])\n', "the asm constraint 'r' is not in the vetted list for outputs"),
    ('def f(x: u32) -> None:\n    asm("nop", inputs=[("=r", x)])\n', "the asm constraint '=r' is not in the vetted list"),
    ('def f(x: u32) -> None:\n    asm("nop", clobbers=["xmm0"])\n', 'asm clobber'),
    ('def f(x: u32) -> None:\n    asm("nop", clobbers=["eax"])\n', 'asm clobber'),
    ('def f(x: u32) -> None:\n    asm("nop", inputs=[("r", 5)])\n', 'an integer literal has no width'),
    ('def f(x: u32) -> None:\n    asm("nop", inputs=[("i", x)])\n', "needs a compile-time constant"),
    ('def f(x: u32) -> None:\n    asm("nop", outputs=[("=r", u32(5))])\n', 'with no storage'),
    ('def f(x: u32) -> None:\n    asm("movl %2, %0", outputs=[("=r", x)], inputs=[("r", x)])\n', 'uses operand %2 but there are 2'),
    ('def f(x: u32) -> None:\n    asm("nop", flags=[])\n', 'asm keyword flags'),
    ('def f(x: u32) -> None:\n    asm("nop", inputs=x)\n', 'takes a list literal'),
    ('def f(x: u32) -> None:\n    asm("nop", inputs=[x])\n', 'is not ("constraint", expression)'),
    ('def f(x: u32) -> None:\n    asm("nop", volatile=x)\n', 'volatile= takes True or False'),
    ('@struct\nclass S:\n    a: u32\ndef f() -> None:\n    s = S()\n    asm("nop", inputs=[("r", s)])\n', 'in a register'),
    ('def f(x: u32) -> None:\n    asm(x)\n', 'asm takes one string literal first'),
    ('def f() -> u32:\n    return asm("nop")\n', 'asm() used as a value'),
]


@NEEDS_TOOLS
class AsmOperands(Workdir):
    def test_instructions_run_with_the_declared_operands(self):
        self.module('asm_ops', ASM_SOURCE)
        out = self.link_and_run('asm_ops', ASM_HARNESS, 'asm_ops')
        self.assertEqual(out.strip(), 'OK')

    def test_privileged_instructions_are_encoded_with_their_operands(self):
        self.module('asm_ops2', ASM_SOURCE)
        outb = self.disassemble('asm_ops2', 'outb_port')
        self.assertRegex(outb, r'\bout\s+%al,\(%dx\)')
        self.assertRegex(self.disassemble('asm_ops2', 'inb_port'), r'\bin\s+\(%dx\),%al')
        self.assertRegex(self.disassemble('asm_ops2', 'outb_fixed'), r'\bout\s+%al,\$0x80')

    def test_volatile_flag_and_implied_memory_clobber(self):
        c, _, _ = freestanding.translate(HEAD + 'def f(x: u32) -> u32:\n    asm("bswap %0", outputs=[("+r", x)], volatile=False)\n'
                                         '    asm("bswap %0", outputs=[("+r", x)])\n    asm("bswap %0", outputs=[("+r", x)], volatile=False, clobbers=["cc", "memory"])\n'
                                         '    return x\n', 'v.py')
        self.assertIn('__asm__("bswap %0" : "+r"(x) :  : );', c)
        self.assertIn('__asm__ __volatile__("bswap %0" : "+r"(x) :  : "memory");', c)
        self.assertIn('__asm__("bswap %0" : "+r"(x) :  : "cc", "memory");', c)

    def test_plain_asm_is_unchanged(self):
        c, _, _ = freestanding.translate(HEAD + 'def f() -> None:\n    asm("cli")\n', 'p.py')
        self.assertIn('__asm__ __volatile__("cli" ::: "memory");', c)

    @unittest.skipUnless(sys.platform.startswith('linux') and os.uname().machine == 'x86_64', 'needs x86-64 Linux')
    def test_static_program_without_libc_writes_through_syscall(self):
        self.module('sys_hello', SYSCALL_SOURCE)
        (self.dir / 'start.S').write_text('.globl _start\n_start:\n andq $-16, %rsp\n call ail_main\n movl %eax, %edi\n'
                                          ' movl $60, %eax\n syscall\n.section .note.GNU-stack,"",@progbits\n')
        self.assertEqual(run([*CC.split(), '-c', self.dir / 'start.S', '-o', self.dir / 'start.o']).returncode, 0)
        link = run([*CC.split(), '-nostdlib', '-static', '-no-pie', self.dir / 'start.o', self.dir / 'sys_hello.o', '-o', self.dir / 'hello'])
        self.assertEqual(link.returncode, 0, link.stderr)
        ran = run([self.dir / 'hello'])
        self.assertEqual((ran.returncode, ran.stdout), (14, 'hello, kernel\n'))

    def test_refusals(self):
        for source, expected in ASM_REFUSALS:
            with self.subTest(source=source):
                with self.assertRaises(freestanding.Refusal) as caught:
                    freestanding.translate(with_head(source), 'm.py')
                self.assertIn(expected, caught.exception.text())

    def test_the_shim_refuses_to_run_asm_with_operands(self):
        with self.assertRaises(fs.HardwareAccess):
            fs.asm('bswap %0', outputs=[('+r', 1)])


# --------------------------------------------------------------------------------- function pointers

FN_SOURCE = HEAD + '''
@struct
class Handler:
    cb: Fn[[u32], u32]
    arg: u32

@struct
class Registry:
    slots: Array[Handler, 4]
    count: u32

def twice(x: u32) -> u32:
    return x + x

def square(x: u32) -> u32:
    return x * x

def negate(x: u32) -> u32:
    return 0 - x

def bump(x: u32) -> u32:
    return x + 1

table: Array[Fn[[u32], u32], 3] = Array[Fn[[u32], u32], 3]([twice, square, negate])
current: Fn[[u32], u32] = twice
nothing: Fn[[u32], u32] = Fn[[u32], u32](0)
registry: Registry = Registry()

def apply(f: Fn[[u32], u32], v: u32) -> u32:
    return f(v)

def pick(i: u32) -> Fn[[u32], u32]:
    return table[i]

def select(i: u32) -> None:
    global current
    current = table[i]

def add_handler(r: Ptr[Registry], f: Fn[[u32], u32], arg: u32) -> bool:
    if r.count >= 4:
        return False
    r.slots[r.count].cb = f
    r.slots[r.count].arg = arg
    r.count += 1
    return True

def run_all(r: Ptr[Registry]) -> u32:
    total: u32 = 0
    for i in range(r.count):
        total = total + r.slots[i].cb(r.slots[i].arg)
    return total

def compose(f: Fn[[u32], u32], g: Fn[[u32], u32], v: u32) -> u32:
    return f(g(v))

def is_null(f: Fn[[u32], u32]) -> bool:
    return f == Fn[[u32], u32](0)

def addr_is_zero(f: Fn[[u32], u32]) -> bool:
    return addr(f) == 0

def null_fn() -> Fn[[u32], u32]:
    return Fn[[u32], u32](0)

def same(f: Fn[[u32], u32], g: Fn[[u32], u32]) -> bool:
    return f == g

def address_of_twice() -> usize:
    return addr(twice)

def call_result(i: u32, v: u32) -> u32:
    return pick(i)(v)

def local_pointer(v: u32) -> u32:
    f = bump
    g: Fn[[u32], u32] = square
    return f(g(v))

def selftest(seed: u32) -> u32:
    r = Registry()
    p = addr_of(r)
    add_handler(p, twice, seed)
    add_handler(p, square, seed + 3)
    add_handler(p, bump, seed)
    add_handler(p, negate, seed + 1)
    total = run_all(p)
    if add_handler(p, twice, 1):
        total = total ^ 0xFFFF
    select(seed % 3)
    total = total ^ current(seed) ^ apply(pick((seed + 1) % 3), 5)
    total = total + compose(twice, square, seed) + call_result(seed % 3, seed) + local_pointer(seed)
    if is_null(nothing) and not is_null(current) and same(current, table[seed % 3]):
        total = total + 1000
    return total
'''

FN_HARNESS = '''
#include <stdint.h>
#include <stdio.h>
#include "fn_ptr.h"
static int failures;
''' + CHECK + '''
int main(void) {
    CHECK(twice(4) == 8 && square(5) == 25 && negate(1) == 0xFFFFFFFFu);
    CHECK(apply(square, 9) == 81 && apply(table[2], 2) == 0xFFFFFFFEu);
    CHECK(pick(0) == twice && pick(1) == square);
    CHECK(is_null(nothing) && is_null(null_fn()) && !is_null(twice));
    CHECK(addr_is_zero(nothing) && !addr_is_zero(square));
    CHECK(address_of_twice() == (uintptr_t)twice);
    CHECK(same(twice, twice) && !same(twice, square));
    CHECK(compose(twice, bump, 5) == 12 && call_result(1, 7) == 49 && local_pointer(4) == 17);
    select(2);
    CHECK(current == negate);
    for (uint32_t seed = 0; seed < 6; seed++)
        printf("fn %u %u\\n", seed, selftest(seed));
    CHECK(registry.count == 0);
    puts(failures ? "FAILED" : "OK");
    return failures != 0;
}
'''


def fn_formula(seed):
    m = 0xFFFFFFFF
    twice = lambda x: (x + x) & m
    square = lambda x: (x * x) & m
    negate = lambda x: (-x) & m
    bump = lambda x: (x + 1) & m
    table = [twice, square, negate]
    slots = [(twice, seed), (square, seed + 3), (bump, seed), (negate, seed + 1)]
    total = sum(f(a) for f, a in slots) & m
    current = table[seed % 3]
    total = total ^ current(seed) ^ table[(seed + 1) % 3](5)
    total = (total + twice(square(seed)) + table[seed % 3](seed) + bump(square(seed))) & m
    return (total + 1000) & m


FN_REFUSALS = [
    ('def inc(x: u32) -> u32:\n    return x + 1\ndef f() -> None:\n    g: Fn[[u8], u32] = inc\n',
     'a Fn[[u32], u32] value where a Fn[[u8], u32] is expected'),
    ('def inc(x: u32) -> u32:\n    return x + 1\ndef f() -> u32:\n    return inc\n', 'where a u32 is expected'),
    ('def f(g: Fn[[u32], u32]) -> u32:\n    return g(1, 2)\n', 'takes 1 arguments, not 2'),
    ('def f(g: Fn[[u32], u32]) -> u32:\n    return g(u8(1))\n', 'a u8 value where a u32 is expected'),
    ('def f(g: Fn[[u32], u32], h: Fn[[u32], u32]) -> bool:\n    return g < h\n', 'ordering Fn[[u32], u32] values'),
    ('def f(g: Fn[[u32], u32]) -> bool:\n    return g == 0\n', 'an integer literal where a Fn[[u32], u32] is expected'),
    ('def f(g: Fn[[u32], u32]) -> None:\n    if g:\n        pass\n', 'a Fn[[u32], u32] as a condition'),
    ('def f(x: u32) -> u32:\n    return x(1)\n', 'a call of x, a u32'),
    ('def f(g: Callable[[int], int]) -> None:\n    pass\n', 'the type Callable needs the runtime'),
    ('def f(g: Fn[u32, u32]) -> None:\n    pass\n', 'Fn needs a parameter list and a result'),
    ('@struct\nclass S:\n    a: u32\ndef f(g: Fn[[S], u32]) -> None:\n    pass\n', 'passes a S by value'),
    ('def f() -> None:\n    g = Fn[[u32], u32](u8(1))\n', 'Fn[...]() of a u8'),
    ('def f(x: u32) -> None:\n    lambda: 1\n', 'a lambda needs closures'),
]


@NEEDS_TOOLS
class FunctionPointers(Workdir):
    def test_c_build_shim_and_formula_agree(self):
        src = self.module('fn_ptr', FN_SOURCE)
        out = self.link_and_run('fn_ptr', FN_HARNESS, 'fn_ptr')
        native = {int(line.split()[1]): int(line.split()[2]) for line in out.splitlines() if line.startswith('fn ')}
        self.assertEqual(len(native), 6)
        mod = fs.load(src, 'fs_fn_ptr')
        for seed in range(6):
            self.assertEqual(native[seed], fn_formula(seed), seed)
            self.assertEqual(mod.selftest(fs.u32(seed)), native[seed], seed)

    def test_shim_null_pointer_and_checks(self):
        src = self.module('fn_ptr2', FN_SOURCE)
        mod = fs.load(src, 'fs_fn_ptr2')
        null = mod.null_fn()
        self.assertTrue(mod.is_null(null))
        with self.assertRaises(fs.Trap):
            null(fs.u32(1))
        with self.assertRaises(fs.HardwareAccess):
            mod.address_of_twice()
        with self.assertRaises(TypeError):
            mod.apply(lambda a, b: a, fs.u32(1))          # two parameters where Fn[[u32], u32] is expected
        with self.assertRaises(TypeError):
            mod.apply(5, fs.u32(1))
        self.assertEqual(mod.apply(mod.square, fs.u32(0x10000)), 0)       # the callee's own wrapping
        self.assertTrue(mod.same(mod.twice, mod.twice))
        self.assertFalse(mod.same(mod.twice, mod.square))

    def test_c_text(self):
        c, h, _ = freestanding.translate(FN_SOURCE, 'fn_ptr.py')
        self.assertIn('uint32_t (*cb)(uint32_t);', c)
        self.assertIn('uint32_t (*table[3])(uint32_t) = {twice, square, negate};', c)
        self.assertIn('uint32_t (*nothing)(uint32_t) = ((uint32_t (*)(uint32_t))(uintptr_t)0ull);', c)
        self.assertIn('extern uint32_t (*current)(uint32_t);', h)
        self.assertIn('uint32_t (*pick(uint32_t i))(uint32_t);', h)

    def test_refusals(self):
        for source, expected in FN_REFUSALS:
            with self.subTest(source=source):
                with self.assertRaises(freestanding.Refusal) as caught:
                    freestanding.translate(with_head(source), 'm.py')
                self.assertIn(expected, caught.exception.text())


# ------------------------------------------------------------------------------------- @interrupt

INTR_SOURCE = HEAD + '''
@struct
class Frame:
    ip: usize
    cs: usize
    flags: usize
    sp: usize
    ss: usize

seen: u32 = 0
last_ip: usize = 0
last_cs: usize = 0
last_sp: usize = 0
last_err: usize = 0

def note(frame: Ptr[Frame], err: usize) -> None:
    global seen, last_ip, last_cs, last_sp, last_err
    seen += 1
    last_ip = frame.ip
    last_cs = frame.cs
    last_sp = frame.sp
    last_err = err

@interrupt
def h_timer(frame: Ptr[Frame]) -> None:
    note(frame, 0)

@interrupt
def h_gp(frame: Ptr[Frame], error: usize) -> None:
    note(frame, error)

def handler_address(which: u32) -> usize:
    if which == 0:
        return addr(h_timer)
    return addr(h_gp)
'''

INTR_HARNESS = '''
#include <stdint.h>
#include <stdio.h>
#include "intr.h"
static int failures;
''' + CHECK + '''
/* Reproduce what the CPU does on an interrupt in the same ring: push ss, rsp, rflags, cs, rip (and an
   error code on top), then enter the handler. Its iretq pops the frame and resumes at label 1. */
static uint64_t fire(void *handler, uint64_t err, int has_err) {
    uint64_t cs, ss, rip;
    __asm__ volatile("movq %%cs, %0" : "=r"(cs));
    __asm__ volatile("movq %%ss, %0" : "=r"(ss));
    __asm__ volatile(
        "movq %%rsp, %%rcx\\n\\t"
        "leaq 1f(%%rip), %[rip]\\n\\t"
        "pushq %[ss]\\n\\tpushq %%rcx\\n\\tpushfq\\n\\tpushq %[cs]\\n\\tpushq %[rip]\\n\\t"
        "testl %[has], %[has]\\n\\tjz 2f\\n\\tpushq %[err]\\n"
        "2:\\tjmp *%[h]\\n"
        "1:\\n"
        : [rip] "=&r"(rip)
        : [ss] "r"(ss), [cs] "r"(cs), [h] "r"(handler), [has] "r"(has_err), [err] "r"(err)
        : "rcx", "memory", "cc");
    return rip;
}
int main(void) {
    CHECK(handler_address(0) == (uintptr_t)h_timer && handler_address(1) == (uintptr_t)h_gp);
    uint64_t cs;
    __asm__ volatile("movq %%cs, %0" : "=r"(cs));
    uint64_t rsp0;
    __asm__ volatile("movq %%rsp, %0" : "=r"(rsp0));
    uint64_t rip = fire((void *)h_timer, 0, 0);
    CHECK(seen == 1 && last_ip == rip && last_cs == cs && last_err == 0);
    CHECK(last_sp != 0 && (last_sp & 7) == 0);
    rip = fire((void *)h_gp, 0xDEAD, 1);                          /* an exception with an error code */
    CHECK(seen == 2 && last_ip == rip && last_err == 0xDEAD);
    rip = fire((void *)h_gp, 0xBEEF, 1);
    rip = fire((void *)h_timer, 0, 0);
    CHECK(seen == 4 && last_ip == rip && last_err == 0);
    puts(failures ? "FAILED" : "OK");
    return failures != 0;
}
'''

INTR_REFUSALS = [
    ('@struct\nclass F:\n    a: usize\n@interrupt\ndef h() -> None:\n    pass\n', '@interrupt h must be def h(frame: Ptr[Frame]) -> None'),
    ('@struct\nclass F:\n    a: usize\n@interrupt\ndef h(frame: Ptr[F], e: u32) -> None:\n    pass\n', '@interrupt h must be'),
    ('@struct\nclass F:\n    a: usize\n@interrupt\ndef h(frame: Ptr[F]) -> u32:\n    return 1\n', '@interrupt h must be'),
    ('@interrupt\ndef h(frame: Ptr[u32]) -> None:\n    pass\n', '@interrupt h must be'),
    ('@struct\nclass F:\n    a: usize\n@interrupt\ndef h(frame: Ptr[F]) -> None:\n    pass\ndef f(p: Ptr[F]) -> None:\n    h(p)\n',
     '@interrupt handler h cannot be called'),
    ('@struct\nclass F:\n    a: usize\n@interrupt\ndef h(frame: Ptr[F]) -> None:\n    pass\ndef f() -> None:\n    g: Fn[[Ptr[F]], None] = h\n',
     'is entered by the CPU and returns with iret'),
    ('@struct\nclass F:\n    a: usize\n    @interrupt\n    def m(self) -> None:\n        pass\n', 'the decorator interrupt'),
    ('@struct\nclass F:\n    a: usize\n@extern\n@interrupt\ndef h(frame: Ptr[F]) -> None:\n    pass\n', '@interrupt h must be'),
]


@NEEDS_TOOLS
class Interrupts(Workdir):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        src = cls.dir / 'intr.py'
        src.write_text(INTR_SOURCE)
        cls.result = compile_fs(src, cls.dir / 'intr.o')

    def test_object_and_flags(self):
        self.assertEqual(self.result.returncode, 0, self.result.stderr)
        self.assertIn('"interrupts": true', self.result.stdout)
        timer = self.disassemble('intr', 'h_timer')
        self.assertIn('iretq', timer)
        self.assertNotIn(' ret', timer.replace('iretq', ''))
        gp = self.disassemble('intr', 'h_gp')
        self.assertIn('iretq', gp)
        self.assertRegex(gp, r'add\s+\$0x8,%rsp')                     # the error code is popped before iretq
        self.assertNotRegex(timer, r'add\s+\$0x8,%rsp')
        self.assertNotIn('xmm', self.disassemble('intr', 'note'))
        header = (self.dir / 'intr.h').read_text()
        self.assertIn('__attribute__((interrupt)) void h_timer(Frame *frame);', header)
        self.assertIn('__attribute__((interrupt)) void h_gp(Frame *frame, uintptr_t error);', header)

    @unittest.skipUnless(sys.platform.startswith('linux') and os.uname().machine == 'x86_64', 'needs x86-64 Linux')
    def test_handlers_run_with_a_reproduced_cpu_frame(self):
        self.assertEqual(self.result.returncode, 0, self.result.stderr)
        out = self.link_and_run('intr', INTR_HARNESS, 'intr')
        self.assertEqual(out.strip(), 'OK')

    def test_the_logic_runs_on_cpython_with_a_fake_frame(self):
        mod = fs.load(self.dir / 'intr.py', 'fs_intr')
        frame = mod.Frame(ip=0x1234, cs=8)
        mod.h_gp(fs.addr_of(frame), fs.usize(77))
        self.assertEqual((mod.seen, mod.last_ip, mod.last_cs, mod.last_err), (1, 0x1234, 8, 77))
        with self.assertRaises(fs.HardwareAccess):
            mod.handler_address(fs.u32(0))

    def test_refusals(self):
        for source, expected in INTR_REFUSALS:
            with self.subTest(source=source):
                with self.assertRaises(freestanding.Refusal) as caught:
                    freestanding.translate(with_head(source), 'm.py')
                self.assertIn(expected, caught.exception.text())


# ------------------------------------------------------------------------------ @packed and @align

LAYOUT_SOURCE = HEAD + '''
@packed
@struct
class P1:
    a: u8
    b: u32
    c: u16

@struct
class N1:
    a: u8
    b: u32
    c: u16

@align(16)
@struct
class A16:
    a: u8

@packed
@struct
class PP:
    x: P1
    y: u8
    z: u64

@struct
class Mix:
    p: P1
    q: u64
    flag: bool
    cb: Fn[[u32], None]
    tail: Array[u16, 3]
    link: Ptr["Mix"]

@align(64)
@packed
@struct
class Both:
    a: u8
    b: u64

@struct
class Holder:
    tag: u8
    inner: P1
    big: A16

@struct
class Wide:
    a: u8
    b: u64
    c: i64
    d: u8

def sizes(i: u32) -> usize:
    match i:
        case 0:
            return size_of(P1)
        case 1:
            return size_of(N1)
        case 2:
            return size_of(A16)
        case 3:
            return size_of(PP)
        case 4:
            return size_of(Mix)
        case 5:
            return size_of(Both)
        case 6:
            return size_of(Holder)
        case 7:
            return size_of(Wide)
        case 8:
            return size_of(Array[N1, 5])
        case _:
            return 0

def aligns(i: u32) -> usize:
    match i:
        case 0:
            return align_of(P1)
        case 1:
            return align_of(N1)
        case 2:
            return align_of(A16)
        case 3:
            return align_of(PP)
        case 4:
            return align_of(Mix)
        case 5:
            return align_of(Both)
        case 6:
            return align_of(Holder)
        case 7:
            return align_of(Wide)
        case 8:
            return align_of(Array[N1, 5])
        case _:
            return 0

def poke(p: Ptr[P1]) -> u32:
    p.b = 0x01020304
    p.c = 0x0506
    p.a = 7
    return p.b + u32(p.c) + u32(p.a)

a16: A16 = A16()
'''

LAYOUT_HARNESS = '''
#include <stdint.h>
#include <stddef.h>
#include <stdio.h>
#include <string.h>
#include "layouts.h"
static int failures;
''' + CHECK + '''
int main(void) {
    for (uint32_t i = 0; i < 9; i++)
        printf("size %u %zu %zu\\n", i, (size_t)sizes(i), (size_t)aligns(i));
    CHECK(sizeof(P1) == 7 && offsetof(P1, b) == 1 && offsetof(P1, c) == 5);
    CHECK(sizeof(N1) == 12 && sizeof(A16) == 16 && ((uintptr_t)&a16 & 15) == 0);
    P1 p;
    memset(&p, 0, sizeof p);
    CHECK(poke(&p) == 0x01020304u + 0x0506u + 7u);
    static const uint8_t want[7] = {7, 4, 3, 2, 1, 6, 5};          /* little endian, no padding */
    CHECK(memcmp(&p, want, 7) == 0);
    puts(failures ? "FAILED" : "OK");
    return failures != 0;
}
'''

LAYOUT_REFUSALS = [
    ('@align(3)\n@struct\nclass S:\n    a: u8\n', '@align takes a power of two'),
    ('@align(0)\n@struct\nclass S:\n    a: u8\n', '@align takes a power of two'),
    ('@align(8192)\n@struct\nclass S:\n    a: u8\n', '@align takes a power of two'),
    ('@align(u32)\n@struct\nclass S:\n    a: u8\n', '@align takes a power of two'),
    ('@packed\nclass S:\n    a: u8\n', 'is not a @struct'),
    ('@struct\n@wrapping\nclass S:\n    a: u8\n', 'the class decorator wrapping'),
    ('from ail_freestanding import u8, struct\n@packed\n@struct\nclass S:\n    a: u8\n', 'packed is not imported'),
    ('def f() -> usize:\n    return size_of(Missing)\n', 'unknown type Missing'),
    ('def f() -> usize:\n    return size_of(u32, u32)\n', 'size_of() takes one type'),
]


@NEEDS_TOOLS
class PackedAndAlign(Workdir):
    def test_checker_c_compiler_and_shim_agree_on_every_layout(self):
        src = self.module('layouts', LAYOUT_SOURCE)                       # _Static_assert inside checks the C compiler
        out = self.link_and_run('layouts', LAYOUT_HARNESS, 'layouts')
        native = {int(l.split()[1]): (int(l.split()[2]), int(l.split()[3])) for l in out.splitlines() if l.startswith('size ')}
        mod = fs.load(src, 'fs_layouts')
        types = [mod.P1, mod.N1, mod.A16, mod.PP, mod.Mix, mod.Both, mod.Holder, mod.Wide, fs.Array[mod.N1, 5]]
        for i, t in enumerate(types):
            self.assertEqual(native[i], (fs.size_of(t), fs.align_of(t)), t)
            self.assertEqual(mod.sizes(fs.u32(i)), native[i][0])
            self.assertEqual(mod.aligns(fs.u32(i)), native[i][1])
        self.assertEqual([native[i][0] for i in range(9)], [7, 12, 16, 16, 48, 64, 32, 32, 60])
        p = mod.P1()
        self.assertEqual(mod.poke(fs.addr_of(p)), 0x01020304 + 0x0506 + 7)

    def test_the_static_asserts_are_in_the_generated_c(self):
        c, h, _ = freestanding.translate(LAYOUT_SOURCE, 'layouts.py')
        self.assertIn('struct __attribute__((packed)) P1 {', c)
        self.assertIn('struct __attribute__((aligned(16))) A16 {', c)
        self.assertIn('struct __attribute__((packed, aligned(64))) Both {', c)
        self.assertIn('_Static_assert(sizeof(P1) == 7 && _Alignof(P1) == 1, "AIL layout of P1");', c)
        self.assertIn('_Static_assert(sizeof(Both) == 64 && _Alignof(Both) == 64, "AIL layout of Both");', c)
        self.assertIn('struct __attribute__((packed)) P1 {', h)

    def test_a_wrong_layout_model_would_fail_the_c_compiler(self):
        class Lying(freestanding.Module):
            def layout(self, t):
                size, align = super().layout(t)
                return (size + 1, align) if isinstance(t, freestanding.StructT) and t.name == 'N1' else (size, align)
        m = Lying(LAYOUT_SOURCE, 'layouts.py')
        m.check()
        src = self.dir / 'lying.c'
        src.write_text(m.emit('layouts.py'))
        result = run([*CC.split(), '-std=c11', '-ffreestanding', '-c', src, '-o', self.dir / 'lying.o'])
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('AIL layout of N1', result.stderr)

    def test_refusals(self):
        for source, expected in LAYOUT_REFUSALS:
            with self.subTest(source=source):
                with self.assertRaises(freestanding.Refusal) as caught:
                    freestanding.translate(with_head(source), 'm.py')
                self.assertIn(expected, caught.exception.text())

    def test_address_of_a_packed_member_is_an_error(self):
        source = HEAD + '@packed\n@struct\nclass P:\n    a: u8\n    w: Array[u32, 2]\ndef f(p: Ptr[P]) -> u32:\n    q = as_ptr(p.w)\n    return q[0]\n'
        src = self.dir / 'packedaddr.py'
        src.write_text(source)
        result = compile_fs(src, self.dir / 'packedaddr.o')
        self.assertEqual(result.returncode, 2, result.stdout + result.stderr)
        self.assertIn('address-of-packed-member', result.stderr)


# ------------------------------------------------------------------------------------------ --m32

M32_SOURCE = HEAD + '''
@struct
class Rec:
    tag: u8
    big: u64
    ptr: Ptr[u8]
    count: usize

table: Array[u32, 4] = Array[u32, 4]([10, 20, 30, 40])

def facts() -> u32:
    return u32(size_of(usize)) * 1000 + u32(size_of(Ptr[u8])) * 100 + u32(size_of(Rec)) * 1 + u32(align_of(Rec)) * 10000

def wrap_usize(x: usize) -> usize:
    return x + 1

def sum_table(p: Ptr[u32], n: usize) -> u32:
    total: u32 = 0
    for i in range(n):
        total = total + p[i]
    return total

def big_shift(x: u64, n: u32) -> u64:
    return (x << n) | (x >> 3)

def addr_bits(p: Ptr[u8]) -> usize:
    return addr(p)

def ail_main() -> u32:
    return facts() + sum_table(as_ptr(table), usize(4)) + u32(wrap_usize(usize(0xFFFFFFFF))) + u32(big_shift(u64(1), 33) >> 33)
'''

M32_START = '''        .text
        .global _start
_start:
        call ail_main
        movl %eax, %ebx
        movl $1, %eax
        int $0x80
        .section .note.GNU-stack,"",@progbits
'''


@NEEDS_TOOLS
class Target32(Workdir):
    def can_run_i386(self):
        if not (shutil.which('ld') and sys.platform.startswith('linux')):
            return False
        src = self.dir / 'probe32.S'
        src.write_text(M32_START.replace('call ail_main', 'movl $0, %eax'))
        if run([*CC.split(), '-m32', '-c', src, '-o', self.dir / 'probe32.o']).returncode:
            return False
        if run(['ld', '-m', 'elf_i386', '-o', self.dir / 'probe32', self.dir / 'probe32.o']).returncode:
            return False
        return run([self.dir / 'probe32']).returncode == 0

    def test_examples_build_for_i386(self):
        for name in ('ring', 'pagealloc', 'crc32', 'vga', 'kernel_main'):
            with self.subTest(name):
                result = compile_fs(EXAMPLES / (name + '.py'), self.dir / (name + '32.o'), '--m32')
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertIn('"target": "i386"', result.stdout)
                self.assertIn('ELF 32-bit', run(['file', self.dir / (name + '32.o')]).stdout if shutil.which('file') else 'ELF 32-bit')

    def test_usize_is_32_bits_and_a_static_i386_program_runs(self):
        if not self.can_run_i386():
            self.skipTest('cannot link or run 32-bit static programs here')
        self.module('m32prog', M32_SOURCE, '--m32')
        (self.dir / 'start32.S').write_text(M32_START)
        self.assertEqual(run([*CC.split(), '-m32', '-c', self.dir / 'start32.S', '-o', self.dir / 'start32.o']).returncode, 0)
        link = run(['ld', '-m', 'elf_i386', '-o', self.dir / 'm32prog', self.dir / 'start32.o', self.dir / 'm32prog.o'])
        self.assertEqual(link.returncode, 0, link.stderr)
        # Rec: tag(1) pad(3) big(8, align 4 on i386) ptr(4) count(4) = 20 bytes, align 4
        expected = (4 * 1000 + 4 * 100 + 20 + 4 * 10000) + (10 + 20 + 30 + 40) + 0 + 1
        self.assertEqual(run([self.dir / 'm32prog']).returncode, expected & 0xFF)

    def test_the_same_source_has_a_64_bit_size_on_x86_64(self):
        c64, _, _ = freestanding.translate(M32_SOURCE, 'm.py')
        c32, _, _ = freestanding.translate(M32_SOURCE, 'm.py', target='i386')
        self.assertIn('_Static_assert(sizeof(Rec) == 32 && _Alignof(Rec) == 8, "AIL layout of Rec");', c64)
        self.assertIn('_Static_assert(sizeof(Rec) == 20 && _Alignof(Rec) == 4, "AIL layout of Rec");', c32)

    def test_64_bit_division_names_libgcc(self):
        src = self.dir / 'div64.py'
        src.write_text(HEAD + 'def f(a: u64, b: u64) -> u64:\n    return a // b\n')
        result = compile_fs(src, self.dir / 'div64.o', '--m32')
        self.assertEqual(result.returncode, 2, result.stdout + result.stderr)
        self.assertIn('undeclared symbols __udivdi3', result.stderr)
        self.assertIn('64-bit // and % on a 32-bit target call libgcc', result.stderr)
        ok = compile_fs(src, self.dir / 'div64x.o')                       # fine on x86-64
        self.assertEqual(ok.returncode, 0, ok.stderr)

    def test_addresses_must_fit_the_pointer(self):
        with self.assertRaises(freestanding.Refusal) as caught:
            freestanding.translate(HEAD + 'p: Ptr[u8] = Ptr[u8](0x100000000)\n', 'm.py', target='i386')
        self.assertIn('does not fit a 32-bit pointer', caught.exception.text())
        freestanding.translate(HEAD + 'p: Ptr[u8] = Ptr[u8](0x100000000)\n', 'm.py')

    def test_flag_needs_freestanding(self):
        result = run([sys.executable, '-B', CLI, 'compile', '--m32', str(EXAMPLES / 'ring.py'), '-o', self.dir / 'x'])
        self.assertEqual(result.returncode, 2)
        self.assertIn('--m32 is part of --freestanding', result.stderr)


# ------------------------------------------------------------------------------------- toy kernel

LIBC_NAMES = {'printf', 'puts', 'putchar', 'malloc', 'free', 'calloc', 'realloc', 'abort', 'exit', '_exit', '__libc_start_main',
              '__stack_chk_fail', 'strlen', 'snprintf', 'sprintf', '__cxa_atexit', 'write', 'read', 'open', 'main'}


def load_kernel_build():
    import importlib.util
    spec = importlib.util.spec_from_file_location('ail_kernel_build', KERNEL / 'build.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def read_u32(data, offset):
    return struct.unpack_from('<I', data, offset)[0]


@NEEDS_TOOLS
@unittest.skipUnless(shutil.which('readelf') and shutil.which('objcopy') and shutil.which('ld'), 'needs readelf, objcopy and ld')
class ToyKernel(Workdir):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.kbuild = load_kernel_build()
        cls.built = cls.kbuild.build(cls.dir / 'kernel')
        cls.kdir = cls.dir / 'kernel'

    def symbols(self, path):
        out = run(['nm', path]).stdout
        return {l.split()[-1] for l in out.splitlines() if len(l.split()) >= 2}

    def test_elf_entry_and_no_libc(self):
        elf = self.built['elf']
        header = run(['readelf', '-h', elf]).stdout
        self.assertIn('ELF64', header)
        self.assertIn('Advanced Micro Devices X86-64', header)
        entry = int(re.search(r'Entry point address:\s+(0x[0-9a-f]+)', header).group(1), 16)
        syms = self.symbols(elf)
        out = run(['nm', '-n', elf]).stdout
        starts = {l.split()[-1]: int(l.split()[0], 16) for l in out.splitlines() if len(l.split()) == 3}
        self.assertEqual(entry, starts['_start'])
        self.assertEqual(entry, 0x100030)
        for name in ('kernel_main', 'kernel_end_addr', 'idt_install', 'idt_build', 'isr_timer', 'isr_breakpoint', 'pa_global_alloc',
                     'console_putc', 'mb_upper_kib', 'usable_pages'):
            self.assertIn(name, syms)
        self.assertEqual(run(['nm', '-u', elf]).stdout.strip(), '')
        self.assertEqual(LIBC_NAMES & syms, set())
        program = run(['readelf', '-lW', elf]).stdout
        self.assertNotIn('INTERP', program)
        self.assertNotIn('DYNAMIC', program)
        self.assertNotIn('NEEDED', run(['readelf', '-d', elf]).stdout)
        loads = [l for l in program.splitlines() if l.strip().startswith('LOAD')]
        self.assertEqual(len(loads), 2)
        self.assertNotIn('RWE', program)
        self.assertEqual(starts['_start'] >> 20, 1)                      # loaded at 1 MiB
        self.assertTrue(starts['_kernel_end'] % 4096 == 0 and starts['_kernel_end'] > starts['kernel_main'])

    def find_headers(self, path):
        data = Path(path).read_bytes()
        # the loader takes the first hit; the symbol table (absolute symbols with the same values) comes later
        mb1 = [o for o in range(0, min(len(data), 8192) - 11, 4) if read_u32(data, o) == 0x1BADB002][:1]
        mb2 = [o for o in range(0, min(len(data), 32768) - 15, 8) if read_u32(data, o) == 0xE85250D6][:1]
        return data, mb1, mb2

    def check_multiboot(self, path):
        data, mb1, mb2 = self.find_headers(path)
        self.assertEqual(len(mb1), 1, 'one multiboot1 header in the first 8 KiB')
        o = mb1[0]
        magic, flags, checksum = struct.unpack_from('<III', data, o)
        self.assertEqual((magic + flags + checksum) & 0xFFFFFFFF, 0)
        self.assertEqual(flags & 0x10000, 0, 'address fields unused: the loader reads the ELF headers')
        self.assertEqual(len(mb2), 1, 'one multiboot2 header in the first 32 KiB')
        o = mb2[0]
        magic, arch, length, checksum = struct.unpack_from('<IIII', data, o)
        self.assertEqual((magic + arch + length + checksum) & 0xFFFFFFFF, 0)
        self.assertEqual(arch, 0)
        self.assertEqual(struct.unpack_from('<HHI', data, o + length - 8), (0, 0, 8))      # the end tag closes it
        return mb1[0], mb2[0]

    def test_multiboot_headers_in_both_images(self):
        self.assertEqual(self.check_multiboot(self.built['elf']), (0x1000, 0x1010))
        self.check_multiboot(self.built['elf32'])

    def test_elf32_image_for_qemu_kernel(self):
        header = run(['readelf', '-h', self.built['elf32']]).stdout
        self.assertIn('ELF32', header)
        self.assertIn('Entry point address:               0x100030', header)
        self.assertEqual(run(['nm', '-u', self.built['elf32']]).stdout.strip(), '')

    def test_interrupt_handlers_return_with_iretq(self):
        for name in ('isr_timer', 'isr_breakpoint', 'isr_spurious'):
            text = run(['objdump', '-d', '--no-show-raw-insn', '--disassemble=' + name, self.built['elf']]).stdout
            self.assertIn('iretq', text, name)
        gp = run(['objdump', '-d', '--no-show-raw-insn', '--disassemble=isr_general_protection', self.built['elf']]).stdout
        self.assertNotIn('xmm', gp)
        boot = run(['objdump', '-d', '-M', 'i386', '--no-show-raw-insn', '--disassemble=_start', self.built['elf']]).stdout
        for needle in ('lgdt', 'wrmsr', 'ljmp', 'rep stos', 'cpuid', 'mov    %eax,%cr3', 'mov    %eax,%cr0'):
            self.assertIn(needle, boot)
        idt = run(['objdump', '-d', '--no-show-raw-insn', '--disassemble=idt_load', self.built['elf']]).stdout
        self.assertRegex(idt, r'lidt\s+')
        self.assertNotIn('xmm', run(['objdump', '-d', self.built['elf']]).stdout)       # general registers only

    def test_modules_have_only_their_declared_undefined_symbols(self):
        expect = {'console': [], 'idt': ['console_put_dec', 'console_put_hex', 'console_write', 'outb'], 'pagealloc': [],
                  'kmain': ['console_init', 'console_put_dec', 'console_put_hex', 'console_write', 'idt_install', 'idt_ticks',
                            'kernel_end_addr', 'outb', 'pa_global_alloc', 'pa_global_free', 'pa_global_init']}
        for name, undefined in expect.items():
            out = run(['nm', '-u', self.kdir / (name + '.o')]).stdout
            self.assertEqual(sorted(l.split()[-1] for l in out.splitlines() if l.strip()), undefined, name)

    def test_pure_parts_in_the_hosted_harness(self):
        exe = self.dir / 'harness_kernel'
        build = run([*CC.split(), '-std=c11', '-O2', '-Wall', '-no-pie', '-I', self.kdir, KERNEL / 'harness_kernel.c',
                     *[self.kdir / (n + '.o') for n in ('console', 'idt', 'pagealloc', 'kmain')], '-o', exe])
        self.assertEqual(build.returncode, 0, build.stderr)
        out = run([exe])
        self.assertEqual(out.returncode, 0, out.stdout + out.stderr)
        self.assertEqual(out.stdout.splitlines()[-1], 'OK', out.stdout)
        self.assertNotIn('FAIL', out.stdout)

    def test_console_and_idt_match_the_cpython_shim(self):
        exe = self.dir / 'harness_kernel2'
        build = run([*CC.split(), '-std=c11', '-O2', '-no-pie', '-I', self.kdir, KERNEL / 'harness_kernel.c',
                     *[self.kdir / (n + '.o') for n in ('console', 'idt', 'pagealloc', 'kmain')], '-o', exe])
        self.assertEqual(build.returncode, 0, build.stderr)
        line = [l for l in run([exe]).stdout.splitlines() if l.startswith('console_scenario')][0].split()
        native = tuple(int(x) for x in line[1:])

        con = fs.load(KERNEL / 'console.py', 'fs_console')
        log = []
        screen = fs.Array[fs.u16, 2000]()
        con.con_out = lambda port, value: log.append((int(port), int(value)))
        con.con_in = lambda port: fs.u8(0x20)
        con.con_screen = fs.as_ptr(screen)

        def text(s):
            buf = fs.Array[fs.u8, max(1, len(s))](list(s.encode()))
            con.console_write(fs.as_ptr(buf), fs.u32(len(s)))

        con.console_init()
        text('Hello, kernel\n')
        con.console_put_hex(fs.u64(0xCAFE))
        con.console_putc(fs.u8(10))
        con.console_put_dec(fs.u64(4096))
        con.console_putc(fs.u8(10))
        for line_no in range(30):
            text('line %02d\n' % line_no)

        def fnv(h, v):
            return ((h ^ v) * 16777619) & 0xFFFFFFFF
        hs = 2166136261
        for i in range(2000):
            hs = fnv(hs, int(screen[i]))
        ht = 2166136261
        for port, value in log:
            ht = fnv(ht, (port << 8) | value)
        self.assertEqual((hs, ht, int(con.con_row), int(con.con_col)), native)

        # the gate encoding: the shim and the 16 bytes the C build stores
        idt = fs.load(KERNEL / 'idt.py', 'fs_idt')
        self.assertTrue(idt.idt_layout_ok())
        idt.idt_set_gate(fs.u8(14), fs.usize(0xFFFF800012345678), fs.u8(1))
        e = idt.idt_table[14]
        packed = struct.pack('<HHBBHII', int(e.offset_low), int(e.selector), int(e.ist), int(e.type_attr),
                             int(e.offset_mid), int(e.offset_high), int(e.reserved))
        self.assertEqual(packed, bytes([0x78, 0x56, 0x08, 0x00, 0x01, 0x8E, 0x34, 0x12, 0x00, 0x80, 0xFF, 0xFF, 0, 0, 0, 0]))
        self.assertEqual(idt.idt_gate_address(fs.addr_of(e)), 0xFFFF800012345678)
        self.assertEqual(len(packed), fs.size_of(idt.IdtEntry))
        self.assertEqual(fs.size_of(idt.IdtPointer), 10)

    def test_sources_are_in_the_subset_and_have_the_documented_externs(self):
        for name, externs in (('console', []), ('idt', ['console_put_dec', 'console_put_hex', 'console_write', 'outb']),
                              ('kmain', ['console_init', 'console_put_dec', 'console_put_hex', 'console_write', 'idt_install',
                                         'idt_ticks', 'kernel_end_addr', 'outb', 'pa_global_alloc', 'pa_global_free', 'pa_global_init'])):
            _, _, found = freestanding.translate((KERNEL / (name + '.py')).read_text(), name + '.py')
            self.assertEqual(found, externs, name)

    def test_the_documented_qemu_command(self):
        kbuild = self.kbuild
        self.assertEqual(kbuild.QEMU.format(kernel='kernel32.elf'),
                         'qemu-system-x86_64 -kernel kernel32.elf -serial stdio -display none -no-reboot '
                         '-device isa-debug-exit,iobase=0xf4,iosize=0x04')
        design = (ROOT.parent / 'docs/design/FREESTANDING.md').read_text()
        self.assertIn(kbuild.QEMU.format(kernel='/tmp/ail-kernel/kernel32.elf'), design)


# ---------------------------------------------------------------------------- shim and misc

class ShimAdditions(unittest.TestCase):
    def test_fn_types_and_size_of(self):
        t = fs.Fn[[fs.u32], fs.u32]
        self.assertIs(t, fs.Fn[[fs.u32], fs.u32])
        self.assertIsNot(t, fs.Fn[[fs.u8], fs.u32])
        self.assertEqual(fs.size_of(t), 8)
        self.assertEqual(fs.size_of(fs.Array[fs.u16, 5]), 10)
        self.assertEqual(fs.size_of(fs.Ptr[fs.u8]), 8)
        self.assertEqual(fs.align_of(fs.u64), 8)

        @fs.packed
        @fs.struct
        class S:
            a: fs.u8
            b: fs.u32

        @fs.align(32)
        @fs.struct
        class T:
            a: fs.u8
        self.assertEqual((fs.size_of(S), fs.align_of(S)), (5, 1))
        self.assertEqual((fs.size_of(T), fs.align_of(T)), (32, 32))
        null = t(0)
        self.assertEqual(fs.addr(null), 0)
        with self.assertRaises(fs.Trap):
            null(fs.u32(1))
        with self.assertRaises(fs.HardwareAccess):
            t(0x1000)(fs.u32(1))
        self.assertEqual(fs.addr(t(0x1000)), 0x1000)
        with self.assertRaises(fs.HardwareAccess):
            fs.addr(lambda x: x)

    def test_interrupt_decorator_is_identity(self):
        @fs.interrupt
        def handler(frame):
            return 5
        self.assertEqual(handler(None), 5)


if __name__ == '__main__':
    unittest.main()

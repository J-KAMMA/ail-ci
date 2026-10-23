"""Toy kernel interrupts: the x86-64 IDT, the PIC and PIT setup, and AIL interrupt handlers.

Handlers are `@interrupt` functions: GCC's __attribute__((interrupt)) makes them save what they use and
return with iretq (see docs/design/FREESTANDING.md, "Interrupt handlers"). Each is a thin wrapper over an
ordinary function (exception_log, timer_tick) that the hosted harness can call. The gate table is plain
packed structs, so its layout (16 bytes per gate, a 10-byte lidt operand) is checked by size_of here and
by _Static_assert in the generated C.

Needs from the kernel: outb and the console_* functions (console.py).
"""
from ail_freestanding import (u8, u16, u32, u64, usize, Array, Ptr, struct, packed, interrupt, extern, arithmetic, addr,
                              addr_of, as_ptr, asm, size_of)

arithmetic("wrapping")

KERNEL_CS = 0x08
GATE_INTERRUPT = 0x8E           # present, ring 0, 64-bit interrupt gate (interrupts off while it runs)
VEC_BREAKPOINT = 3
VEC_TIMER = 32                  # IRQ0 after the PIC is remapped to 32..47
PIT_HZ = 100


@packed
@struct
class IdtEntry:
    offset_low: u16
    selector: u16
    ist: u8
    type_attr: u8
    offset_mid: u16
    offset_high: u32
    reserved: u32


@packed
@struct
class IdtPointer:
    limit: u16
    base: u64


@struct
class InterruptFrame:
    """What the CPU pushed (long mode): the return address, code segment, flags, stack pointer and segment."""
    ip: usize
    cs: usize
    flags: usize
    sp: usize
    ss: usize


@extern
def outb(port: u16, value: u8) -> None:
    """Defined by console.py (or the test harness)."""


@extern
def console_write(text: Ptr[u8], n: u32) -> None:
    """Defined by console.py (or the test harness)."""


@extern
def console_put_hex(v: u64) -> None:
    """Defined by console.py (or the test harness)."""


@extern
def console_put_dec(v: u64) -> None:
    """Defined by console.py (or the test harness)."""


idt_table: Array[IdtEntry, 256] = Array[IdtEntry, 256]()
idt_pointer: IdtPointer = IdtPointer()
idt_tick_count: u64 = 0
idt_exceptions: u32 = 0
idt_last_vector: u8 = 0
idt_last_ip: usize = 0
idt_last_error: usize = 0

_msg_exception: Array[u8, 11] = Array[u8, 11](b"exception #")
_msg_at: Array[u8, 4] = Array[u8, 4](b" at ")
_msg_error: Array[u8, 8] = Array[u8, 8](b" error: ")
_msg_nl: Array[u8, 1] = Array[u8, 1](b"\n")
_msg_halt: Array[u8, 8] = Array[u8, 8](b"halted.\n")


def idt_layout_ok() -> bool:
    return size_of(IdtEntry) == 16 and size_of(IdtPointer) == 10 and size_of(InterruptFrame) == 40


def idt_set_gate(vector: u8, handler: usize, ist: u8) -> None:
    """Point gate `vector` at the code at address `handler` (kernel code segment, interrupt gate)."""
    e = addr_of(idt_table[vector])
    e.offset_low = u16(handler & 0xFFFF)
    e.selector = KERNEL_CS
    e.ist = ist & 7
    e.type_attr = GATE_INTERRUPT
    e.offset_mid = u16((handler >> 16) & 0xFFFF)
    e.offset_high = u32(handler >> 32)
    e.reserved = 0


def idt_gate_address(e: Ptr[IdtEntry]) -> usize:
    return usize(e.offset_low) | (usize(e.offset_mid) << 16) | (usize(e.offset_high) << 32)


def pic_remap() -> None:
    """Move the two 8259 PICs to vectors 32..47 and unmask only IRQ0 (the timer)."""
    outb(0x20, 0x11)
    outb(0xA0, 0x11)
    outb(0x21, 32)
    outb(0xA1, 40)
    outb(0x21, 4)
    outb(0xA1, 2)
    outb(0x21, 0x01)
    outb(0xA1, 0x01)
    outb(0x21, 0xFE)
    outb(0xA1, 0xFF)


def pit_init(hz: u32) -> None:
    """Channel 0, rate generator, 1193182 / hz."""
    divisor = u16(1193182 // hz)
    outb(0x43, 0x36)
    outb(0x40, u8(divisor & 0xFF))
    outb(0x40, u8(divisor >> 8))


def halt_forever() -> None:
    while True:
        asm("cli")
        asm("hlt")


def exception_log(vector: u8, ip: usize, error: usize) -> None:
    global idt_exceptions, idt_last_vector, idt_last_ip, idt_last_error
    idt_exceptions += 1
    idt_last_vector = vector
    idt_last_ip = ip
    idt_last_error = error
    console_write(as_ptr(_msg_exception), u32(len(_msg_exception)))
    console_put_dec(u64(vector))
    console_write(as_ptr(_msg_at), u32(len(_msg_at)))
    console_put_hex(u64(ip))
    console_write(as_ptr(_msg_error), u32(len(_msg_error)))
    console_put_hex(u64(error))
    console_write(as_ptr(_msg_nl), 1)


def exception_fatal(vector: u8, ip: usize, error: usize) -> None:
    exception_log(vector, ip, error)
    console_write(as_ptr(_msg_halt), u32(len(_msg_halt)))
    halt_forever()


def timer_tick() -> None:
    global idt_tick_count
    idt_tick_count += 1
    outb(0x20, 0x20)            # end of interrupt to the master PIC


def idt_ticks() -> u64:
    return idt_tick_count


@interrupt
def isr_divide(frame: Ptr[InterruptFrame]) -> None:
    exception_fatal(0, frame.ip, 0)


@interrupt
def isr_breakpoint(frame: Ptr[InterruptFrame]) -> None:
    exception_log(VEC_BREAKPOINT, frame.ip, 0)         # a trap: returns to the instruction after int3


@interrupt
def isr_invalid_opcode(frame: Ptr[InterruptFrame]) -> None:
    exception_fatal(6, frame.ip, 0)


@interrupt
def isr_double_fault(frame: Ptr[InterruptFrame], error: usize) -> None:
    exception_fatal(8, frame.ip, error)


@interrupt
def isr_general_protection(frame: Ptr[InterruptFrame], error: usize) -> None:
    exception_fatal(13, frame.ip, error)


@interrupt
def isr_page_fault(frame: Ptr[InterruptFrame], error: usize) -> None:
    cr2: u64 = 0
    asm("movq %%cr2, %0", outputs=[("=r", cr2)])
    console_put_hex(cr2)
    exception_fatal(14, frame.ip, error)


@interrupt
def isr_timer(frame: Ptr[InterruptFrame]) -> None:
    timer_tick()


@interrupt
def isr_spurious(frame: Ptr[InterruptFrame]) -> None:
    pass


def idt_build() -> None:
    """Fill the table: every gate to isr_spurious first, then the ones with real handlers."""
    for v in range(u32(256)):
        idt_set_gate(u8(v), addr(isr_spurious), 0)
    idt_set_gate(0, addr(isr_divide), 0)
    idt_set_gate(VEC_BREAKPOINT, addr(isr_breakpoint), 0)
    idt_set_gate(6, addr(isr_invalid_opcode), 0)
    idt_set_gate(8, addr(isr_double_fault), 0)
    idt_set_gate(13, addr(isr_general_protection), 0)
    idt_set_gate(14, addr(isr_page_fault), 0)
    idt_set_gate(VEC_TIMER, addr(isr_timer), 0)
    idt_pointer.limit = u16(size_of(IdtEntry) * 256 - 1)
    idt_pointer.base = u64(addr(addr_of(idt_table)))


def idt_load() -> None:
    asm("lidt %0", inputs=[("m", idt_pointer)])


def idt_install() -> None:
    """Build the table, remap the PIC, start the PIT at PIT_HZ and load the IDT (interrupts stay off)."""
    idt_build()
    pic_remap()
    pit_init(PIT_HZ)
    idt_load()

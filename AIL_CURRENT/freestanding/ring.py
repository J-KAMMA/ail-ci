"""A byte ring buffer: the queue a keyboard or serial interrupt handler fills and the kernel drains.

head and tail count bytes ever written and read; they wrap at 2**32, and head - tail is the fill.
"""
from ail_freestanding import u8, u32, Array, struct, wrapping

RING_SIZE = 256


@struct
class Ring:
    head: u32
    tail: u32
    data: Array[u8, 256]

    @wrapping
    def count(self) -> u32:
        return self.head - self.tail

    def is_empty(self) -> bool:
        return self.head == self.tail

    @wrapping
    def push(self, b: u8) -> bool:
        if self.head - self.tail == RING_SIZE:
            return False
        self.data[self.head % RING_SIZE] = b
        self.head += 1
        return True

    @wrapping
    def pop(self) -> u32:
        """The next byte, or 0x100 when the ring is empty."""
        if self.head == self.tail:
            return 0x100
        b = self.data[self.tail % RING_SIZE]
        self.tail += 1
        return u32(b)


keyboard: Ring = Ring()


@wrapping
def ring_selftest(seed: u32) -> u32:
    """A deterministic push/pop workload; a checksum of everything popped and refused."""
    r = Ring()
    r.head = seed * 2654435761
    r.tail = r.head
    state: u32 = seed
    total: u32 = 0
    for _ in range(u32(3000)):
        state = state * 1103515245 + 12345
        if (state >> 16) & 3 != 0:
            if not r.push(u8(state >> 8)):
                total = total * 31 + 0xFFFF
        else:
            total = total * 31 + r.pop()
    while not r.is_empty():
        total = total * 31 + r.pop()
    return total ^ r.count()

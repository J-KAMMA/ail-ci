"""A bitmap page-frame allocator: one bit per 4 KiB physical page, 1 = in use.

The kernel calls pa_init with the usable range from the multiboot2 memory map, then pa_alloc and
pa_free hand out physical addresses. Every arithmetic operation here traps on overflow.
"""
from ail_freestanding import u32, u64, usize, Array, Ptr, struct, arithmetic, addr_of, wrapping

arithmetic("checked")

PAGE_SHIFT = 12
PAGE_SIZE = 1 << PAGE_SHIFT
MAX_PAGES = 4096
WORDS = MAX_PAGES // 64
FULL = (1 << 64) - 1


@struct
class PageAllocator:
    bits: Array[u64, 64]
    base: usize
    npages: u32
    used: u32
    hint: u32


frames: PageAllocator = PageAllocator()


def pa_init(pa: Ptr[PageAllocator], base: usize, npages: u32) -> None:
    """Manage npages pages starting at the page-aligned physical address base."""
    if npages > MAX_PAGES:
        npages = MAX_PAGES
    pa.base = base
    pa.npages = npages
    pa.used = 0
    pa.hint = 0
    for w in range(u32(WORDS)):
        pa.bits[w] = 0
    for p in range(npages, u32(MAX_PAGES)):
        pa.bits[p >> 6] = pa.bits[p >> 6] | (u64(1) << (p & 63))


def _lowest_zero(word: u64) -> u32:
    bit: u32 = 0
    while (word >> bit) & 1 != 0:
        bit += 1
    return bit


def pa_alloc(pa: Ptr[PageAllocator]) -> usize:
    """A free page's physical address, or 0 when every page is in use."""
    for k in range(u32(WORDS)):
        w = (pa.hint + k) % WORDS
        if pa.bits[w] != FULL:
            bit = _lowest_zero(pa.bits[w])
            pa.bits[w] = pa.bits[w] | (u64(1) << bit)
            pa.used += 1
            pa.hint = w
            page = w * 64 + bit
            return pa.base + (usize(page) << PAGE_SHIFT)
    return 0


def pa_free(pa: Ptr[PageAllocator], address: usize) -> bool:
    """Give a page back; False for an address outside the range, unaligned, or already free."""
    if address < pa.base or (address - pa.base) & (PAGE_SIZE - 1) != 0:
        return False
    page = (address - pa.base) >> PAGE_SHIFT
    if page >= usize(pa.npages):
        return False
    w = u32(page >> 6)
    mask = u64(1) << (page & 63)
    if pa.bits[w] & mask == 0:
        return False
    pa.bits[w] = pa.bits[w] & ~mask
    pa.used -= 1
    if w < pa.hint:
        pa.hint = w
    return True


def pa_is_used(pa: Ptr[PageAllocator], page: u32) -> bool:
    return (pa.bits[page >> 6] >> (page & 63)) & 1 != 0


def pa_selftest(seed: u32) -> u64:
    """Random allocations and frees over a small range; a checksum of the addresses and results."""
    pa = PageAllocator()
    p = addr_of(pa)
    pa_init(p, usize(0x100000), u32(300) + seed % 200)
    held = Array[usize, 512]()
    nheld: u32 = 0
    state: u32 = seed
    total: u64 = 0
    for _ in range(u32(4000)):
        state = wrapping(state * 1103515245 + 12345)
        if (state >> 16) % 3 != 0 and nheld < 512:
            a = pa_alloc(p)
            total = wrapping(total * 1000003 + u64(a))
            if a != 0:
                held[nheld] = a
                nheld += 1
        elif nheld > 0:
            i = (state >> 8) % nheld
            ok = pa_free(p, held[i])
            total = wrapping(total * 1000003 + u64(ok))
            nheld -= 1
            held[i] = held[nheld]
    total = wrapping(total * 31 + u64(pa_free(p, usize(0x100000) + 5)))
    total = wrapping(total * 31 + u64(pa.used))
    return total

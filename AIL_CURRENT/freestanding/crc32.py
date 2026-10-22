"""CRC-32 (IEEE 802.3, the one zlib computes), table-driven, as a kernel checks a loaded module."""
from ail_freestanding import u8, u32, usize, Array, Ptr

POLY = 0xEDB88320

crc_table: Array[u32, 256] = Array[u32, 256]()
_ready: bool = False


def crc32_init() -> None:
    global _ready
    for n in range(u32(256)):
        c = n
        for _ in range(8):
            if c & 1:
                c = (c >> 1) ^ POLY
            else:
                c = c >> 1
        crc_table[n] = c
    _ready = True


def crc32_update(crc: u32, data: Ptr[u8], n: usize) -> u32:
    """Continue a CRC over n bytes; start with crc = 0."""
    if not _ready:
        crc32_init()
    c = crc ^ 0xFFFFFFFF
    for i in range(n):
        c = crc_table[(c ^ u32(data[i])) & 0xFF] ^ (c >> 8)
    return c ^ 0xFFFFFFFF

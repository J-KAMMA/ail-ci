"""G5a: the stdlib `zlib` module (compress, decompress, crc32, adler32) for AIL, written over the C FFI.

`import zlib` in a program compiled by AIL finds this file when the program's own directory has no
`zlib.py` (ail_modules.py searches the bundled `stdlib/` last). Under CPython the same program imports
the real `zlib`; the two print the same bytes because both call the system zlib. This file also runs
under CPython through the `ail_ffi` shim (its tests do that), which is how the FFI itself is compared.

Supported: compress(data, level=-1, wbits=15), decompress(data, wbits=15, bufsize=16384), crc32(data,
value=0), adler32(data, value=1), the numeric constants, and `except zlib.error` (spelt RuntimeError
inside the compiler, as csv.Error is ValueError there: the message is CPython's `Error -3 while
decompressing data: incorrect header check`). Not yet: compressobj/decompressobj, the dictionary and
flush APIs. Arguments are `bytes` (a bytearray or memoryview is converted with bytes() first).
"""
from ail_ffi import extern, length, c_int, c_ulong, c_uint, c_size_t, c_char_p

MAX_WBITS = 15
DEFLATED = 8
DEF_MEM_LEVEL = 8
DEF_BUF_SIZE = 16384
Z_NO_COMPRESSION = 0
Z_BEST_SPEED = 1
Z_BEST_COMPRESSION = 9
Z_DEFAULT_COMPRESSION = -1
Z_FILTERED = 1
Z_HUFFMAN_ONLY = 2
Z_RLE = 3
Z_FIXED = 4
Z_DEFAULT_STRATEGY = 0
Z_NO_FLUSH = 0
Z_PARTIAL_FLUSH = 1
Z_SYNC_FLUSH = 2
Z_FULL_FLUSH = 3
Z_FINISH = 4
Z_BLOCK = 5
Z_TREES = 6


@extern(lib="z", header="zlib.h", symbol="crc32")
def zlib_crc32(crc: c_ulong, buf: bytes, n: length("buf", c_uint)) -> c_ulong: ...


@extern(lib="z", header="zlib.h", symbol="adler32")
def zlib_adler32(adler: c_ulong, buf: bytes, n: length("buf", c_uint)) -> c_ulong: ...


@extern(lib="z", header="zlib_glue.h", sources=["zlib_glue.c"])
def zglue_deflate(level: c_int, wbits: c_int, src: bytes, n: length("src", c_size_t)) -> c_int: ...


@extern(lib="z", header="zlib_glue.h", sources=["zlib_glue.c"])
def zglue_inflate(wbits: c_int, src: bytes, n: length("src", c_size_t), bufsize: c_size_t) -> c_int: ...


@extern(lib="z", header="zlib_glue.h", sources=["zlib_glue.c"])
def zglue_size() -> c_size_t: ...


@extern(lib="z", header="zlib_glue.h", sources=["zlib_glue.c"])
def zglue_take(dst: bytearray, n: length("dst", c_size_t)) -> c_int: ...


@extern(lib="z", header="zlib_glue.h", sources=["zlib_glue.c"])
def zglue_errmsg() -> c_char_p: ...


def crc32(data: bytes, value: int = 0) -> int:
    return zlib_crc32(value, data)


def adler32(data: bytes, value: int = 1) -> int:
    return zlib_adler32(value, data)


def compress(data: bytes, level: int = -1, wbits: int = 15) -> bytes:
    rc = zglue_deflate(level, wbits, data)
    if rc != 0:
        raise RuntimeError(zglue_errmsg())
    out = bytearray(zglue_size())
    zglue_take(out)
    return bytes(out)


def decompress(data: bytes, wbits: int = 15, bufsize: int = 16384) -> bytes:
    if bufsize < 0:
        raise ValueError("bufsize must be non-negative")
    rc = zglue_inflate(wbits, data, bufsize)
    if rc != 0:
        raise RuntimeError(zglue_errmsg())
    out = bytearray(zglue_size())
    zglue_take(out)
    return bytes(out)

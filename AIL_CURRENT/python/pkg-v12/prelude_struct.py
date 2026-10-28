# -*- coding: utf-8 -*-
# prelude_struct.py -- the runtime helpers of `struct.pack`, `unpack`, `unpack_from` and `pack_into`
# (structlib.py injects the ones a program uses).  The format string is parsed by the compiler, so the
# helpers only handle the codes it accepted; bytes are built with int.to_bytes / int.from_bytes.


class error(Exception):
    pass


def _ail_struct_int(v, size: int, signed: bool, code: str, lo, hi, order: str) -> bytes:
    if isinstance(v, bool):
        v = int(v)
    if not isinstance(v, int):
        raise error("required argument is not an integer")
    if v < lo or v > hi:
        raise error("'" + code + "' format requires " + str(lo) + " <= number <= " + str(hi))
    return v.to_bytes(size, order, signed=signed)


def _ail_struct_bool(v) -> bytes:
    if v:
        return b"\x01"
    return b"\x00"


def _ail_struct_char(v) -> bytes:
    if isinstance(v, bytes) or isinstance(v, bytearray):
        if len(v) != 1:
            raise error("char format requires a bytes object of length 1")
        return bytes(v)
    raise error("char format requires a bytes object of length 1")


def _ail_struct_s(v, n: int) -> bytes:
    if isinstance(v, bytes):
        data = v
    elif isinstance(v, bytearray):
        data = bytes(v)
    else:
        raise error("argument for 's' must be a bytes object")
    if len(data) > n:
        data = data[:n]
    if len(data) < n:
        data = data + b"\x00" * (n - len(data))
    return data


def _ail_struct_p(v, n: int) -> bytes:
    if isinstance(v, bytes):
        data = v
    elif isinstance(v, bytearray):
        data = bytes(v)
    else:
        raise error("argument for 'p' must be a bytes object")
    if n <= 0:
        return b""
    limit = n - 1
    if limit > 255:
        limit = 255
    if len(data) > limit:
        data = data[:limit]
    return len(data).to_bytes(1, "big") + data + b"\x00" * (n - 1 - len(data))


def _ail_struct_unpack_int(b, size: int, signed: bool, order: str) -> int:
    return int.from_bytes(b, order, signed=signed)


def _ail_struct_unpack_bool(b) -> bool:
    return b[0] != 0


def _ail_struct_unpack_char(b) -> bytes:
    return bytes(b)


def _ail_struct_unpack_s(b) -> bytes:
    return bytes(b)


def _ail_struct_unpack_p(b, n: int) -> bytes:
    if n <= 0:
        return b""
    k = b[0]
    if k > n - 1:
        k = n - 1
    return bytes(b[1:1 + k])


def _ail_struct_check(data, offset: int, size: int, exact: int) -> None:
    if not (isinstance(data, bytes) or isinstance(data, bytearray)):
        raise TypeError("a bytes-like object is required, not '" + type(data).__name__ + "'")
    if exact != 0:
        if len(data) != size:
            raise error("unpack requires a buffer of " + str(size) + " bytes")
        return
    if offset < 0:
        raise error("not enough data to unpack " + str(size) + " bytes at offset " + str(offset))
    if offset + size > len(data):
        raise error("unpack_from requires a buffer of at least " + str(offset + size) + " bytes for unpacking "
                    + str(size) + " bytes at offset " + str(offset) + " (actual buffer size is " + str(len(data)) + ")")


def _ail_struct_store(buf, offset: int, data: bytes) -> None:
    if not isinstance(buf, bytearray):
        raise TypeError("argument 1 must be a read-write bytes-like object, not " + type(buf).__name__)
    if offset < 0:
        raise error("no space to pack " + str(len(data)) + " bytes at offset " + str(offset))
    need = offset + len(data)
    if need > len(buf):
        raise error("pack_into requires a buffer of at least " + str(need) + " bytes for packing " + str(len(data))
                    + " bytes at offset " + str(offset) + " (actual buffer size is " + str(len(buf)) + ")")
    i = 0
    while i < len(data):
        buf[offset + i] = data[i]
        i += 1

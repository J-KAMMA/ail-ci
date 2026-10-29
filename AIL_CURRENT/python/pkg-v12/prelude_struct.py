# The `struct` scalar helpers (library batch 6) injected by stdlib4/structlib.py.  The format string is
# checked at compile time, so the pack/unpack field expressions and the unpack function itself are generated
# there; this file holds the few checks that are easier to write once.  It is plain Python and also runs under
# CPython next to the struct module.
def _ail_struct_bytes(value: bytes, code: str) -> bytes:
    if isinstance(value, bytes):
        return value
    if isinstance(value, bytearray):
        return bytes(value)
    raise ValueError("argument for '%s' must be a bytes object" % code)


def _ail_struct_pack_c(value: bytes) -> bytes:
    if not isinstance(value, bytes) or len(value) != 1:
        raise ValueError('char format requires a bytes object of length 1')
    return value


def _ail_struct_pack_s(value: bytes, count: int) -> bytes:
    data: bytes = _ail_struct_bytes(value, 's')
    if len(data) >= count:
        return data[:count]
    return data + b'\x00' * (count - len(data))


def _ail_struct_pack_p(value: bytes, count: int) -> bytes:
    data: bytes = _ail_struct_bytes(value, 'p')
    if count <= 0:
        return b''
    room: int = count - 1
    if len(data) > room:
        data = data[:room]
    return bytes([len(data)]) + data + b'\x00' * (room - len(data))


def _ail_struct_pascal(data: bytes, pos: int, count: int) -> bytes:
    if count <= 0:
        return b''
    n: int = data[pos]
    room: int = count - 1
    if n > room:
        n = room
    return bytes(data[pos + 1:pos + 1 + n])


def _ail_struct_bool(value: bool) -> bytes:
    if value:
        return b'\x01'
    return b'\x00'


def _ail_struct_int_bytes(value: int, size: int, order: str, signed: bool, code: str) -> bytes:
    if not isinstance(value, int):
        raise ValueError("required argument is not an integer")
    try:
        return int(value).to_bytes(size, order, signed=signed)
    except OverflowError:
        raise ValueError("argument out of range for format code '%s'" % code)


def _ail_struct_arity(got: int, want: int) -> bytes:
    if got != want:
        raise ValueError('struct.pack: the format needs %d values but got %d' % (want, got))
    return b''

# The bytes-like check for `struct.unpack` / `struct.unpack_from`, injected only where the general runtime
# can raise TypeError (the typed path refuses a non-buffer at compile time).  It is plain Python and also
# runs under CPython next to the struct module.
def _ail_struct_buffer(data: bytes) -> bytes:
    if isinstance(data, bytes):
        return data
    if isinstance(data, bytearray):
        return bytes(data)
    raise TypeError("a bytes-like object is required, not '" + type(data).__name__ + "'")

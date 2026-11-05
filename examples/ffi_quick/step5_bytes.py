from ail_ffi import *

@extern(header="add.h", sources=["add.c"])
def ail_quick_reverse(src: bytes, n: length("src", c_size_t), dst: bytearray) -> None: ...


out = bytearray(5)
ail_quick_reverse(b"hello", out)
print(out.decode())

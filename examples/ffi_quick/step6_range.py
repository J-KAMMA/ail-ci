from ail_ffi import *

@extern(header="add.h", sources=["add.c"])
def ail_quick_add32(a: c_int32, b: c_int32) -> c_int32: ...


print(ail_quick_add32(2147483647, 0))
try:
    ail_quick_add32(2147483648, 0)
except OverflowError as e:
    print(type(e).__name__)

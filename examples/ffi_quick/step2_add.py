from ail_ffi import *

@extern(header="add.h", sources=["add.c"])
def ail_quick_add(a: c_int64, b: c_int64) -> c_int64: ...


print(ail_quick_add(2, 3))
print(ail_quick_add(-40, 2))

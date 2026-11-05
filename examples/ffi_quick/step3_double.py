from ail_ffi import *

@extern(header="add.h", sources=["add.c"])
def ail_quick_average(a: c_double, b: c_double) -> c_double: ...


print(ail_quick_average(3.5, 4.25))
print(ail_quick_average(0.1, 0.2))

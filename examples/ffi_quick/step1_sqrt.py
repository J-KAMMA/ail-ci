from ail_ffi import *

link("m")

@extern(header="math.h", symbol="sqrt")
def c_sqrt(x: c_double) -> c_double: ...


print(c_sqrt(9.0))
print(c_sqrt(2.0))

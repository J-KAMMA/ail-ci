from ail_ffi import *

@extern(header="add.h", sources=["add.c"])
def ail_quick_strlen(text: c_char_p) -> c_size_t: ...


print(ail_quick_strlen(""))
print(ail_quick_strlen("hello"))
print(ail_quick_strlen("héllo"))

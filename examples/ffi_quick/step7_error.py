from ail_ffi import *

@extern(header="add.h", sources=["add.c"], check="negative", errno=True)
def ail_quick_parse(text: c_char_p) -> c_int64: ...


print(ail_quick_parse("1234"))
try:
    ail_quick_parse("12a4")
except OSError as e:
    print(type(e).__name__, e)

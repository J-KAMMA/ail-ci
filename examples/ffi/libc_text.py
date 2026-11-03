from ail_ffi import *

@extern(header="string.h", symbol="strlen")
def c_strlen(s: c_char_p) -> c_size_t: ...

@extern(header="stdlib.h", symbol="strtol", trust=True)
def c_strtol(s: c_char_p, end: ptr(c_void_p), base: c_int) -> c_long: ...

@extern(header="stdlib.h", symbol="strtol", trust=True,
         check="negative", errno=True)
def c_strtol_checked(s: c_char_p, end: ptr(c_void_p), base: c_int) -> c_long: ...

@extern(header="ctype.h", symbol="toupper")
def c_toupper(c: c_int) -> c_int: ...


def to_long(text: str, base: int) -> int:
    return c_strtol(text, bytearray(8), base)


def upper(buf: bytearray) -> None:
    for i in range(len(buf)):
        buf[i] = c_toupper(buf[i])


def main():
    print(c_strlen(""), c_strlen("hello"), c_strlen("héllo"))
    print(to_long("ff", 16), to_long("7fffffffffffffff", 16),
          to_long("z", 36), to_long("zzzzzzzzzzzz", 36))
    text = bytearray(b"Mixed Case 123")
    upper(text)
    print(text.decode())
    try:
        c_strtol_checked("-8000000000000001", bytearray(8), 16)
    except OSError as e:
        print(str(e))


main()

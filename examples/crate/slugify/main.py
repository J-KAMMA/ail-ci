from slugify_ffi import slugify


def show(text, room):
    out = bytearray(room)
    got = slugify(text, out)
    if got < 0:
        print("need", -got)
    else:
        print(got, bytes(out[0:got]).decode())


def main():
    show(b"Hello, World!", 64)
    show(b"  --A__b--  ", 64)
    show(b"already-slug", 64)
    show(b"", 4)
    show(b"Hello, World!", 3)
    show(b"caf\xc3\xa9 \xe2\x9c\x93", 64)
    show(b"a b c", 4)


main()

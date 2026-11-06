"""chunk: EOFError on a short header, ValueError on use after close."""
import chunk


def be(n):
    return n.to_bytes(4, "big")


def show(what, func):
    try:
        func()
        print(what, "ok")
    except Exception as e:
        print(what, type(e).__name__, repr(str(e)))


def main():
    f = open("short.iff", "wb")
    f.write(b"ABC")
    f.close()

    def short_header():
        f = open("short.iff", "rb")
        c = chunk.Chunk(f)
        c.close()
        f.close()

    show("header", short_header)

    f = open("good.iff", "wb")
    f.write(b"GOOD" + be(4) + b"abcd")
    f.close()

    f = open("good.iff", "rb")
    c = chunk.Chunk(f)
    print("name", c.getname(), c.getsize())
    c.close()
    print("closed", c.closed)

    def read_closed():
        c.read()

    def seek_closed():
        c.seek(0)

    def tell_closed():
        c.tell()

    def tty_closed():
        c.isatty()

    show("read", read_closed)
    show("seek", seek_closed)
    show("tell", tell_closed)
    show("isatty", tty_closed)
    f.close()


main()

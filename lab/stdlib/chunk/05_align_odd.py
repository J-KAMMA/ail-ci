"""chunk: align=True consumes the pad byte of an odd chunk; align=False does not."""
import chunk


def be(n):
    return n.to_bytes(4, "big")


def main():
    f = open("aligned.iff", "wb")
    f.write(b"ODD1" + be(1) + b"x" + b"\x00")
    f.write(b"NEXT" + be(0))
    f.close()

    f = open("aligned.iff", "rb")
    c = chunk.Chunk(f)
    print("name", c.getname(), c.getsize())
    print("data", c.read())
    print("tell", c.tell(), "file", f.tell())
    n = chunk.Chunk(f)
    print("next", n.getname(), n.getsize())
    n.close()
    c.close()
    f.close()

    f = open("plain.iff", "wb")
    f.write(b"ODD1" + be(1) + b"x")
    f.write(b"NEXT" + be(0))
    f.close()

    f = open("plain.iff", "rb")
    c = chunk.Chunk(f, align=False)
    print("name", c.getname(), c.getsize())
    print("data", c.read())
    print("tell", c.tell(), "file", f.tell())
    n = chunk.Chunk(f, align=False)
    print("next", n.getname(), n.getsize())
    n.close()
    c.close()
    f.close()


main()

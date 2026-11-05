"""chunk: seek with whence 0, 1 and 2, plus skip() to the next chunk."""
import chunk


def be(n):
    return n.to_bytes(4, "big")


def main():
    payload = b"abcdefghijkl"
    f = open("seek.iff", "wb")
    f.write(b"SEEK" + be(len(payload)) + payload + b"TAIL" + be(1) + b"z")
    f.close()

    f = open("seek.iff", "rb")
    c = chunk.Chunk(f)
    print("start", c.tell(), f.tell())
    c.seek(0)
    print("w0", c.tell(), f.tell())
    c.seek(3, 0)
    print("w0", c.tell(), f.tell())
    c.seek(2, 1)
    print("w1", c.tell(), f.tell())
    c.seek(-1, 2)
    print("w2", c.tell(), f.tell())
    c.seek(0, 2)
    print("w2", c.tell(), f.tell())
    print("end", c.read())
    c.close()
    print("closedpos", c.closed, f.tell())
    f.close()

    f = open("seek.iff", "rb")
    c = chunk.Chunk(f)
    print("skipname", c.getname(), c.tell())
    c.skip()
    print("after", c.tell(), f.tell())
    n = chunk.Chunk(f)
    print("next", n.getname(), n.getsize(), n.read())
    n.close()
    f.close()


main()

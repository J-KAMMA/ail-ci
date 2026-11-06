"""chunk: a Chunk over a Chunk, and seek bounds raise RuntimeError."""
import chunk


def be(n):
    return n.to_bytes(4, "big")


def main():
    inner_bytes = b"INNE" + be(12) + b"abcdefghijkl"
    tail_bytes = b"TAIL" + be(1) + b"z"
    payload = inner_bytes + tail_bytes
    f = open("outer.iff", "wb")
    f.write(b"FORM" + be(len(payload)) + payload)
    f.close()

    f = open("outer.iff", "rb")
    outer = chunk.Chunk(f)
    print("outer", outer.getname(), outer.getsize())
    inner = chunk.Chunk(outer)
    print("inner", inner.getname(), inner.getsize(), inner.read())
    inner.close()
    print("outert", outer.tell(), f.tell())
    print("formlen", len(outer.read()))
    outer.close()
    f.close()

    f = open("outer.iff", "rb")
    c = chunk.Chunk(f)
    for pos in (-1, 30, 29):
        try:
            c.seek(pos)
            print("seek", pos, "ok", c.tell())
        except RuntimeError:
            print("seek", pos, "RuntimeError")
    print("at", c.tell())
    c.close()
    f.close()


main()

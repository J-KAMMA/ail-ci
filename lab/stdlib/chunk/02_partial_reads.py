"""chunk: read(n) in pieces, a short read at the end, and tell after each."""
import chunk


def be(n):
    return n.to_bytes(4, "big")


def main():
    payload = b"0123456789ab"
    f = open("parts.iff", "wb")
    f.write(b"DATA" + be(len(payload)) + payload)
    f.close()

    f = open("parts.iff", "rb")
    c = chunk.Chunk(f)
    print("name", c.getname())
    print("r1", c.read(3), c.tell())
    print("r2", c.read(4), c.tell())
    print("r3", c.read(100), c.tell())
    print("r4", c.read(1), c.tell())
    print("r5", c.read(-5), c.tell())
    c.close()
    f.close()


main()

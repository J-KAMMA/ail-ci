"""chunk: inclheader=True subtracts the 8-byte header from the size field."""
import chunk


def be(n):
    return n.to_bytes(4, "big")


def main():
    payload = b"wxyz"
    f = open("plain.iff", "wb")
    f.write(b"HEAD" + be(len(payload)) + payload)
    f.close()

    f = open("plain.iff", "rb")
    c = chunk.Chunk(f)
    print("plain", c.getname(), c.getsize(), c.read())
    c.close()
    f.close()

    f = open("incl.iff", "wb")
    f.write(b"HEAD" + be(len(payload) + 8) + payload)
    f.close()

    f = open("incl.iff", "rb")
    c = chunk.Chunk(f, inclheader=True)
    print("incl", c.getname(), c.getsize())
    print("tell", c.tell())
    print("data", c.read())
    print("tell", c.tell())
    c.close()
    print("file", f.tell())
    f.close()

    f = open("incl.iff", "rb")
    c = chunk.Chunk(f, inclheader=True)
    c.seek(0, 2)
    print("end", c.tell(), c.read())
    c.close()
    f.close()


main()

"""chunk: a size field of 0xFFFFFFFF stays a positive int64 (4294967295)."""
import chunk


def main():
    f = open("huge.iff", "wb")
    f.write(b"HUGE" + (0xFFFFFFFF).to_bytes(4, "big") + b"tail")
    f.close()

    f = open("huge.iff", "rb")
    c = chunk.Chunk(f)
    print("name", c.getname())
    print("size", c.getsize())
    print("big", c.getsize() > 2147483647)
    print("data", c.read(4), c.tell())
    c.seek(0, 2)
    print("end", c.tell())
    print("rest", c.read())
    c.close()
    print("file", f.tell())
    f.close()

    f = open("huge.iff", "rb")
    c = chunk.Chunk(f, inclheader=True)
    print("incl", c.getsize())
    c.close()
    f.close()


main()

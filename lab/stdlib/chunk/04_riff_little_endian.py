"""chunk: RIFF files use little-endian size fields (bigendian=False)."""
import chunk


def le(n):
    return n.to_bytes(4, "little")


def main():
    fmt = b"fmt " + le(16) + b"\x01\x00\x01\x00\x44\xac\x00\x00\x10\x00\x10\x00\x00\x00\x00\x00"
    riff = b"WAVE" + fmt
    f = open("song.wav", "wb")
    f.write(b"RIFF" + le(len(riff)) + riff)
    f.close()

    f = open("song.wav", "rb")
    top = chunk.Chunk(f, bigendian=False)
    print("riff", top.getname(), top.getsize())
    print("form", top.read(4), top.tell())
    c = chunk.Chunk(top, bigendian=False)
    print("name", c.getname())
    print("size", c.getsize())
    data = c.read()
    print("len", len(data))
    print("data", data)
    print("tty", c.isatty())
    c.close()
    print("top", top.tell(), top.getsize())
    print("rest", len(top.read()))
    top.close()
    print("pos", f.tell())
    f.close()


main()

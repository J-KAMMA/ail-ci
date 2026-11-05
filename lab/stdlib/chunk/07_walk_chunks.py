"""chunk: walk every chunk of a file until Chunk raises EOFError."""
import chunk


def be(n):
    return n.to_bytes(4, "big")


def put(name, data):
    out = name + be(len(data)) + data
    if len(data) & 1:
        out = out + b"\x00"
    return out


def main():
    blob = put(b"FMT ", b"\x01\x00\x01\x00\x44\xac")
    blob = blob + put(b"DATA", b"0123456789abc")
    blob = blob + put(b"NOTE", b"")
    f = open("walk.wav", "wb")
    f.write(blob)
    f.close()

    f = open("walk.wav", "rb")
    count = 0
    while True:
        try:
            c = chunk.Chunk(f)
        except EOFError:
            print("eof")
            break
        name = c.getname()
        size = c.getsize()
        data = c.read()
        print(count, name, size, len(data), c.tell(), f.tell())
        c.close()
        count = count + 1
    print("count", count, "filepos", f.tell())
    f.close()


main()

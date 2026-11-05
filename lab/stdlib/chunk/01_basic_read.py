"""chunk: name, size, read() to the end, tell, isatty and close."""
import chunk


def be(n):
    return n.to_bytes(4, "big")


def iff(name, data):
    return name + be(len(data)) + data


def main():
    blob = iff(b"TEST", b"hello world!")
    f = open("basic.iff", "wb")
    f.write(blob)
    f.close()

    f = open("basic.iff", "rb")
    c = chunk.Chunk(f)
    print("name", c.getname())
    print("size", c.getsize())
    print("tty", c.isatty())
    print("at", c.tell())
    data = c.read()
    print("data", data)
    print("len", len(data))
    print("at", c.tell())
    print("again", c.read())
    c.close()
    print("filepos", f.tell())
    f.close()


main()

import struct

FIXED = "<4s3c3p2x"
PASCAL = "<B5p"

def fixed_field(name, letters):
    return struct.pack(FIXED, name, letters[0:1], letters[1:2], letters[2:3], name[:3])

def main():
    print("sizes", struct.calcsize(FIXED), struct.calcsize(PASCAL))
    blob = fixed_field(b"abcdef", b"xyz")
    print(blob.hex(), len(blob))
    print(struct.unpack(FIXED, blob))

    data = struct.pack(PASCAL, 9, b"abcdef")
    print(data.hex(), struct.unpack(PASCAL, data))
    data = struct.pack(PASCAL, 2, b"hi")
    print(data.hex(), struct.unpack(PASCAL, data))
    data = struct.pack(PASCAL, 0, b"")
    print(data.hex(), struct.unpack(PASCAL, data))

    zero = struct.pack("<0s0s", b"ignored", b"ignored")
    print("zero", zero, struct.unpack("<0s0s", b""))
    print("char", struct.pack("<c", b"Q"), struct.unpack("<c", b"Q"))
    print("short string", struct.pack("<8s", b"a\x00b").hex())
    print("short string back", struct.unpack("<8s", b"a\x00b\x00\x00\x00\x00\x00"))

    raw = struct.pack("<4s", b"ab")
    print("padded", raw.hex(), struct.unpack("<4s", raw)[0].rstrip(b"\x00"))

main()

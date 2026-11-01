import struct

def main():
    buffer = bytearray(b"." * 20)
    struct.pack_into("<i", buffer, 0, 100)
    struct.pack_into("<h", buffer, 4, -2)
    struct.pack_into(">I", buffer, 7, 0x01020304)
    print(buffer.hex())

    print(struct.unpack_from("<i", buffer, 0))
    print(struct.unpack_from("<h", buffer, 4))
    print(struct.unpack_from(">I", buffer, 7))
    print(struct.unpack_from("<h", buffer, -6))

    values = (11, 22)
    struct.pack_into("<ii", buffer, 8, *values)
    print(struct.unpack_from("<ii", buffer, 8))

    struct.pack_into("<b", buffer, -1, 9)
    print(buffer[-1], buffer.hex())

    try:
        struct.unpack_from("<i", buffer, 19)
    except struct.error as exc:
        print("unpack", str(exc))

    try:
        struct.pack_into("<i", buffer, 18, 1)
    except struct.error as exc:
        print("pack", str(exc))

    try:
        struct.unpack_from("<i", b"123", -1)
    except struct.error as exc:
        print("negative", str(exc))

    print(len(buffer), struct.unpack_from("<i", buffer, 0)[0])

main()

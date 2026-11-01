import struct

def show(label, data):
    print(label, data)

def main():
    try:
        struct.unpack("<i", b"abc")
    except struct.error as exc:
        show("short", str(exc))

    try:
        struct.unpack("<i", b"abcdefgh")
    except struct.error as exc:
        show("long", str(exc))

    try:
        struct.pack("<B", 256)
    except struct.error as exc:
        show("range", str(exc))

    try:
        struct.pack("<i", "text")
    except struct.error as exc:
        show("type", str(exc))

    try:
        struct.calcsize("<4")
    except struct.error as exc:
        show("format", str(exc))

    try:
        struct.calcsize("<z")
    except struct.error as exc:
        show("char code", str(exc))

    try:
        struct.pack("<ii", 1)
    except struct.error as exc:
        show("count", str(exc))

    try:
        struct.unpack("<i", "1234")
    except TypeError as exc:
        show("buffer type", str(exc))

    buffer = bytearray(2)
    try:
        struct.pack_into("<i", buffer, 0, 1)
    except struct.error as exc:
        show("pack into", str(exc))

    try:
        struct.unpack_from("<i", b"12")
    except struct.error as exc:
        show("unpack from", str(exc))

main()

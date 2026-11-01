import struct

MAGIC = b"SAVE"
VERSION = 3
HEADER = "<4sHII2f"

def make_header(width, height, scale, ratio):
    magic = MAGIC
    flags = 0x8001
    count = width * height
    return struct.pack(HEADER, magic, VERSION, flags, count, scale, ratio)

def read_header(data):
    magic, version, flags, count, scale, ratio = struct.unpack(HEADER, data)
    return magic, version, flags, count, scale, ratio

def main():
    size = struct.calcsize(HEADER)
    print("header size", size)
    blob = make_header(640, 480, 1.5, 0.75)
    print("blob", blob.hex())
    print("fields", read_header(blob))

    buf = bytearray(size + 4)
    struct.pack_into(HEADER, buf, 0, b"IMG2", 9, 0, 12, 2.0, 0.5)
    print("magic", struct.unpack_from("<4s", buf, 0)[0])
    print("flags", struct.unpack_from("<I", buf, 6)[0])
    print("tail", struct.unpack_from("<H", buf, size)[0])

    header = struct.Struct(HEADER)
    print("again", header.unpack(header.pack(MAGIC, 3, 0x8001, 4, 1.0, 1.0)))
    print("checksum", sum(blob) % 251)

main()

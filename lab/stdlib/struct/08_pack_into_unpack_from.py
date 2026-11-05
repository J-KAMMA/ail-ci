"""pack_into and unpack_from on a bytearray at offsets."""
import struct

buf = bytearray(16)
print(len(buf), bytes(buf))
print(struct.pack_into(">i", buf, 0, 0x01020304))
struct.pack_into("<h", buf, 6, -2)
print(bytes(buf))
print(struct.unpack_from(">i", buf, 0))
print(struct.unpack_from("<h", buf, 6))
print(struct.unpack_from(">H", buf, 4))
print(struct.pack_into("=2H", buf, 8, 7, 8))
print(bytes(buf))
print(struct.unpack_from("=2H", buf, 8))
off = 12
struct.pack_into("=i", buf, off, 42)
print(struct.unpack_from("=i", buf, off))
print(struct.calcsize(">i"), struct.calcsize("<h"))
print(struct.unpack_from("=i", bytearray(8), 4))

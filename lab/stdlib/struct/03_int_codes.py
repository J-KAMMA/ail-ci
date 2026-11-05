"""The integer codes b B h H i I l L in standard sizes and in native size."""
import struct

fmt = "=bBhHiIlL"
print(struct.calcsize(fmt))
data = struct.pack(fmt, -1, 255, -2, 65535, -3, 4000000000, -4, 4000000000)
print(data)
print(struct.unpack(fmt, data))
print(struct.calcsize("<bBhHiIlL"), struct.calcsize(">bBhHiIlL"))
print(struct.pack("<I", 0xDEADBEEF))
print(struct.pack(">I", 0xDEADBEEF))
print(struct.pack("=i", -1), struct.pack("=I", 4294967295))
print(struct.unpack("=B", b"\xff"), struct.unpack("=b", b"\xff"))
print(struct.unpack("=H", b"\xff\xff"), struct.unpack("=h", b"\xff\xff"))
print(struct.calcsize("@l"), struct.pack("@l", -5), struct.unpack("@l", struct.pack("@l", -5)))
print(struct.unpack("=I", b"\x00\x00\x01\x00"), struct.unpack(">I", b"\x00\x00\x01\x00"))

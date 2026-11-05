"""Byte orders: '<' little, '>' big, '!' network (big), '=' standard sizes, '@' native."""
import struct

print(struct.pack("<i", 1))
print(struct.pack(">i", 1))
print(struct.pack("!i", 1))
print(struct.pack("=i", 1))
print(struct.pack("@i", 1))
print(struct.pack("<h", 258), struct.pack(">h", 258))
print(struct.calcsize("<i"), struct.calcsize(">i"), struct.calcsize("!i"),
      struct.calcsize("=i"), struct.calcsize("@i"))
print(struct.calcsize("<l"), struct.calcsize("@l"), struct.calcsize("=l"))
print(struct.calcsize("@b"), struct.calcsize("@bi"), struct.calcsize("@bh"))
print(struct.calcsize("=bi"), struct.calcsize("=bh"))
print(struct.unpack(">hhl", struct.pack(">hhl", 1, -2, 3)))
print(struct.unpack("@bh", struct.pack("@bh", 5, 6)))
print(struct.calcsize("@"), struct.pack("@"))
print(struct.pack(">i", 16909060), struct.pack("<i", 16909060))

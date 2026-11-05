"""Repeat counts: "3h", "<5b", ">2i", padding counts and native alignment of counted items."""
import struct

print(struct.calcsize("3h"), struct.pack("=3h", 1, 2, 3))
print(struct.unpack("=3h", b"\x01\x00\x02\x00\x03\x00"))
print(struct.calcsize("<5b"), struct.pack("<5b", 1, 2, 3, 4, 5))
print(struct.calcsize(">2i"), struct.pack(">2i", 1, 2))
print(struct.pack("<4x"))
print(struct.calcsize("2x"), struct.calcsize("3x"), struct.calcsize("0i"))
print(struct.pack("=0i"))
print(struct.unpack(">2H", b"\x00\x01\x00\x02"))
print(struct.calcsize("10s"), struct.pack("=10s", b"abc"))
print(struct.calcsize("2?"), struct.pack("=2?", True, False))
print(struct.pack("=3?", 1, 0, "x"))
print(struct.calcsize("@3h"), struct.calcsize("@3i"), struct.calcsize("@2bh"))
print(struct.unpack("@2bh", struct.pack("@2bh", 1, 2, 3)))

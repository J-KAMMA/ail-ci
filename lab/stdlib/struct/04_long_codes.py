"""The 8-byte codes q Q, and the native-only size_t codes n N."""
import struct

print(struct.calcsize("q"), struct.calcsize("Q"), struct.calcsize("n"), struct.calcsize("N"))
print(struct.calcsize("=q"), struct.calcsize("<q"), struct.calcsize("@q"))
print(struct.pack("=q", 1234567890123))
print(struct.pack(">q", -1234567890123))
print(struct.unpack("=q", struct.pack("=q", -5)))
print(struct.unpack(">Q", b"\x00\x00\x00\x00\x00\x00\x00\x2a"))
print(struct.calcsize("@nN"), struct.calcsize("nN"))
print(struct.pack("=Q", 4611686018427387904))
print(struct.unpack("=q", struct.pack("=q", -2 ** 63)))
print(struct.unpack("n", struct.pack("n", -9)), struct.unpack("N", struct.pack("N", 9)))

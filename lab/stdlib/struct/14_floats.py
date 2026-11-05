"""The float codes e, f and d (the module refuses them until bit-exact conversion exists)."""
import struct

print(struct.calcsize("e"), struct.calcsize("f"), struct.calcsize("d"))
print(struct.pack("<d", 1.5))
print(struct.unpack("<d", struct.pack("<d", -2.25)))
print(struct.pack(">f", 3.25))
print(struct.pack("<e", 1.5))
print(struct.unpack("<2d", struct.pack("<2d", 0.0, 1.0)))
print(struct.pack("@f", 0.5), struct.unpack("@f", struct.pack("@f", 0.5)))

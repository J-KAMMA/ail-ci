"""A mixed record packed and unpacked both ways, plus star-argument round trips."""
import struct

fmt = "<BhHiIq"
print(struct.calcsize(fmt))
data = struct.pack(fmt, 7, 300, 40000, -5, 4000000000, -9000000000)
print(data)
values = struct.unpack(fmt, data)
print(values)
print(values[0], values[5])
for v in values:
    print(v)
back = struct.unpack(">3i", b"\x00\x00\x00\x01\x00\x00\x00\x02\x00\x00\x00\x03")
print(struct.pack(">3i", back[0], back[1], back[2]))
print(struct.unpack("<2h2i", struct.pack("<2h2i", -1, 1, -70000, 70000)))
print(struct.unpack(">Bh", struct.pack(">Bh", 200, -300)))

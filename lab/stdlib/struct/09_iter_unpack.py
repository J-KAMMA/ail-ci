"""iter_unpack over records, with tuple unpacking in the loop."""
import struct

data = struct.pack("=3i", 10, 20, 30)
for item in struct.iter_unpack("=i", data):
    print(item)
record = struct.pack(">Bh", 1, 300) + struct.pack(">Bh", 2, -300)
total = 0
for a, b in struct.iter_unpack(">Bh", record):
    print(a, b)
    total = total + b
print(total)
print(list(struct.iter_unpack("=h", b"\x01\x00\x02\x00")))
for value in struct.iter_unpack("=2H", b"\x00\x01\x00\x02\x00\x03\x00\x04"):
    print(value)
print(struct.calcsize("=i"), struct.calcsize(">Bh"))

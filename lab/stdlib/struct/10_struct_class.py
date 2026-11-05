"""The Struct class: .format, .size and the pack/unpack methods."""
import struct

s = struct.Struct(">hhl")
print(s.format, s.size)
print(s.pack(1, 2, 3))
print(s.unpack(b"\x00\x01\x00\x02\x00\x00\x00\x03"))
t = struct.Struct("<3i")
print(t.format, t.size, t.pack(1, 2, 3))
print(struct.Struct("=B").size, struct.Struct("@bi").size)
buf = bytearray(12)
print(t.pack_into(buf, 0, 5, 6, 7))
print(bytes(buf))
print(t.unpack_from(buf, 0))
print(struct.Struct(">i").format, struct.Struct("<i").format, struct.Struct("!i").format)
print(struct.Struct("=?").pack(True), struct.Struct("=?").unpack(b"\x00"))
for item in struct.Struct("=i").iter_unpack(struct.pack("=2i", 1, 2)):
    print(item)
print(struct.Struct("@bh").size, struct.Struct("=l").size)

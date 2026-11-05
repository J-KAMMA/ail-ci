"""int64 edges: q at both ends, Q up to int64, then Q at 2**64 - 1 (beyond int64)."""
import struct

lo = -2 ** 63
hi = 2 ** 63 - 1
print(struct.pack("=q", lo))
print(struct.pack("=q", hi))
print(struct.unpack("=q", struct.pack("=q", lo)))
print(struct.unpack("=q", struct.pack("=q", hi)))
print(struct.pack("=Q", hi))
print(struct.unpack("=Q", struct.pack("=Q", hi)))
print(struct.pack("<q", -1), struct.pack(">q", -1))
print(struct.calcsize("@q"), struct.calcsize("=q"))
print(struct.unpack(">Q", b"\xff\xff\xff\xff\xff\xff\xff\xff"))

"""The codes ? c s p x: booleans, single chars, fixed and Pascal strings, padding."""
import struct

print(struct.pack("=?", True), struct.pack("=?", False), struct.pack("=?", 3))
print(struct.unpack("=?", b"\x01"), struct.unpack("=?", b"\x00"))
print(struct.pack("=c", b"A"), struct.pack("=3c", b"a", b"b", b"c"))
print(struct.unpack("=c", b"Z"), struct.unpack("=3c", b"abc"))
print(struct.pack("=5s", b"abc"), struct.pack("=2s", b"abcdef"))
print(struct.pack("=5p", b"abc"))
print(struct.unpack("=5s", b"ab\x00\x00\x00"))
print(struct.unpack("=5p", struct.pack("=5p", b"hello")))
print(struct.pack("=3x"), struct.calcsize("=3x"))
print(struct.pack("=b3xb", 1, 2), struct.unpack("=b3xb", b"\x01\x00\x00\x00\x02"))
print(struct.unpack("=5p", b"\x02ab\x00\x00"))
print(struct.pack("=0s", b""), struct.pack("=1s", b"z"), struct.pack("=4p", b"abc"))

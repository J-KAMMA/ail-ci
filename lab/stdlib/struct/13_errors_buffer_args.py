"""Buffer-length errors, argument-count errors and the s/c argument checks."""
import struct

try:
    struct.unpack("<i", b"ab")
except struct.error as e:
    print(str(e))
try:
    struct.unpack("<i", b"abcdefgh")
except struct.error as e:
    print(str(e))
try:
    struct.unpack_from("<i", bytearray(2), 0)
except struct.error as e:
    print(str(e))
try:
    struct.pack_into("<i", bytearray(2), 0, 1)
except struct.error as e:
    print(str(e))
try:
    struct.unpack_from("<i", bytearray(4), 4)
except struct.error as e:
    print(str(e))
try:
    struct.pack_into("<i", bytearray(4), 4, 1)
except struct.error as e:
    print(str(e))
try:
    struct.pack("<i", 1, 2)
except struct.error as e:
    print(str(e))
try:
    struct.pack("<i")
except struct.error as e:
    print(str(e))
try:
    struct.pack("c", b"ab")
except struct.error as e:
    print(str(e))
try:
    struct.pack("5s", 5)
except struct.error as e:
    print(str(e))
try:
    struct.iter_unpack("<i", b"abcde")
except struct.error as e:
    print(str(e))

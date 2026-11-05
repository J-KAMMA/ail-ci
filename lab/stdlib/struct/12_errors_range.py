"""Each range error and the bad format char, caught and printed with str(e)."""
import struct

try:
    struct.pack("<h", 32768)
except struct.error as e:
    print(str(e))
try:
    struct.pack("<h", -32769)
except struct.error as e:
    print(str(e))
try:
    struct.pack("B", 256)
except struct.error as e:
    print(str(e))
try:
    struct.pack("b", -129)
except struct.error as e:
    print(str(e))
try:
    struct.pack("<i", 2147483648)
except struct.error as e:
    print(str(e))
try:
    struct.pack("<I", -1)
except struct.error as e:
    print(str(e))
try:
    struct.pack("<Q", -1)
except struct.error as e:
    print(str(e))
try:
    struct.calcsize("<z")
except struct.error as e:
    print(str(e))
try:
    struct.pack("<z", 1)
except struct.error as e:
    print(str(e))
try:
    struct.Struct("<i<")
except struct.error as e:
    print(str(e))

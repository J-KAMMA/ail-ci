import struct
from struct import Struct as Record

def main():
    point = struct.Struct("<hh")
    print(point.format, point.size)
    print(point.pack(3, -4).hex())
    print(point.unpack(b"\xff\xff\x02\x00"))

    item = Record(format="<I8s")
    print(item.format, item.size)
    blob = item.pack(42, b"sample")
    print(blob.hex(), item.unpack(blob))

    buffer = bytearray(12)
    point.pack_into(buffer, 0, 1, 2)
    point.pack_into(buffer, 4, 3, 4)
    print(buffer.hex())
    print(point.unpack_from(buffer, 0))
    print(point.unpack_from(buffer, 4))
    print(point.unpack_from(buffer, -4))

    records = item.pack(1, b"a") + item.pack(2, b"b")
    unpacked = list(item.iter_unpack(records))
    print(unpacked)
    print(len(unpacked))

    print(point.size == struct.calcsize(point.format))
    print(item.format)

main()

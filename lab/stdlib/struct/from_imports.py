from struct import pack, unpack, calcsize
from struct import pack as write, unpack as read

def main():
    values = (1, 2, 3)
    blob = pack("<iii", *values)
    print(blob.hex(), len(blob))
    print(unpack("<iii", blob))
    print(write(">H", 513).hex(), read(">H", b"\x02\x01"))
    print(calcsize("<iii"), calcsize(""), calcsize("<0s"))

    empty = pack("")
    print(empty, unpack("", empty))
    zero = pack("<0s0s", b"abc", b"xyz")
    print(zero, unpack("<0s0s", b""))

    data = pack("<HHH", 1, 2, 3)
    print(data.hex())
    print(unpack("<H", data[:2]), unpack("<H", data[2:4]), unpack("<H", data[4:]))

    print(pack("<b", -1).hex(), unpack("<b", b"\xff"))
    print(pack("<q", -2).hex(), unpack("<q", b"\xfe\xff\xff\xff\xff\xff\xff\xff"))

main()

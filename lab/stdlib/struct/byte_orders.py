import struct

INT = "<i"
BIG = ">i"
NATIVE = "@i"
EQUALS = "=i"

def main():
    value = 0x01020304
    print(INT, struct.pack(INT, value).hex())
    print(BIG, struct.pack(BIG, value).hex())
    print(NATIVE, struct.pack(NATIVE, value).hex())
    print(EQUALS, struct.pack(EQUALS, value).hex())
    print(struct.unpack(INT, struct.pack(INT, value)))
    print(struct.unpack(BIG, struct.pack(BIG, value)))

    print("long sizes", struct.calcsize("@l"), struct.calcsize("=l"),
          struct.calcsize("<l"), struct.calcsize("!l"))
    print("short sizes", struct.calcsize("@h"), struct.calcsize("=h"),
          struct.calcsize("<h"), struct.calcsize("!h"))
    print("native pointer", struct.calcsize("@P"), struct.calcsize("@n"), struct.calcsize("@N"))

    for order in ("<", ">", "!", "=", "@"):
        fmt = order + "HHi"
        print(order, struct.calcsize(fmt), struct.pack(fmt, 1, 2, 3).hex())

    mixed = struct.pack("<bHi", 1, 2, 3)
    print("mixed", mixed.hex(), struct.unpack("<bHi", mixed))
    spaced = struct.pack("< b H i", 4, 5, 6)
    print("spaced", spaced.hex(), struct.unpack("< b H i", spaced))

main()

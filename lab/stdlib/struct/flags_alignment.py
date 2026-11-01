import struct

FLAGS = "<???BBHI"
NATIVE = "@bhi"
PAD = "@bxi"

def describe(mask):
    enabled = []
    for index, name in enumerate(("ready", "error", "busy")):
        if mask[index]:
            enabled.append(name)
    return enabled

def main():
    print("flags size", struct.calcsize(FLAGS))
    mask = struct.unpack("<???", struct.pack("<???", True, False, True))
    print(mask, describe(mask))
    blob = struct.pack(FLAGS, True, True, False, 7, 250, 300, 70000)
    print(blob.hex())
    print(struct.unpack(FLAGS, blob))

    print("native", struct.calcsize(NATIVE), struct.calcsize(PAD))
    native = struct.pack(NATIVE, 1, 2, 3)
    print(native.hex(), len(native))
    print(struct.unpack(NATIVE, native))
    padded = struct.pack(PAD, 5, 6)
    print(padded.hex(), len(padded), struct.unpack(PAD, padded))

    for value in (True, False, 0, 1, 2, -1, "", "x", [], [0]):
        print(repr(value), struct.pack("<?", value).hex())
    print("standard", struct.calcsize("=bhi"), struct.calcsize("<bhi"))
    print("native pair", struct.calcsize("@bi"), struct.calcsize("@ib"))

main()

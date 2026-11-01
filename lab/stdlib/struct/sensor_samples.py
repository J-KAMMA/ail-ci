import struct

SAMPLE = "<q3f"
HALF = "<eH"

def encode(timestamp, values):
    return struct.pack(SAMPLE, timestamp, values[0], values[1], values[2])

def decode(blob):
    timestamp, x, y, z = struct.unpack(SAMPLE, blob)
    return timestamp, x, y, z

def main():
    samples = [
        (0, (0.0, 1.0, -1.0)),
        (1700000000, (1.5, 2.25, -0.125)),
        (1700000001, (100.0, 0.0, 65504.0)),
    ]
    for timestamp, values in samples:
        blob = encode(timestamp, values)
        print(len(blob), blob.hex())
        print(decode(blob))

    print("size", struct.calcsize(SAMPLE), struct.calcsize(HALF))
    for number in (0.0, 1.0, -2.5, 0.5, 65504.0, 3.0):
        encoded = struct.pack(HALF, number, 7)
        print(number, encoded.hex(), struct.unpack(HALF, encoded))

    halves = struct.Struct("<3e")
    print(halves.size, halves.unpack(halves.pack(1.0, -0.5, 0.25)))
    print(struct.unpack("<f", struct.pack("<f", 1.0000001)))
    print(struct.unpack("<d", struct.pack("<d", 1.0000000000000002)))

main()

import struct

RECORD = "<iH6s"
records = [
    (3, 120, b"alpha"),
    (5, 80, b"beta"),
    (8, 15, b"gamma"),
]

def build(rows):
    parts = []
    for row in rows:
        parts.append(struct.pack(RECORD, row[0], row[1], row[2]))
    return b"".join(parts)

def main():
    print("record size", struct.calcsize(RECORD))
    blob = build(records)
    print("blob", blob.hex())
    print("iter", list(struct.iter_unpack(RECORD, blob)))

    template = struct.Struct(RECORD)
    total = 0
    names = []
    for amount, weight, raw in template.iter_unpack(blob):
        total += amount * weight
        names.append(raw.rstrip(b"\x00"))
    print("total", total)
    print("names", names)

    for row in records:
        packed = template.pack(row[0], row[1], row[2])
        print(template.unpack(packed))

    print("empty", list(struct.iter_unpack(RECORD, b"")))
    print("calc", struct.calcsize("<2i3s"))

main()

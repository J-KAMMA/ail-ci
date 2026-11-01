import struct

TLV = struct.Struct(">BBH")
CRC = struct.Struct("<H")

def encode(tag, value):
    head = TLV.pack(tag, 0, len(value))
    return head + value + CRC.pack(crc(value))

def crc(data):
    total = 0
    for byte in data:
        total = (total * 31 + byte) & 0xFFFF
    return total

def decode(blob):
    tag, flags, length = TLV.unpack_from(blob, 0)
    start = TLV.size
    body = blob[start:start + length]
    check = CRC.unpack_from(blob, start + length)[0]
    return tag, flags, body, check

def main():
    messages = [
        (1, b"temperature=21.5"),
        (2, b"status=ok"),
        (3, b""),
        (255, b"x" * 40),
    ]
    stream = b""
    heads = b""
    for tag, value in messages:
        packet = encode(tag, value)
        stream += packet
        heads += TLV.pack(tag, 0, len(value))
        print(tag, len(packet), packet.hex(), decode(packet))

    print("stream", len(stream))
    records = struct.iter_unpack(">BBH", heads)
    tags = []
    for tag, flags, length in records:
        tags.append((tag, flags, length))
    print("heads", tags)
    print("sizes", TLV.size, struct.calcsize(">BBH"), struct.calcsize("<H"))

    try:
        TLV.unpack_from(stream, 0)
        CRC.unpack_from(stream, len(stream) - 1)
    except struct.error as exc:
        print("error", str(exc))

    print("crc", crc(b"abc"), CRC.pack(crc(b"abc")).hex())

main()

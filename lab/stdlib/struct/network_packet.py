import struct

HEADER = "!BBHII"
PAYLOAD = "!H"

def frame(kind, flags, sequence, source, target, body):
    head = struct.pack(HEADER, kind, flags, sequence, source, target)
    if body is None:
        return head
    return head + struct.pack(PAYLOAD, len(body)) + body

def parse(data):
    kind, flags, sequence, source, target = struct.unpack(HEADER, data[:struct.calcsize(HEADER)])
    offset = struct.calcsize(HEADER)
    length = struct.unpack_from(PAYLOAD, data, offset)[0]
    offset += struct.calcsize(PAYLOAD)
    body = data[offset:offset + length]
    return kind, flags, sequence, source, target, body

def main():
    print("header", struct.calcsize(HEADER), "payload", struct.calcsize(PAYLOAD))
    packets = [
        frame(1, 0, 7, 0x0A000001, 0x0A000002, b"hello"),
        frame(2, 0x10, 65535, 0, 4294967295, b""),
        frame(3, 0xFF, 256, 0xFFFFFFFF, 1, b"payload"),
    ]
    for packet in packets:
        print(len(packet), packet.hex())
        print(parse(packet))
    empty = frame(4, 0, 0, 0, 0, None)
    print("empty", len(empty), struct.unpack(HEADER, empty))
    print("big-endian", struct.pack("!I", 0x01020304).hex())
    print("little-endian", struct.pack("<I", 0x01020304).hex())

main()

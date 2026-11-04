import binascii


def main() -> None:
    payload = (b"The quick brown fox jumps over the lazy dog. " * 100)[:4219]
    crc = 0
    pos = 0
    while pos < len(payload):
        end = pos + 4096
        if end > len(payload):
            end = len(payload)
        crc = binascii.crc32(payload[pos:end], crc)
        pos = end
    print("%08x" % crc)
    print("%08x" % binascii.crc32(payload))
    print("%08x" % binascii.crc32(b""))
    print(len(payload))


main()

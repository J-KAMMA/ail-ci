from rle_ffi import rle_encode


def decode(data, used):
    out = bytearray()
    index = 0
    while index < used:
        value = data[index]
        count = data[index + 1]
        while count > 0:
            out.append(value)
            count -= 1
        index += 2
    return bytes(out)


def round_trip(data):
    out = bytearray(2 * len(data) + 2)
    used = rle_encode(data, out, len(out))
    print(len(data), used, decode(bytes(out), used) == data)


def main():
    round_trip(b"aaaaabbbccdddddddddd")
    round_trip(b"abc")
    round_trip(b"The quick brown fox jumps over the lazy dog. " * 8)
    small = bytearray(1)
    print(rle_encode(b"aaaaaaaaaa", small, len(small)))


main()

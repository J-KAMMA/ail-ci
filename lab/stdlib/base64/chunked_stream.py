import base64


def make(seed: int, n: int) -> bytes:
    out = bytearray()
    x = seed
    for i in range(n):
        x = (x * 1103515245 + 12345) % 2147483648
        out.append((x >> 16) & 255)
    return bytes(out)


def chunked_encode(data: bytes, step: int) -> bytes:
    out = bytearray()
    i = 0
    while i < len(data):
        out.extend(base64.b64encode(data[i:i + step]))
        i += step
    return bytes(out)


def main() -> None:
    for seed in (1, 7, 99):
        data = make(seed, 1000)
        full = base64.b64encode(data)
        for step in (1, 2, 3, 4, 5, 16, 57, 100):
            encoded = chunked_encode(data, step)
            print(seed, step, encoded == full, base64.b64decode(encoded) == data)
        print(base64.decodebytes(base64.encodebytes(data)) == data)
    print(len(base64.b64encode(make(5, 5000))))
    print(base64.b64encode(make(5, 5000)) == base64.standard_b64encode(make(5, 5000)))


main()

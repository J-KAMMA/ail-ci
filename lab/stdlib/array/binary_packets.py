from array import array


def main():
    values = array('I', [1, 256, 65535])
    raw = values.tobytes()
    print(raw.hex(), len(raw))
    copy = array('I')
    copy.frombytes(raw)
    print(copy, copy == values)
    words = array('d', [1.0, -0.0])
    print(words.tobytes().hex())
    try:
        array('i').frombytes(b'\x01\x02\x03')
    except ValueError as exc:
        print("ValueError", exc)
    try:
        array('i').frombytes(b'\x01\x02\x03\x04\x05')
    except ValueError as exc:
        print("ValueError", exc)
    address, length = values.buffer_info()
    print(length, address > 0)


main()

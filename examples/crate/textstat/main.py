from textstat_ffi import stats


def read_u64(data, start):
    value = 0
    for index in range(8):
        value = value | (data[start + index] << (8 * index))
    return value


def report(data):
    out = bytearray(24)
    try:
        stats(data, out)
    except ValueError as error:
        print("ValueError:", error)
        return
    print(read_u64(bytes(out), 0), read_u64(bytes(out), 8), read_u64(bytes(out), 16))


def main():
    report(b"")
    report(b"one two\nthree\n")
    report("caf\u00e9 \u2713\n\n".encode("utf-8"))
    report(b"bad \xff utf8")


main()

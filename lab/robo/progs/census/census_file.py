"""Census probe: file I/O through the AIL runtime (write_bytes + read_bytes)."""

from ail import read_bytes, write_bytes


def main() -> None:
    write_bytes("census.txt", b"hello sensor\n")
    data = read_bytes("census.txt")
    print("bytes", len(data))
    print("first", data[0])


main()

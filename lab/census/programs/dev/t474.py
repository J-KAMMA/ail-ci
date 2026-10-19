import sys


def main() -> None:
    text: str = sys.stdin.read()
    lines: list[str] = text.split("\n")
    # A trailing newline produces an extra empty element; drop it.
    if lines and lines[-1] == "":
        lines.pop()

    for index, line in enumerate(lines, start=1):
        line = line.rstrip("\r")

        # Encode the line as UTF-8 bytes.
        data: bytes = line.encode("utf-8")

        # Work with a mutable copy as well.
        buf: bytearray = bytearray(data)

        hex_str: str = buf.hex()
        length: int = len(buf)

        # Decode back and verify round-trip equality.
        decoded: str = bytes(buf).decode("utf-8")
        matches: bool = decoded == line and bytes(buf) == data

        print(f"Line {index}:")
        print(f"  bytes:   {data!r}")
        print(f"  hex:     {hex_str}")
        print(f"  length:  {length}")
        print(f"  decoded: {decoded!r}")
        print(f"  equal:   {matches}")


if __name__ == "__main__":
    main()

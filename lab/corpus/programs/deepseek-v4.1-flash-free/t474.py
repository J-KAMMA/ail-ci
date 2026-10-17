import sys
from typing import List


def process_line(line: str) -> str:
    encoded: bytes = line.encode("utf-8")
    buf: bytearray = bytearray(encoded)
    hex_string: str = bytes(buf).hex()
    decoded: str = buf.decode("utf-8")
    roundtrip: bool = decoded == line
    return f"{encoded!r} | {hex_string} | {len(buf)} | {roundtrip}"


def main() -> None:
    data: str = sys.stdin.read()
    lines: List[str] = data.splitlines()
    for line in lines:
        print(process_line(line))


if __name__ == "__main__":
    main()

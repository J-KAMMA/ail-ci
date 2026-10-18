import struct
import sys


def to_bytes_list(x: int) -> list[int]:
    v = abs(x)
    length = (v.bit_length() + 7) // 8
    data = v.to_bytes(length, "big")
    assert int.from_bytes(data, "big") == v
    return list(data)


def main() -> None:
    tokens = sys.stdin.read().split()
    if not tokens:
        return
    n = int(tokens[0])
    nums = [int(t) for t in tokens[1:1 + n]]

    out: list[str] = []
    for x in nums:
        out.append(str(to_bytes_list(x)))
        if abs(x) < 2 ** 32:
            out.append(str(list(struct.pack(">I", abs(x)))))

    sys.stdout.write("\n".join(out) + "\n")


if __name__ == "__main__":
    main()

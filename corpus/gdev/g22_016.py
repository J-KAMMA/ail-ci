# task: Compute the 32-bit FNV-1a hash of a fixed string using XOR and masked multiplication and print the hexadecimal digest.
from typing import Final

FNV_OFFSET_BASIS: Final[int] = 0x811C9DC5
FNV_PRIME: Final[int] = 0x01000193
MASK_32: Final[int] = 0xFFFFFFFF


def fnv1a_32(data: bytes) -> int:
    """Return the 32-bit FNV-1a hash of the given bytes."""
    h: int = FNV_OFFSET_BASIS
    for byte in data:
        h ^= byte
        h = (h * FNV_PRIME) & MASK_32
    return h


def main() -> None:
    message: str = "The quick brown fox jumps over the lazy dog"
    digest: int = fnv1a_32(message.encode("utf-8"))
    print(f"FNV-1a 32-bit digest of {message!r}: {digest:08x}")


if __name__ == "__main__":
    main()

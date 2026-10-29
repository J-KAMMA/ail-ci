# task: Pack four 8-bit R, G, B, and A values into a single 32-bit integer and then unpack them, printing both steps.
from typing import Tuple


def pack_rgba(r: int, g: int, b: int, a: int) -> int:
    """Pack four 8-bit channels into a single 32-bit integer (0xRRGGBBAA)."""
    for name, value in (("r", r), ("g", g), ("b", b), ("a", a)):
        if not 0 <= value <= 0xFF:
            raise ValueError(f"channel {name}={value} is out of the 8-bit range 0..255")
    return (r << 24) | (g << 16) | (b << 8) | a


def unpack_rgba(packed: int) -> Tuple[int, int, int, int]:
    """Unpack a 32-bit integer (0xRRGGBBAA) into four 8-bit channels."""
    if not 0 <= packed <= 0xFFFFFFFF:
        raise ValueError(f"value {packed} does not fit in 32 bits")
    r = (packed >> 24) & 0xFF
    g = (packed >> 16) & 0xFF
    b = (packed >> 8) & 0xFF
    a = packed & 0xFF
    return r, g, b, a


def main() -> None:
    samples: Tuple[Tuple[int, int, int, int], ...] = (
        (255, 128, 64, 32),
        (0, 0, 0, 0),
        (255, 255, 255, 255),
        (18, 52, 86, 120),
    )

    for r, g, b, a in samples:
        print(f"Input channels: R={r} G={g} B={b} A={a}")
        packed = pack_rgba(r, g, b, a)
        print(f"Packed 32-bit value: {packed} (0x{packed:08X}, binary {packed:032b})")
        ur, ug, ub, ua = unpack_rgba(packed)
        print(f"Unpacked channels: R={ur} G={ug} B={ub} A={ua}")
        status = "OK" if (ur, ug, ub, ua) == (r, g, b, a) else "MISMATCH"
        print(f"Round-trip check: {status}")
        print()


if __name__ == "__main__":
    main()

# task: Hash fixed strings into ten buckets with a custom deterministic hash function and print the number of strings in each bucket.
from typing import Sequence


FIXED_STRINGS: tuple[str, ...] = (
    "apple",
    "banana",
    "cherry",
    "date",
    "elderberry",
    "fig",
    "grape",
    "honeydew",
    "kiwi",
    "lemon",
    "mango",
    "nectarine",
    "orange",
    "papaya",
    "quince",
    "raspberry",
    "strawberry",
    "tangerine",
    "ugli",
    "vanilla",
    "watermelon",
    "xigua",
    "yam",
    "zucchini",
    "avocado",
    "blueberry",
    "coconut",
    "dragonfruit",
    "eggplant",
    "feijoa",
    "guava",
    "huckleberry",
    "jackfruit",
    "kumquat",
    "lime",
    "mulberry",
    "olive",
    "peach",
    "plum",
    "rhubarb",
    "salak",
)

NUM_BUCKETS: int = 10
FNV_OFFSET_BASIS: int = 0xCBF29CE484222325
FNV_PRIME: int = 0x100000001B3
MASK_64: int = (1 << 64) - 1


def custom_hash(text: str) -> int:
    """Deterministic 64-bit FNV-1a style hash with an extra mixing step."""
    value: int = FNV_OFFSET_BASIS
    for byte in text.encode("utf-8"):
        value ^= byte
        value = (value * FNV_PRIME) & MASK_64
    # Final avalanche mixing to spread low bits.
    value ^= value >> 33
    value = (value * 0xFF51AFD7ED558CCD) & MASK_64
    value ^= value >> 33
    return value


def bucket_index(text: str, buckets: int = NUM_BUCKETS) -> int:
    """Map a string to a bucket index in the range [0, buckets)."""
    return custom_hash(text) % buckets


def count_buckets(strings: Sequence[str], buckets: int = NUM_BUCKETS) -> list[int]:
    """Count how many strings fall into each bucket."""
    counts: list[int] = [0] * buckets
    for s in strings:
        counts[bucket_index(s, buckets)] += 1
    return counts


def main() -> None:
    counts: list[int] = count_buckets(FIXED_STRINGS, NUM_BUCKETS)
    print(f"Total strings: {len(FIXED_STRINGS)}")
    for index, count in enumerate(counts):
        print(f"Bucket {index}: {count}")


if __name__ == "__main__":
    main()

# task: Encode a dictionary whose keys are integers and show how json converts them to strings when decoded.
import json
from typing import Any


def describe(label: str, value: Any) -> None:
    print(f"{label}: {value!r}")


def main() -> None:
    # Original dictionary with integer keys (insertion order preserved).
    original: dict[int, str] = {
        3: "three",
        -1: "minus one",
        10: "ten",
        0: "zero",
    }
    describe("original keys", list(original.keys()))
    describe("original types", [type(k).__name__ for k in original])

    # Encode to JSON: integer keys become strings in the output text.
    encoded: str = json.dumps(original, sort_keys=True)
    print(f"encoded JSON: {encoded}")

    # Decode back: keys are now strings, not integers.
    decoded: dict[str, str] = json.loads(encoded)
    describe("decoded keys", list(decoded.keys()))
    describe("decoded types", [type(k).__name__ for k in decoded])

    # Show that the lookup by the original integer key fails after round-trip.
    describe("decoded[3] lookup", decoded.get(3))
    describe("decoded['3'] lookup", decoded.get("3"))

    # Restore integer keys explicitly.
    restored: dict[int, str] = {int(k): v for k, v in decoded.items()}
    describe("restored keys", list(restored.keys()))
    describe("restored equals original", restored == original)

    # Sorting keys in JSON is string-based, so "10" sorts before "3".
    unsorted_text: str = json.dumps(original)
    print(f"unsorted JSON: {unsorted_text}")
    describe("string key order after decode", list(json.loads(unsorted_text).keys()))

    # Nested example with a bool-like and a negative key.
    nested: dict[int, dict[int, int]] = {1: {2: 4}, -5: {0: 0}}
    nested_text: str = json.dumps(nested, sort_keys=True)
    print(f"nested JSON: {nested_text}")
    nested_decoded: Any = json.loads(nested_text)
    describe("nested decoded", nested_decoded)


if __name__ == "__main__":
    main()

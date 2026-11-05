# task: Serialize a dictionary containing bytes encoded as base64 strings and print the JSON output.
import base64
import json
from typing import Any


def encode_bytes(value: bytes) -> str:
    """Encode raw bytes as a standard base64 ASCII string."""
    return base64.b64encode(value).decode("ascii")


def decode_bytes(encoded: str) -> bytes:
    """Decode a standard base64 ASCII string back to raw bytes."""
    return base64.b64decode(encoded.encode("ascii"), validate=True)


def prepare_for_json(data: dict[str, Any]) -> dict[str, Any]:
    """Return a copy of the dictionary where bytes values are base64-encoded strings."""
    result: dict[str, Any] = {}
    for key, value in data.items():
        if isinstance(value, bytes):
            result[key] = encode_bytes(value)
        elif isinstance(value, dict):
            result[key] = prepare_for_json(value)
        elif isinstance(value, list):
            result[key] = [
                encode_bytes(item) if isinstance(item, bytes) else item
                for item in value
            ]
        else:
            result[key] = value
    return result


def main() -> None:
    payload: dict[str, Any] = {
        "name": "example",
        "version": 3,
        "checksum": b"\x00\x01\x02\xfe\xff",
        "message": b"Hello, World!",
        "nested": {
            "token": b"secret-token-123",
            "empty": b"",
        },
        "chunks": [b"\xde\xad\xbe\xef", b"\x00\x7f\x80"],
        "enabled": True,
        "ratio": 0.75,
        "tags": ["alpha", "beta"],
    }

    serializable = prepare_for_json(payload)
    output = json.dumps(serializable, indent=2, sort_keys=True)
    print(output)

    # Verify round-trip for the bytes fields.
    restored = json.loads(output)
    assert decode_bytes(restored["message"]) == b"Hello, World!"
    assert decode_bytes(restored["checksum"]) == b"\x00\x01\x02\xfe\xff"
    assert decode_bytes(restored["nested"]["token"]) == b"secret-token-123"


if __name__ == "__main__":
    main()

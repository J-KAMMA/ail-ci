# task: Deserialize a JSON string into a dataclass Person by manually mapping keys to constructor arguments.
import json
from dataclasses import dataclass, field
from typing import Any


@dataclass
class Address:
    street: str
    city: str
    zip_code: str


@dataclass
class Person:
    name: str
    age: int
    email: str | None = None
    tags: list[str] = field(default_factory=list)
    address: Address | None = None


class PersonDecodeError(ValueError):
    """Raised when JSON data cannot be mapped onto a Person."""


def _require(data: dict[str, Any], key: str, expected: type) -> Any:
    if key not in data:
        raise PersonDecodeError(f"missing required key: {key!r}")
    value = data[key]
    if not isinstance(value, expected):
        raise PersonDecodeError(
            f"key {key!r} must be {expected.__name__}, got {type(value).__name__}"
        )
    return value


def _optional(data: dict[str, Any], key: str, expected: type) -> Any | None:
    value = data.get(key)
    if value is None:
        return None
    if not isinstance(value, expected):
        raise PersonDecodeError(
            f"key {key!r} must be {expected.__name__} or null, got {type(value).__name__}"
        )
    return value


def address_from_dict(data: dict[str, Any]) -> Address:
    return Address(
        street=_require(data, "street", str),
        city=_require(data, "city", str),
        zip_code=_require(data, "zip", str),
    )


def person_from_dict(data: dict[str, Any]) -> Person:
    if not isinstance(data, dict):
        raise PersonDecodeError("top-level JSON value must be an object")

    name = _require(data, "name", str)
    age = _require(data, "age", int)
    email = _optional(data, "email", str)

    raw_tags = data.get("tags", [])
    if not isinstance(raw_tags, list) or not all(isinstance(t, str) for t in raw_tags):
        raise PersonDecodeError("key 'tags' must be a list of strings")
    tags = list(raw_tags)

    raw_address = data.get("address")
    address: Address | None = None
    if raw_address is not None:
        if not isinstance(raw_address, dict):
            raise PersonDecodeError("key 'address' must be an object or null")
        address = address_from_dict(raw_address)

    return Person(
        name=name,
        age=age,
        email=email,
        tags=tags,
        address=address,
    )


def deserialize_person(json_text: str) -> Person:
    try:
        data = json.loads(json_text)
    except json.JSONDecodeError as exc:
        raise PersonDecodeError(f"invalid JSON: {exc}") from exc
    return person_from_dict(data)


def main() -> None:
    sample = """
    {
        "name": "Ada Lovelace",
        "age": 36,
        "email": "ada@example.com",
        "tags": ["mathematics", "computing"],
        "address": {
            "street": "12 St James's Square",
            "city": "London",
            "zip": "SW1Y 4JH"
        }
    }
    """

    person = deserialize_person(sample)
    print(person)
    print(f"Name: {person.name}")
    print(f"Age: {person.age}")
    print(f"Email: {person.email}")
    print(f"Tags: {', '.join(person.tags)}")
    if person.address is not None:
        print(f"City: {person.address.city}")

    minimal = deserialize_person('{"name": "Alan Turing", "age": 41}')
    print(minimal)

    try:
        deserialize_person('{"name": "Broken", "age": "unknown"}')
    except PersonDecodeError as exc:
        print(f"Error: {exc}")


if __name__ == "__main__":
    main()

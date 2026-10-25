# task: Validate a list of ages against an allowed range, raising ValueError with a specific message for each invalid entry, and print every validation outcome.
from typing import Union


MIN_AGE = 0
MAX_AGE = 130


def validate_age(value: Union[int, float, str, None], min_age: int = MIN_AGE, max_age: int = MAX_AGE) -> int:
    """Validate a single age value and return it as an int.

    Raises ValueError with a specific message if the value is invalid.
    """
    if value is None:
        raise ValueError("age is missing (None)")
    if isinstance(value, bool):
        raise ValueError(f"age must be an integer, got boolean {value!r}")
    if isinstance(value, str):
        stripped = value.strip()
        if not stripped.lstrip("-").isdigit():
            raise ValueError(f"age must be an integer, got non-numeric string {value!r}")
        number = int(stripped)
    elif isinstance(value, int):
        number = value
    elif isinstance(value, float):
        if not value.is_integer():
            raise ValueError(f"age must be a whole number, got fractional value {value!r}")
        number = int(value)
    else:
        raise ValueError(f"age must be an integer, got unsupported type {type(value).__name__}")

    if number < min_age:
        raise ValueError(f"age {number} is below the minimum of {min_age}")
    if number > max_age:
        raise ValueError(f"age {number} is above the maximum of {max_age}")
    return number


def main() -> None:
    samples: list[Union[int, float, str, None]] = [
        25,
        0,
        130,
        -1,
        131,
        "42",
        " 17 ",
        "abc",
        "-5",
        3.0,
        3.5,
        None,
        True,
        [18],
        "",
    ]

    valid_count = 0
    invalid_count = 0

    for index, value in enumerate(samples, start=1):
        try:
            age = validate_age(value)
        except ValueError as exc:
            invalid_count += 1
            print(f"[{index:02d}] INVALID input={value!r}: {exc}")
        else:
            valid_count += 1
            print(f"[{index:02d}] VALID   input={value!r} -> {age}")

    print(f"Summary: {valid_count} valid, {invalid_count} invalid, "
          f"{len(samples)} total (allowed range {MIN_AGE}-{MAX_AGE})")


if __name__ == "__main__":
    main()

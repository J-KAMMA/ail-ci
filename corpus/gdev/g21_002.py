# task: Encode a Python list containing None, True, and False values to JSON and print the resulting string.
import json


def main() -> None:
    data: list[object] = [None, True, False]
    encoded: str = json.dumps(data)
    print(encoded)


if __name__ == "__main__":
    main()

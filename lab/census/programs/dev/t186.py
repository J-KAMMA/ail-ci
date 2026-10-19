import json
import sys


def main() -> None:
    text: str = sys.stdin.read().strip()
    original: object = json.loads(text)
    dumped: str = json.dumps(original, sort_keys=True, separators=(",", ":"))
    reparsed: object = json.loads(dumped)
    equal: bool = original == reparsed
    print(equal)
    print(dumped)


if __name__ == "__main__":
    main()

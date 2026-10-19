import json
import sys


def main() -> None:
    data = sys.stdin.read()
    obj = json.loads(data)
    result = json.dumps(obj, separators=(",", ":"), ensure_ascii=True)
    sys.stdout.write(result + "\n")


if __name__ == "__main__":
    main()

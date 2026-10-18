import json
import sys


def main() -> None:
    line = sys.stdin.readline()
    data = json.loads(line)
    sys.stdout.write(json.dumps(data, separators=(",", ":"), ensure_ascii=True))
    sys.stdout.write("\n")


if __name__ == "__main__":
    main()

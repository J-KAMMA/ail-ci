import sys


def main() -> None:
    data: str = sys.stdin.buffer.read().decode("utf-8")
    for raw_line in data.split("\n"):
        line: str = raw_line[:-1] if raw_line.endswith("\r") else raw_line
        if line:
            for ch in line:
                print(f"U+{ord(ch):04X} {ch}")
            return


if __name__ == "__main__":
    main()

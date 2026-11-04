import sys


def main() -> None:
    stream = sys.stdin
    line = stream.readline()
    print("got", line.strip())


main()

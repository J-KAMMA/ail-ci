import sys

SIZE = 10 * 1000 * 1000


def main():
    path = sys.argv[1] if len(sys.argv) > 1 else "input.bin"
    block = b"a" * 100000
    with open(path, "wb") as stream:
        left = SIZE
        while left > 0:
            piece = block if left >= len(block) else block[:left]
            stream.write(piece)
            left -= len(piece)
    print(path, SIZE)


main()

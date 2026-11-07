LIMIT = 250000


def main() -> None:
    pieces = []
    for value in range(LIMIT):
        pieces.append(str(value % 10))
    global text
    text = "".join(pieces)
    print(len(text), text[:12], text[-12:])


main()

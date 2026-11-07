LIMIT = 250000


def main() -> None:
    global text
    text = ""
    for value in range(LIMIT):
        text += str(value % 10)
    print(len(text), text[:12], text[-12:])


main()

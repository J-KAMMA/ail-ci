import tomllib


def check(text):
    try:
        tomllib.loads(text)
        return "ok"
    except tomllib.TOMLDecodeError as error:
        return "decode " + str(error)


def main():
    cases = [
        "a = 1\na = 2\n",
        'a = "unclosed\n',
        "a = just-a-value\n",
        "[a]\n[a]\n",
        "a = [1, 2\n",
        "a = {b = 1, b = 2}\n",
        "a = 01\n",
    ]
    for text in cases:
        print(repr(text), check(text))
    print("is valueerror", issubclass(tomllib.TOMLDecodeError, ValueError))


main()

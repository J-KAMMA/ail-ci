import tomllib

DOC = 'x = 99999999999999999999\n'


def main():
    try:
        data = tomllib.loads(DOC)
        print("x", data["x"])
        print("type", type(data["x"]).__name__)
    except Exception as error:
        print("error", type(error).__name__, str(error))


main()

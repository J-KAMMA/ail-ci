import tomllib

DATA = b'''
name = "compiled"
version = "1.2.3"

[deps]
math = "1.0"
json = "2.0"
'''


class BinaryReader:
    def __init__(self, data):
        self.data = data

    def read(self):
        return self.data


class TextReader:
    def read(self):
        return "x = 1\n"


def main():
    data = tomllib.load(BinaryReader(DATA))
    print("name", data["name"])
    print("version", data["version"])
    print("deps", data["deps"]["math"], data["deps"]["json"])
    again = tomllib.load(BinaryReader(DATA))
    print("again", again == data)
    try:
        tomllib.load(TextReader())
    except TypeError as error:
        print("type", str(error))


main()

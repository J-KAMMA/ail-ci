import shlex


def main():
    text = "copy 'a b' \"c d\" plain\\ arg"
    posix = shlex.split(text)
    plain = shlex.split(text, posix=False)
    print("posix", posix)
    print("plain", plain)
    print("lengths", len(posix), len(plain))
    for token in plain:
        if token.startswith("'"):
            print("single", token[1:-1])
        elif token.startswith('"'):
            print("double", token[1:-1])
        else:
            print("bare", token)
    print("joined", shlex.join(posix))
    print("kept", shlex.join(plain))
    print("sizes", [len(token) for token in posix])
    print("first", posix[0], plain[0])
    print("last", posix[len(posix) - 1], plain[len(plain) - 1])


main()

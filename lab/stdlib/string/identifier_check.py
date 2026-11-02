import string

CANDIDATES = ["alpha", "_beta", "gamma1", "1delta", "has space", "class", "", "x-y"]


def valid(name):
    if not name:
        return False
    first = name[0]
    if first not in string.ascii_letters and first != "_":
        return False
    for ch in name[1:]:
        if ch not in string.ascii_letters and ch not in string.digits and ch != "_":
            return False
    return True


def main():
    for name in CANDIDATES:
        print(repr(name), valid(name))
    print("letters", len(string.ascii_letters))
    print("underscore in punctuation?", "_" in string.punctuation)
    print("hex?", all(ch in string.hexdigits for ch in "0123456789abcdefABCDEF"))


main()

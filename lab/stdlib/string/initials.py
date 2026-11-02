import string

PEOPLE = [
    "ada lovelace",
    "Grace Brewster Murray Hopper",
    "  edsger   w   dijkstra ",
    "alan,turing",
    "",
]


def initials(name, sep=None):
    parts = name.split(sep)
    letters = []
    for part in parts:
        part = part.strip(string.whitespace)
        if part:
            letters.append(part[0].upper())
    return "".join(letters)


def main():
    for person in PEOPLE:
        pretty = string.capwords(person)
        print(repr(pretty), initials(pretty))
    print(initials(string.capwords("ada,lovelace", ","), ","))
    print(initials(string.capwords("a,b,c", sep=","), ","))
    print(string.ascii_uppercase)


main()

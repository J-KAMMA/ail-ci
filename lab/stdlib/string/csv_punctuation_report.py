import string

ROWS = [
    "alice,ENGINEER,42",
    "bob, designer ,7",
    "carol,QA, 19 ",
    ",,,",
]


def clean(field):
    return field.strip(string.whitespace)


def main():
    for row in ROWS:
        fields = [clean(part) for part in row.split(",")]
        pretty = [string.capwords(part) for part in fields]
        print("|".join(pretty))
    print(string.punctuation)
    print(repr(string.whitespace))
    print(repr(string.printable[-10:]))


main()

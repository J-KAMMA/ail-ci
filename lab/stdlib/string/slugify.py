import string

TITLES = ["Hello, World!", "  A  Tale of Two Cities ", "", "Café déjà vu", "Python 3.12 rocks"]


def slug(text):
    out = []
    for ch in text.lower():
        if ch in string.ascii_lowercase or ch in string.digits:
            out.append(ch)
        elif ch in string.whitespace or ch in string.punctuation:
            out.append("-")
        else:
            out.append("-")
    raw = "".join(out)
    while "--" in raw:
        raw = raw.replace("--", "-")
    return raw.strip("-")


def main():
    for title in TITLES:
        print(repr(slug(title)), "|", string.capwords(title))
    print(string.capwords("one,two,three", ","))
    print(string.capwords("one two three", sep=" "))


main()

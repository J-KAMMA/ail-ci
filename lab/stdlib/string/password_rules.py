import string

CANDIDATES = ["short", "LongEnough1!", "alllowercase1", "NOLETTERS123!", "", "GoodPass9?"]


def check(pw):
    problems = []
    if len(pw) < 10:
        problems.append("too short")
    if not any(ch in string.ascii_lowercase for ch in pw):
        problems.append("no lowercase")
    if not any(ch in string.ascii_uppercase for ch in pw):
        problems.append("no uppercase")
    if not any(ch in string.digits for ch in pw):
        problems.append("no digit")
    if not any(ch in string.punctuation for ch in pw):
        problems.append("no punctuation")
    return problems


def main():
    for pw in CANDIDATES:
        try:
            problems = check(pw)
            if problems:
                raise ValueError(", ".join(problems))
            print("ok", pw)
        except ValueError as exc:
            print("bad", repr(pw), exc)
    print("printable", len(string.printable), "whitespace", len(string.whitespace))


main()

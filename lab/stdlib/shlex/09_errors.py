import shlex


def check(text, posix):
    try:
        tokens = shlex.split(text, posix=posix)
        return "ok " + str(len(tokens))
    except ValueError as error:
        return "value " + str(error)
    except Exception as error:
        return "other " + str(error)


def main():
    cases = [
        "a 'b c' d",
        "a 'unclosed",
        'a "also unclosed',
        "a\\\\",
        "a \\'b'",
        "",
        "   ",
        "''",
        '""',
    ]
    for text in cases:
        print(repr(text), check(text, True), check(text, False))
    lexer = shlex.shlex("x 'y", "", True)
    try:
        lexer.get_token()
        lexer.get_token()
    except ValueError as error:
        print("lexer", str(error))
    lexer = shlex.shlex("x \\", "", True)
    try:
        lexer.get_token()
        lexer.get_token()
    except ValueError as error:
        print("escape", str(error))


main()

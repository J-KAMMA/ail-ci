import shlex


def main():
    record = "alpha,beta, 'gamma, delta';epsilon"
    lexer = shlex.shlex(record, "", True)
    lexer.whitespace = ",; \t\r\n"
    lexer.whitespace_split = True
    lexer.commenters = ""
    fields = list(lexer)
    print("fields", fields)
    print("count", len(fields))
    for index, field in enumerate(fields):
        print(index, len(field), field)
    lexer = shlex.shlex("key=value # trailing\nnext=two", "", True)
    lexer.whitespace_split = True
    first = lexer.get_token()
    second = lexer.get_token()
    print("comment", first, second)
    lexer = shlex.shlex("a|b|c", "", True)
    lexer.whitespace_split = True
    lexer.commenters = ""
    lexer.quotes = ""
    print("noquotes", list(lexer))
    lexer = shlex.shlex("a\\tb\\nc", "", True)
    lexer.whitespace = "\n"
    lexer.whitespace_split = True
    lexer.commenters = ""
    print("lines", list(lexer))


main()

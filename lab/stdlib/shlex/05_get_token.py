import shlex


def main():
    lexer = shlex.shlex("one two 'three four' five", "", True)
    lexer.whitespace_split = True
    lexer.commenters = ""
    seen = []
    while True:
        token = lexer.get_token()
        if token == lexer.eof:
            break
        seen.append(token)
        print("token", token, lexer.lineno)
    print("seen", seen)
    print("count", len(seen))
    lexer = shlex.shlex("a b c", "", True)
    lexer.whitespace_split = True
    lexer.commenters = ""
    first = lexer.get_token()
    second = lexer.get_token()
    lexer.push_token(first)
    third = lexer.get_token()
    fourth = lexer.get_token()
    print("pushback", third, fourth, lexer.get_token() == lexer.eof)
    print("again", second)


main()

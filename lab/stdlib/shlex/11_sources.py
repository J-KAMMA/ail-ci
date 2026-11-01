import shlex


def main():
    lexer = shlex.shlex("outer one", "outer.sh", True)
    lexer.whitespace_split = True
    lexer.commenters = ""
    print("first", lexer.get_token(), lexer.infile, lexer.lineno)
    lexer.push_source("inner two three", "inner.sh")
    print("pushed", lexer.infile, lexer.lineno)
    print("inner", lexer.get_token(), lexer.lineno)
    print("inner", lexer.get_token(), lexer.lineno)
    lexer.pop_source()
    print("popped", lexer.infile, lexer.lineno)
    print("outer", lexer.get_token(), lexer.lineno)
    print("end", lexer.get_token() == lexer.eof)
    lexer = shlex.shlex("a b", "", True)
    lexer.whitespace_split = True
    lexer.commenters = ""
    print("push", lexer.get_token())
    lexer.push_token("inserted")
    print("order", lexer.get_token(), lexer.get_token())
    print("leader", lexer.error_leader("script.sh", 12))


main()

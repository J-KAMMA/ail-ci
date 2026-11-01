import shlex


def main():
    command = "grep -n 'TODO' src/main.py | head -20"
    lexer = shlex.shlex(command, "pipeline.sh", True)
    lexer.whitespace_split = True
    lexer.commenters = ""
    tokens = list(lexer)
    print("tokens", tokens)
    print("count", len(tokens))
    print("source", lexer.infile)
    print("line", lexer.lineno)
    for index, token in enumerate(tokens):
        if token == "|":
            print("pipe after", index, tokens[index - 1])
        elif token.startswith("-"):
            print("option", token)
        else:
            print("word", index, token)
    second = shlex.shlex("alpha beta gamma", "")
    second.whitespace_split = True
    second.commenters = ""
    total = 0
    for token in second:
        total = total + len(token)
    print("total", total)


main()

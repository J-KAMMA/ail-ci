import shlex


def main():
    command = "ls -l; cat file.txt | grep foo && echo ok || echo bad"
    lexer = shlex.shlex(command, "", True, True)
    lexer.whitespace_split = True
    tokens = list(lexer)
    print("tokens", tokens)
    operators = []
    words = []
    for token in tokens:
        if token == ";" or token == "|" or token == "&&" or token == "||":
            operators.append(token)
        else:
            words.append(token)
    print("operators", operators)
    print("words", words)
    print("counts", len(tokens), len(words), len(operators))
    grouped = shlex.shlex("a&&b||c", "", False, True)
    grouped.whitespace_split = True
    print("grouped", list(grouped))
    custom = shlex.shlex("x:y;z", "", True, ":;")
    custom.whitespace_split = True
    print("custom", list(custom))


main()

import shlex


def classify(token):
    if token == ";":
        return "separator"
    if token == "|":
        return "pipe"
    if token == "&&" or token == "||":
        return "logical"
    if token == ">" or token == "<":
        return "redirect"
    return "word"


def main():
    script = """echo "hello world" | tr 'a-z' 'A-Z' > out.txt
cat out.txt && echo done # finished
printf '%s\\n' one two three
"""
    for number, line in enumerate(script.splitlines(), 1):
        lexer = shlex.shlex(line, "script.sh", True, True)
        lexer.whitespace_split = True
        print(number, list(lexer))
        kinds = []
        for token in lexer:
            kinds.append(classify(token))
        print(number, kinds)
    lexer = shlex.shlex("a\\ b 'c d' \"e f\"", "", True)
    lexer.whitespace_split = True
    lexer.commenters = ""
    tokens = list(lexer)
    print("escaped", tokens)
    print("joined", shlex.join(tokens))


main()

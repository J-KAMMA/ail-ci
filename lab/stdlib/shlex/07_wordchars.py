import shlex


def main():
    line = "build --target=release -j4 src/main.c"
    plain = shlex.shlex(line, "", True)
    plain.whitespace_split = True
    print("plain", list(plain))
    custom = shlex.shlex(line, "", True)
    custom.whitespace_split = True
    custom.wordchars = custom.wordchars + "-"
    tokens = list(custom)
    print("custom", tokens)
    options = []
    values = []
    for token in tokens:
        if token.startswith("--"):
            name, value = token.split("=", 1)
            options.append(name)
            values.append(value)
        elif token.startswith("-"):
            options.append(token)
        else:
            values.append(token)
    print("options", options)
    print("values", values)
    print("count", len(tokens))
    custom = shlex.shlex("alpha-beta gamma", "", True)
    custom.whitespace_split = True
    custom.wordchars = custom.wordchars + "-"
    print("hyphen", list(custom))


main()

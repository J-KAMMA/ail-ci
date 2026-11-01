import shlex


def main():
    line = "python -m http.server --bind 127.0.0.1 --directory '/tmp/my docs'"
    argv = shlex.split(line)
    print("argc", len(argv))
    for arg in argv:
        print("arg", arg)
    rebuilt = shlex.join(argv)
    print("rebuilt", rebuilt)
    print("round trip", shlex.split(rebuilt) == argv)
    print("safe", shlex.quote("simple"))
    print("space", shlex.quote("a b"))
    print("quote", shlex.quote("it's"))
    print("empty", shlex.quote(""))
    try:
        shlex.split("git commit -m 'unfinished")
    except ValueError as error:
        print("error", str(error))
    print("done")


main()

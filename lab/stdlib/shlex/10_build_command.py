import shlex


def build(args):
    return shlex.join(args)


def main():
    cases = [
        ["python3", "-c", "print('hello world')"],
        ["tar", "-czf", "backup file.tar.gz", "src dir"],
        ["echo", "a'b", 'c"d', "plain"],
        ["env", "NAME=value with spaces", "tool"],
        [],
        ["one"],
    ]
    for args in cases:
        command = build(args)
        print("command", command)
        print("again", shlex.split(command) == args)
        print("quote", [shlex.quote(arg) for arg in args])
    single = "echo 'a b' c"
    args = shlex.split(single)
    print("split", args)
    print("join", shlex.join(args))
    print("nested", shlex.split(shlex.join(["sh", "-c", shlex.join(args)])))


main()

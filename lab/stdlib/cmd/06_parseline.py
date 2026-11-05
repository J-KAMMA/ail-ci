import cmd


class ParseShell(cmd.Cmd):
    def do_shell(self, arg):
        print("shell", arg)

    def do_EOF(self, arg):
        return True


def main():
    shell = ParseShell()
    lines = ["?x", "!ls", "  spaced  args  ", "", "plain"]
    for line in lines:
        command, args, text = shell.parseline(line)
        print("parsed", repr(line), repr(command), repr(args), repr(text))


main()

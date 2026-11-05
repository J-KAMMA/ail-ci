import cmd


class DirectShell(cmd.Cmd):
    def do_alpha(self, arg):
        print("alpha", arg)
        return False

    def do_EOF(self, arg):
        print("eof")
        return True

    def default(self, line):
        print("custom default", line)
        return "handled"


def main():
    shell = DirectShell()
    lines = ["alpha 1", "unknown x", "alpha", "EOF"]
    for line in lines:
        result = shell.onecmd(line)
        print("result", result)


main()

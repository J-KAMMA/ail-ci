import cmd


class HookShell(cmd.Cmd):
    prompt = "hook> "

    def preloop(self):
        print("preloop")

    def postloop(self):
        print("postloop")

    def precmd(self, line):
        print("precmd", repr(line))
        return line

    def postcmd(self, stop, line):
        print("postcmd", stop, repr(line))
        return stop

    def do_add(self, arg):
        parts = arg.split()
        total = 0
        for part in parts:
            total = total + int(part)
        print("sum", total)

    def do_EOF(self, arg):
        print("eof")
        return True


def main():
    shell = HookShell()
    shell.cmdloop()


main()

import cmd


class Calculator(cmd.Cmd):
    prompt = "calc> "

    def do_num(self, arg):
        value = int(arg)
        print("value", value)

    def do_add(self, arg):
        parts = arg.split()
        total = 0
        for part in parts:
            total = total + int(part)
        print("total", total)

    def do_EOF(self, arg):
        print("bye")
        return True


def main():
    shell = Calculator()
    shell.cmdloop()


main()

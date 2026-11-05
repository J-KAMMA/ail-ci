import cmd


class EchoShell(cmd.Cmd):
    prompt = "> "

    def do_echo(self, arg):
        print("echo:", arg)

    def do_EOF(self, arg):
        print("done")
        return True


def main():
    shell = EchoShell()
    shell.cmdloop()


main()

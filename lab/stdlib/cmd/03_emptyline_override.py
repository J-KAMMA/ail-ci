import cmd


class QuietShell(cmd.Cmd):
    prompt = "quiet> "
    use_rawinput = False

    def do_ping(self, arg):
        if arg:
            print("ping", arg)
        else:
            print("ping (none)")

    def emptyline(self):
        print("(empty line ignored)")

    def do_EOF(self, arg):
        print("bye")
        return True


def main():
    shell = QuietShell()
    shell.cmdloop()


main()

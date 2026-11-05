import cmd


class AliasShell(cmd.Cmd):
    prompt = "(alias) "

    def help_EOF(self):
        pass

    def help_add(self):
        pass

    def help_alpha(self):
        pass

    def help_count(self):
        pass

    def help_echo(self):
        pass

    def help_greet(self):
        print("greet NAME -- greet someone")

    def help_num(self):
        pass

    def help_ping(self):
        pass

    def help_secret(self):
        pass

    def help_shell(self):
        pass

    def do_EOF(self, arg):
        """Exit."""
        print("bye")
        return True

    def do_add(self, arg):
        """Add numbers."""
        print("add", arg)

    def do_alpha(self, arg):
        """Alpha command."""
        print("alpha", arg)

    def do_count(self, arg):
        """Count things."""
        print("count", arg)

    def do_echo(self, arg):
        """Echo the argument back."""
        print("echo", arg)

    def do_greet(self, arg):
        """Greet someone."""
        print("hello", arg)

    def help_greet(self):
        print("greet NAME -- greet someone")

    def do_num(self, arg):
        """Show a number."""
        print("num", arg)

    def do_ping(self, arg):
        """Ping a host."""
        print("ping", arg)

    def do_secret(self, arg):
        """Secret command."""
        pass

    def do_shell(self, arg):
        """Run a shell command (simulated)."""
        print("shell:", arg)


def main():
    shell = AliasShell()
    shell.cmdqueue.append("?greet")
    shell.cmdqueue.append("!echo hi")
    shell.cmdqueue.append("help")
    shell.cmdqueue.append("EOF")
    shell.cmdloop()


main()

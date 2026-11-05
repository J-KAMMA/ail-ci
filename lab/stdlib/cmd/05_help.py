import cmd


class HelpShell(cmd.Cmd):
    prompt = "(help) "

    def do_EOF(self, arg):
        """Exit the shell."""
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
        print(arg)

    def do_greet(self, arg):
        """Greet someone."""
        print("hello", arg)

    def do_num(self, arg):
        """Show a number."""
        print("num", arg)

    def do_ping(self, arg):
        """Ping a host."""
        print("ping", arg)

    def do_secret(self, arg):
        pass

    def do_shell(self, arg):
        """Run a shell command."""
        print("shell", arg)

    def help_echo(self):
        print("echo TEXT -- custom help")

    def help_secret(self):
        print("secret -- documented only by help_secret")


def main():
    shell = HelpShell()
    shell.onecmd("help")
    shell.onecmd("help echo")
    shell.onecmd("help secret")
    shell.onecmd("help unknown")


main()

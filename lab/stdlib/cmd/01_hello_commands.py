import cmd


class Greeter(cmd.Cmd):
    """A greeting shell."""

    prompt = "(greeter) "
    intro = "Greeter ready"

    def do_greet(self, arg):
        """greet [name] -- greet someone."""
        if arg:
            print("Hello, %s!" % arg)
        else:
            print("Hello, world!")

    def do_EOF(self, arg):
        """Leave the shell."""
        print("Goodbye")
        return True


def main():
    Greeter().cmdloop()


main()

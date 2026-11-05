import cmd


class CountShell(cmd.Cmd):
    prompt = "count> "

    def do_count(self, arg):
        if arg:
            count = int(arg)
        else:
            count = 1
        index = 0
        while index < count:
            print("tick", index)
            index = index + 1

    def do_EOF(self, arg):
        print("end")
        return True


def main():
    shell = CountShell()
    shell.cmdqueue.append("count 2")
    shell.cmdqueue.append("count 3")
    shell.cmdqueue.append("EOF")
    shell.cmdloop()


main()

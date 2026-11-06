import mailcap

FIELD = "cat %s; echo %t; charset %{charset}; 100%%; \\%s; \\\\ and more"


def main():
    print(mailcap.subst(FIELD, "text/plain", "letter.txt",
                        ["charset=utf-8"]))
    print(mailcap.subst(FIELD, "text/plain", "letter.txt"))
    print(mailcap.subst("%{unknown} and %{charset}", "text/plain", "f.txt",
                        ["charset=latin-1"]))
    print(mailcap.subst("no percent at all", "text/plain", "f.txt"))
    print(mailcap.subst("ends with %", "text/plain", "f.txt"))
    print(mailcap.subst("%z and %n", "text/plain", "f.txt"))


main()

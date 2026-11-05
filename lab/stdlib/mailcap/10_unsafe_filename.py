import mailcap
import os

TEXT = """text/plain; cat %s
"""


def main():
    name = "mailcap_10.txt"
    with open(name, "w") as fp:
        fp.write(TEXT)
    os.environ["MAILCAPS"] = name
    caps = mailcap.getcaps()
    command, entry = mailcap.findmatch(caps, "text/plain", "view", "a;rm")
    print("unsafe", command, entry)
    command, entry = mailcap.findmatch(caps, "text/plain", "view", "safe-name.txt")
    print("safe", command, entry["lineno"])
    print("mime", mailcap.subst("cat %t", "text/plain;rm", "f.txt"))
    print("param", mailcap.subst("cat %{charset}", "text/plain", "f.txt",
                                 ["charset=a;rm"]))
    print("safe subst", mailcap.subst("cat %t", "text/plain", "f.txt"))


main()

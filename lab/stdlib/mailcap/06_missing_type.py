import mailcap
import os

TEXT = """text/plain; cat %s
text/plain; less %s; needsterminal
"""


def main():
    name = "mailcap_06.txt"
    with open(name, "w") as fp:
        fp.write(TEXT)
    os.environ["MAILCAPS"] = name
    caps = mailcap.getcaps()
    print("caps", sorted(caps))
    print("missing", mailcap.lookup(caps, "image/png", "view"))
    print("missing bare", mailcap.lookup(caps, "application/pdf"))
    print("present", len(mailcap.lookup(caps, "text/plain", "view")))
    print("no such key", mailcap.lookup(caps, "text/plain", "edit"))
    print("all", len(mailcap.lookup(caps, "text/plain")))


main()

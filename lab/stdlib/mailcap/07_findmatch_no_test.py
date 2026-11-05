import mailcap
import os

TEXT = """text/plain; cat %s
text/plain; less %s; needsterminal
text/*; generic %s
"""


def main():
    name = "mailcap_07.txt"
    with open(name, "w") as fp:
        fp.write(TEXT)
    os.environ["MAILCAPS"] = name
    caps = mailcap.getcaps()
    command, entry = mailcap.findmatch(caps, "text/plain", "view")
    print("command", command)
    print("view", entry["view"])
    print("lineno", entry["lineno"])
    missing, entry2 = mailcap.findmatch(caps, "image/png", "view")
    print("missing", missing, entry2)
    other, entry3 = mailcap.findmatch(caps, "text/xml", "view")
    print("wildcard", other, entry3["lineno"])


main()

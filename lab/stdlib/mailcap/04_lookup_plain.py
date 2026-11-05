import mailcap
import os

TEXT = """text/plain; cat %s
text/html; browser %s
text/plain; less %s
text/plain; more %s; charset=utf-8
"""


def main():
    name = "mailcap_04.txt"
    with open(name, "w") as fp:
        fp.write(TEXT)
    os.environ["MAILCAPS"] = name
    caps = mailcap.getcaps()
    print("caps", sorted(caps))
    entries = mailcap.lookup(caps, "text/plain", "view")
    print("with key", len(entries))
    for entry in entries:
        print(" ", entry["view"], entry["lineno"])
    everything = mailcap.lookup(caps, "text/plain")
    print("no key", len(everything))
    for entry in everything:
        print(" ", entry["view"])


main()

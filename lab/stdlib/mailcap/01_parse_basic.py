import mailcap
import os

TEXT = """# a comment

text/plain; cat %s
application/json; jq . %s; needsterminal; charset=utf-8
text/plain; less %s; x=1; x=2; flag
"""


def show(caps):
    for key in sorted(caps):
        print("type", key)
        for entry in caps[key]:
            for field in sorted(entry):
                print("  %s=%r" % (field, entry[field]))


def main():
    name = "mailcap_01.txt"
    with open(name, "w") as fp:
        fp.write(TEXT)
    os.environ["MAILCAPS"] = name
    caps = mailcap.getcaps()
    show(caps)


main()

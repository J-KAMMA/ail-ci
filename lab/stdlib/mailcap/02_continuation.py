import mailcap
import os

TEXT = """text/plain; cat %s \\
; charset=utf-8
text/html; sed -e s/a/b/ \\
-e s/c/d/ %s; flag
# comment between entries
text/plain; more %s
"""


def show(caps):
    for key in sorted(caps):
        print("type", key)
        for entry in caps[key]:
            for field in sorted(entry):
                print("  %s=%r" % (field, entry[field]))


def main():
    name = "mailcap_02.txt"
    with open(name, "w") as fp:
        fp.write(TEXT)
    os.environ["MAILCAPS"] = name
    show(mailcap.getcaps())


main()

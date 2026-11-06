import mailcap
import os

ONE = """# first file
text/plain; cat %s
image/png; display %s
"""

TWO = """text/plain; less %s
text/plain; more %s
"""


def main():
    with open("mailcap_03a.txt", "w") as fp:
        fp.write(ONE)
    with open("mailcap_03b.txt", "w") as fp:
        fp.write(TWO)
    os.environ["MAILCAPS"] = "mailcap_03a.txt:mailcap_03b.txt"
    caps = mailcap.getcaps()
    for key in sorted(caps):
        print("type", key)
        for entry in caps[key]:
            print("  lineno", entry["lineno"], "view", entry["view"])


main()

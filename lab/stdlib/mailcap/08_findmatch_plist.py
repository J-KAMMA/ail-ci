import mailcap
import os

TEXT = """text/plain; viewer --charset %{charset} %s
text/plain; plain %s; charset=us-ascii
text/*; generic %t %s %{charset}
"""


def main():
    name = "mailcap_08.txt"
    with open(name, "w") as fp:
        fp.write(TEXT)
    os.environ["MAILCAPS"] = name
    caps = mailcap.getcaps()
    command, entry = mailcap.findmatch(caps, "text/plain", "view",
                                       "/tmp/letter.txt", ["charset=utf-8"])
    print("command", command)
    print("lineno", entry["lineno"])
    empty, entry2 = mailcap.findmatch(caps, "text/plain", "view",
                                      "/tmp/letter.txt", [])
    print("empty", empty, entry2["lineno"])
    wild, entry3 = mailcap.findmatch(caps, "text/xml", "view",
                                     "/tmp/letter.txt", ["CHARSET=latin-1"])
    print("wild", wild)
    print("lineno", entry3["lineno"])


main()

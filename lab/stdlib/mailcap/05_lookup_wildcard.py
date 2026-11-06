import mailcap
import os

TEXT = """text/*; generic %s
text/plain; cat %s
image/png; png %s
text/html; html %s
text/*; fallback %s
"""


def main():
    name = "mailcap_05.txt"
    with open(name, "w") as fp:
        fp.write(TEXT)
    os.environ["MAILCAPS"] = name
    caps = mailcap.getcaps()
    for mimetype in ["text/plain", "text/html", "text/xml", "image/png", "image/gif"]:
        entries = mailcap.lookup(caps, mimetype, "view")
        views = []
        for entry in entries:
            views.append(entry["view"])
        print(mimetype, views)


main()

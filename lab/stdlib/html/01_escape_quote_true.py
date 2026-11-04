import html

samples = [
    "<a href=\"x\">Tom & Jerry's</a>",
    "plain text",
    "&&<<>>",
    "'single' and \"double\"",
    "already &amp; escaped",
]

for text in samples:
    print(repr(html.escape(text)))
    print(html.escape(text, quote=True))
    print(len(html.escape(text)))

print(repr(html.escape("")))
print(repr(html.escape("&<>'\"")))

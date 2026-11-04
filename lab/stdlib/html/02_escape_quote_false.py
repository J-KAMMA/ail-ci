import html

rows = [
    "a < b && c > d",
    "\"quoted\"",
    "'apostrophe'",
    "&amp; &lt;",
]

for row in rows:
    print(repr(html.escape(row, quote=False)))
    print(repr(html.escape(row, False)))
    print(repr(html.escape(row, quote=True)))
    print(repr(html.escape(row, True)))

print(repr(html.escape("<tag>", False)))
print(repr(html.escape("&", quote=False)))

from html import escape, unescape

values = [
    "plain",
    "<a href=\"x\">Tom & Jerry's</a>",
    "&amp; already",
    "&#65; numeric",
    "quotes ' and \"",
    "unicode café ☃ € 中文",
    "",
]

for value in values:
    encoded = escape(value)
    decoded = unescape(encoded)
    print(repr(value), decoded == value, repr(encoded))

print(unescape(escape("a < b && c > d")) == "a < b && c > d")
print(repr(unescape(escape("&lt;"))))

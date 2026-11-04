import html

cases = [
    "&#0;", "&#xd800;", "&#x110000;", "&#x110000",
    "&#999999999999999999999999999999;",
    "&#xFFFFFFFFFFFFFFFFFFFFFFFFFFFFFF;",
    "&#x0;", "&#13;", "&#x0d;",
]

for text in cases:
    print(repr(text), repr(html.unescape(text)))

for code in range(0x80, 0xa0):
    text = "&#x%x;" % code
    print(hex(code), repr(html.unescape(text)))

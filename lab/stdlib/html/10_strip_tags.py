import html


def strip_tags(text):
    out = []
    inside = False
    index = 0
    while index < len(text):
        char = text[index]
        if char == "<":
            inside = True
        elif char == ">":
            inside = False
        elif not inside:
            out.append(char)
        index = index + 1
    return html.unescape("".join(out))


document = "<p>Tom &amp; Jerry&nbsp;live</p><b>&lt;tag&gt;</b>"
print(repr(strip_tags(document)))
print(repr(strip_tags("<a title='x'>plain &amp; simple</a>")))
print(repr(strip_tags("no tags &copy; here")))
print(repr(strip_tags("<one><two>deep</two></one>")))

import html

titles = ["Tom & Jerry's", "<b>bold</b>", "no specials"]

print([html.escape(title) for title in titles])
print([html.escape(title, False) for title in titles])

labels = ["tag", "amp", "plain"]
texts = ["<p>", "a & b", "nothing"]
for i in range(len(labels)):
    print(labels[i], repr(html.escape(texts[i])))


def wrap(value: str) -> str:
    return html.escape(value, quote=True)


print(repr(wrap(titles[0])))
print(repr(html.escape(titles[1], quote=False)))
print(len(html.escape(titles[2])))

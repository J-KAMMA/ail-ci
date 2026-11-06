"""Example 3: a word count over a caller-owned text buffer."""

__ail_name__ = "wordcount"
__ail_export__ = ["word_count"]


def word_count(text: str) -> int:
    count = 0
    inword = False
    for ch in text:
        if ch == " " or ch == "\t" or ch == "\n" or ch == "\r":
            inword = False
        else:
            if not inword:
                count += 1
                inword = True
    return count


if __name__ == "__main__":
    for value in ["", "one", "  one two\tthree\nfour  ", "a,b c-d"]:
        print('word_count("%s") = %d' % (value.replace("\t", "\\t").replace("\n", "\\n"), word_count(value)))

"""Example 2: a str-to-str transform through a caller buffer."""

__ail_name__ = "transform"
__ail_export__ = ["transform"]


def transform(text: str) -> str:
    out = ""
    for ch in text:
        if ch >= "a" and ch <= "z":
            out = out + chr(ord(ch) - 32)
        elif ch == " ":
            out = out + "_"
        else:
            out = out + ch
    return out


if __name__ == "__main__":
    for value in ["Hello World 42", "ail embed", "", "already UPPER", "héllo wörld"]:
        print('transform("%s") = "%s"' % (value, transform(value)))

import json

DOC = '["caf\\u00e9", "\\ud83d\\ude00", "line\\nbreak", "tab\\tchar"]'


def main() -> None:
    words: list[str] = json.loads(DOC)
    for word in words:
        print(word, len(word))
    print(json.dumps(words))
    print(json.dumps(words, ensure_ascii=False))
    print(json.dumps(words, ensure_ascii=False, indent=2))
    text = "naïve \"quoted\" \\ path"
    print(json.dumps(text))
    print(json.dumps(text, ensure_ascii=False))
    back: str = json.loads(json.dumps(text))
    print(back == text)


main()

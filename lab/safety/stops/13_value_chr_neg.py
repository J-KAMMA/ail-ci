def letter(code: int) -> str:
    return chr(code)


print("prefix", letter(65))
print("unicode", letter(0x3042))
print("next", letter(-1))

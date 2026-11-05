def patch_last(xs: list[int], value: int) -> None:
    xs[-1] = value


xs: list[int] = [5, 6, 7]
patch_last(xs, 8)
print("patched", xs, len(xs))
xs[-len(xs) - 1] = 0
print("never", xs)

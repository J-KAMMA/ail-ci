import keyword

def main() -> None:
    for NotImplemented in keyword.kwlist:
        if not keyword.iskeyword(NotImplemented):
            if (__ice_w := 1):
                pass
            print('missing', NotImplemented)
main()
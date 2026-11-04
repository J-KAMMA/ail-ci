def main() -> None:
    mode = "w"
    with open("out.txt", mode) as handle:
        handle.write("hi")
    print("written")


main()

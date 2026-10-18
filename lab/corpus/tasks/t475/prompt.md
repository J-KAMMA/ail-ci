Write a complete Python 3.12 program that solves the task below.

Task: Use int.from_bytes and to_bytes on the numbers (abs, big-endian, minimal length) and print the byte lists; also struct.pack('>I') for those under 2**32.

Input (read from standard input): The first line holds n. The second line holds n positive integers (up to 12 digits).

Output: write the result to standard output exactly as described. Print nothing else.

Requirements: standard library only; ordinary readable Python with type hints where natural; define main() and end with
if __name__ == "__main__":
    main()

Reply with the program in a single ```python code block and nothing else.
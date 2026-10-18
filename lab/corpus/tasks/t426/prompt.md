Write a complete Python 3.12 program that solves the task below.

Task: Use a custom exception hierarchy (BaseAppError, ParseError, RangeError) for validating lines: ints must be 1..5; print which error was raised; use finally to count processed lines.

Input (read from standard input): Several lines; each is an integer, a non-numeric word, or empty.

Output: write the result to standard output exactly as described. Print nothing else.

Requirements: standard library only; ordinary readable Python with type hints where natural; define main() and end with
if __name__ == "__main__":
    main()

Reply with the program in a single ```python code block and nothing else.
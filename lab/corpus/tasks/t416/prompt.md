Write a complete Python 3.12 program that solves the task below.

Task: Simulate a text editor with undo: treat each line as 'push X' = type X, 'pop' = undo the last, 'peek' = print the current last char typed or 'none', 'size' prints the number of kept entries; at the end print the concatenation of kept entries.

Input (read from standard input): Several lines of commands: 'push X', 'pop', 'peek', 'size'.

Output: write the result to standard output exactly as described. Print nothing else.

Requirements: standard library only; ordinary readable Python with type hints where natural; define main() and end with
if __name__ == "__main__":
    main()

Reply with the program in a single ```python code block and nothing else.
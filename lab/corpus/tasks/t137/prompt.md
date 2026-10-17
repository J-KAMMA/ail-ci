Write a complete Python 3.12 program that solves the task below.

Task: Implement an undo-able key-value store: after each 'set' or 'del' push a snapshot; 'count' prints the number of keys; 'get' prints the value or 'nil'; 'incr' acts as set; at the end print the final state sorted by key.

Input (read from standard input): Several lines of commands: 'set K V', 'get K', 'del K', 'incr K V', 'count' (keys are single letters, V is an integer).

Output: write the result to standard output exactly as described. Print nothing else.

Requirements: standard library only; ordinary readable Python with type hints where natural; define main() and end with
if __name__ == "__main__":
    main()

Reply with the program in a single ```python code block and nothing else.
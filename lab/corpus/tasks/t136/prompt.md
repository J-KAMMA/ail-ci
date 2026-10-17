Write a complete Python 3.12 program that solves the task below.

Task: Implement an LRU cache of capacity 2 using OrderedDict: 'set K V' inserts or updates, 'get K' prints value or -1 and marks it recently used, 'del K' removes (print nothing), 'incr K V' behaves like set with value V, 'count' prints the current size.

Input (read from standard input): Several lines of commands: 'set K V', 'get K', 'del K', 'incr K V', 'count' (keys are single letters, V is an integer).

Output: write the result to standard output exactly as described. Print nothing else.

Requirements: standard library only; ordinary readable Python with type hints where natural; define main() and end with
if __name__ == "__main__":
    main()

Reply with the program in a single ```python code block and nothing else.
Write a complete Python 3.12 program that solves the task below.

Task: Output a JSON list of {id, name_upper, n_tags} for each record, using json.dumps with default settings.

Input (read from standard input): One line containing a JSON array of objects with keys id, name, tags (list of strings), score (float), active (bool), and sometimes meta (an object with level int and note string or null). Strings may contain escaped characters or non-ASCII text.

Output: write the result to standard output exactly as described. Print nothing else.

Requirements: standard library only; ordinary readable Python with type hints where natural; define main() and end with
if __name__ == "__main__":
    main()

Reply with the program in a single ```python code block and nothing else.
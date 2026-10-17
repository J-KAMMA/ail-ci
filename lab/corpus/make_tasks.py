#!/usr/bin/env python3
"""Write tasks/tNNN/{task.json,prompt.md,in0.txt,in1.txt,in2.txt} from tasks.py (deterministic)."""
import json, random, sys
from pathlib import Path
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import inputs_lib, tasks

PROMPT = """Write a complete Python 3.12 program that solves the task below.

Task: {desc}

Input (read from standard input): {fmt}

Output: write the result to standard output exactly as described. Print nothing else.

Requirements: standard library only; ordinary readable Python with type hints where natural; define main() and end with
if __name__ == "__main__":
    main()

Reply with the program in a single ```python code block and nothing else."""

def main():
    out = HERE / "tasks"
    for i, (cat, desc, gen) in enumerate(tasks.TASKS):
        tid = "t%03d" % i
        d = out / tid
        d.mkdir(parents=True, exist_ok=True)
        fmt = tasks.FORMATS[gen]
        (d / "task.json").write_text(json.dumps({"id": tid, "category": cat, "description": desc, "input_format": gen}, indent=1) + "\n", encoding="utf-8")
        (d / "prompt.md").write_text(PROMPT.format(desc=desc, fmt=fmt), encoding="utf-8")
        for k in range(3):
            rng = random.Random("%s-%d" % (tid, k))
            (d / ("in%d.txt" % k)).write_text(getattr(inputs_lib, gen)(rng, k), encoding="utf-8")
    print(len(tasks.TASKS), "tasks")

main()

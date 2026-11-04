#!/usr/bin/env python3
"""Run compare-lab's run_task.py with this directory as its task root.

    python3 lab/compare_cand/run.py --task csv_rollup --smoke --out /tmp/r.json --langs python

run_task.py binds HERE at import time (`HERE = Path(__file__).resolve().parent`), so it is loaded
as a module and its HERE is rebound to lab/compare_cand before main() runs. REPO and AIL are also
bound at import, but they are computed from the same repository root and stay correct; they are
reassigned here too, together with the toolchains.env symlink lookup in read_pins().
"""
import importlib.util
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
COMPARE = HERE.parent / 'compare'


def load_run_task():
    spec = importlib.util.spec_from_file_location('compare_run_task', COMPARE / 'run_task.py')
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    module.HERE = HERE
    module.REPO = HERE.parents[1]
    module.AIL = module.REPO / 'AIL_CURRENT' / 'ail_chatgpt.py'
    return module


if __name__ == '__main__':
    load_run_task().main()

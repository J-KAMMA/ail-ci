#!/usr/bin/env python3
"""Make the perf input for a task under $1 (default /tmp/layout-input), without re-running a lab.

    python3 lab/layout/mkinput.py berth_sim /tmp/in

The seed and the case are the ones lab/roof, lab/energy and lab/emit use, so a measurement here is
on the same bytes as those labs' numbers.
"""
import importlib.util
import random
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]


def main():
    task = sys.argv[1]
    out = Path(sys.argv[2] if len(sys.argv) > 2 else '/tmp/layout-input')
    out.mkdir(parents=True, exist_ok=True)
    spec = importlib.util.spec_from_file_location('g' + task,
                                                  REPO / 'lab' / 'compare' / 'tasks' / task / 'gen.py')
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    _pub, _hid, perf = m.cases(random.Random('%s-20261012' % task))
    name, data, args = perf
    path = out / (task + '.bin')
    path.write_bytes(data)
    print('%s %s %d bytes args=%s stdin=%s -> %s' % (task, name, len(data), args,
                                                     bool(getattr(m, 'STDIN', False)), path))


if __name__ == '__main__':
    main()

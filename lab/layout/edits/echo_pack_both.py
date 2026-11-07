#!/usr/bin/env python3
"""Hand edit (not a compiler change): echo_pack's `prev` chain plus an unconditional store.

    python3 lab/layout/edits/echo_pack_both.py in/program.c out/program.c

Both echo_pack causes in one file: the int32 element width (`echo_pack_prev32.py`) and the
single-probe unconditional store (`echo_pack_uncond.py`).

Measured: 4.13M LLC removed, i.e. about the same as either edit alone, not their sum. The two
touch the same `prev` array, and `prev32`'s replacement initialisation re-introduces an int32
fill that cancels `uncond`'s saving; RESULTS.md records the overlap.
"""
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent


def main():
    src, dst = sys.argv[1], sys.argv[2]
    tmp = Path(dst + '.step1')
    for script in ('echo_pack_uncond.py', 'echo_pack_prev32.py'):
        subprocess.run([sys.executable, str(HERE / script), src, str(tmp)], check=True)
        src = str(tmp)
    Path(dst).write_bytes(Path(src).read_bytes())
    tmp.unlink(missing_ok=True)


if __name__ == '__main__':
    main()

#!/usr/bin/env python3
"""Hand edit (not a compiler change): echo_pack's `prev` chain plus an unconditional store.

    python3 lab/layout/edits/echo_pack_both.py in/program.c out/program.c

Both echo_pack causes in one file, to show the saving is additive: the int32 element width
(`echo_pack_prev32.py`) and the single-probe unconditional store (`echo_pack_uncond.py`).
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

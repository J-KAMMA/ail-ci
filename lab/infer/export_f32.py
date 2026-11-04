#!/usr/bin/env python3
"""Write one little-endian f32 file per GGUF tensor, plus manifest.txt.

Usage: python3 export_f32.py MODEL.gguf OUT_DIR

The GGUF reader already presents each tensor in the PyTorch orientation
(out_features, in_features), with ne0 (in_features) contiguous.  Writing the
array with numpy's native C order therefore gives the layout the reference and
the AIL program index as W[out, in].
"""
import sys
from pathlib import Path

import numpy as np
import gguf


def main() -> int:
    if len(sys.argv) != 3:
        print("usage: export_f32.py MODEL.gguf OUT_DIR", file=sys.stderr)
        return 2
    src = Path(sys.argv[1])
    out = Path(sys.argv[2])
    out.mkdir(parents=True, exist_ok=True)
    reader = gguf.GGUFReader(str(src))
    lines = []
    for tensor in reader.tensors:
        data = np.asarray(tensor.data)
        if data.dtype != np.float32:
            data = data.astype(np.float32)
        name = tensor.name
        data.astype("<f4").tofile(out / (name + ".f32"))
        shape = " ".join(str(n) for n in data.shape)
        lines.append("%s\t%s\t%s.f32" % (name, shape, name))
    (out / "manifest.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("wrote %d tensors to %s" % (len(lines), out))
    return 0


if __name__ == "__main__":
    sys.exit(main())

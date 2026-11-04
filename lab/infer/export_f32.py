#!/usr/bin/env python3
"""Write one little-endian f32 file per GGUF tensor, plus manifest.txt.

Usage: python3 export_f32.py MODEL.gguf OUT_DIR

The GGUF reader already presents each tensor in the PyTorch orientation
(out_features, in_features), with ne0 (in_features) contiguous.  Writing the
array with numpy's native C order therefore gives the layout the reference and
the AIL program index as W[out, in].

Quantized tensors are refused by name: their reader data is the raw block
bytes, and casting those to f32 would silently write wrong weights.  Convert
the GGUF to F32 (or F16) first.
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
        name = tensor.name
        kind = getattr(tensor, "tensor_type", None)
        if kind is not None:
            kind_name = getattr(kind, "name", None)
            if not isinstance(kind_name, str):
                kind_name = str(kind).rsplit(".", 1)[-1]
            if kind_name not in ("F32", "F16"):
                print("refused: tensor %s is %s, not an unquantized float type; "
                      "convert the GGUF to F32 first (llama-quantize ... F32)"
                      % (name, kind_name), file=sys.stderr)
                return 2
        data = np.asarray(tensor.data)
        if not np.issubdtype(data.dtype, np.floating):
            print("refused: tensor %s has dtype %s, not a floating type; "
                  "convert the GGUF to F32 first (llama-quantize ... F32)"
                  % (name, data.dtype), file=sys.stderr)
            return 2
        if data.dtype != np.float32:
            data = data.astype(np.float32)
        data.astype("<f4").tofile(out / (name + ".f32"))
        shape = " ".join(str(n) for n in data.shape)
        lines.append("%s\t%s\t%s.f32" % (name, shape, name))
    (out / "manifest.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("wrote %d tensors to %s" % (len(lines), out))
    return 0


if __name__ == "__main__":
    sys.exit(main())

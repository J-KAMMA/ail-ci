#!/usr/bin/env python3
"""Command-line wrapper for lab/infer/bpe.py.

`bpe.py` is the AIL program and module; this wrapper makes the same CLI
available to CPython without copying the tokenizer (set no environment: it
inserts this directory into `sys.path`).  AIL builds use `bpe.py` itself:

    python3 -B AIL_CURRENT/ail_chatgpt.py compile lab/infer/bpe.py -o /tmp/bpe
    /tmp/bpe encode VOCAB_DIR TEXT_FILE
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import bpe  # noqa: E402

if __name__ == "__main__":
    sys.exit(bpe.main())

#!/usr/bin/env python3
"""Write oracle token ids for every line of a corpus.

    python3 lab/infer/tok_oracle.py --gpt2 DIR --corpus FILE --out FILE
    python3 lab/infer/tok_oracle.py --zenz MODEL.gguf LLAMA-TOKENIZE --corpus FILE --out FILE
    python3 lab/infer/tok_oracle.py --tiny

--gpt2 uses Hugging Face `tokenizers` (pinned in TOKENIZER.md); DIR holds
vocab.json and merges.txt from tok_fetch.sh.  --zenz calls the pinned fork's
llama-tokenize once per line with --ids --no-bos and parses its [id, ...]
output.  --tiny retrains the committed 512-merge case in
AIL_CURRENT/bpe_cases/tiny from lab/infer/tok_corpus.txt.

Output is JSON: one list of ids per corpus line.
"""
import argparse
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CORPUS = ROOT / "lab/infer/tok_corpus.txt"
TINY = ROOT / "AIL_CURRENT/bpe_cases/tiny"


def load_local(directory):
    from tokenizers import Tokenizer
    from tokenizers.models import BPE
    from tokenizers.pre_tokenizers import ByteLevel

    vocab = json.loads((Path(directory) / "vocab.json").read_text(encoding="utf-8"))
    merges = []
    for line in (Path(directory) / "merges.txt").read_text(encoding="utf-8").splitlines():
        if line and not line.startswith("#"):
            left, right = line.split(" ", 1)
            merges.append((left, right))
    tokenizer = Tokenizer(BPE(vocab=vocab, merges=merges))
    tokenizer.pre_tokenizer = ByteLevel(add_prefix_space=False, use_regex=True)
    return tokenizer


def tokenizers_ids(directory, lines):
    import tokenizers

    print("tokenizers %s" % tokenizers.__version__, file=sys.stderr)
    tokenizer = load_local(directory)
    return [tokenizer.encode(line, add_special_tokens=False).ids for line in lines]


def llama_ids(model, executable, lines):
    rows = []
    for line in lines:
        result = subprocess.run(
            [executable, "-m", model, "-p", line, "--ids", "--no-bos",
             "--no-escape", "--no-parse-special", "--log-disable"],
            capture_output=True, text=True)
        if result.returncode != 0:
            raise SystemExit("llama-tokenize failed: " + result.stderr[-2000:])
        text = result.stdout.strip()
        start = text.find("[")
        end = text.rfind("]")
        if start < 0 or end < start:
            raise SystemExit("unexpected llama-tokenize output: " + text[:200])
        rows.append([int(x) for x in text[start + 1:end].replace(",", " ").split()])
    return rows


def tiny():
    from tokenizers import Tokenizer
    from tokenizers.models import BPE
    from tokenizers.pre_tokenizers import ByteLevel
    from tokenizers.trainers import BpeTrainer

    lines = CORPUS.read_text(encoding="utf-8").splitlines()
    tokenizer = Tokenizer(BPE())
    tokenizer.pre_tokenizer = ByteLevel(add_prefix_space=False, use_regex=True)
    trainer = BpeTrainer(vocab_size=768, initial_alphabet=ByteLevel.alphabet(),
                         show_progress=False)
    tokenizer.train_from_iterator(lines, trainer=trainer)
    TINY.mkdir(parents=True, exist_ok=True)
    tokenizer.model.save(str(TINY))
    ids = [tokenizer.encode(line, add_special_tokens=False).ids for line in lines]
    (TINY / "expected_ids.json").write_text(json.dumps(ids, ensure_ascii=False) + "\n",
                                           encoding="utf-8")
    print("wrote %s (%d merges, %d lines)" % (TINY, len(tokenizer.get_vocab()) - 256, len(lines)))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--gpt2")
    parser.add_argument("--zenz", nargs=2, metavar=("MODEL", "LLAMA_TOKENIZE"))
    parser.add_argument("--tiny", action="store_true")
    parser.add_argument("--corpus", default=str(CORPUS))
    parser.add_argument("--out")
    args = parser.parse_args()
    if args.tiny:
        tiny()
        return 0
    lines = Path(args.corpus).read_text(encoding="utf-8").splitlines()
    if args.gpt2:
        rows = tokenizers_ids(args.gpt2, lines)
    elif args.zenz:
        rows = llama_ids(args.zenz[0], args.zenz[1], lines)
    else:
        parser.error("give --gpt2 DIR, --zenz MODEL EXE, or --tiny")
    if not args.out:
        parser.error("--out FILE is required")
    Path(args.out).write_text(json.dumps(rows, ensure_ascii=False) + "\n", encoding="utf-8")
    print("wrote %d id lists to %s" % (len(rows), args.out))
    return 0


if __name__ == "__main__":
    sys.exit(main())

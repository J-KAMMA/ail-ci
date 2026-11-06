#!/usr/bin/env bash
# B6 tokenizer benchmark: GPT-2 BPE tokens per second, AIL against Hugging
# Face `tokenizers`, one thread, median of 5.  Also peak RSS and binary size.
#
#   bash lab/infer/tok_bench.sh [GPT2_DIR] [DEST]
#
# GPT2_DIR defaults to ${RUNNER_TEMP:-/tmp}/ail-tok/gpt2 (tok_fetch.sh).
# The corpus is lab/infer/tok_corpus.txt repeated to about 5 MB.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
GPT2="${1:-${RUNNER_TEMP:-/tmp}/ail-tok/gpt2}"
DEST="${2:-${RUNNER_TEMP:-/tmp}/ail-tok}"
CORPUS="$ROOT/lab/infer/tok_corpus.txt"
BENCH="$DEST/tok_bench_corpus.txt"
BIN="$DEST/bpe-ail"
mkdir -p "$DEST"

if [ ! -f "$GPT2/vocab.json" ] || [ ! -f "$GPT2/merges.txt" ]; then
    echo "missing $GPT2/vocab.json or merges.txt; run lab/infer/tok_fetch.sh" >&2
    exit 2
fi

python3 - "$CORPUS" "$BENCH" <<'PY'
import sys
from pathlib import Path
lines = Path(sys.argv[1]).read_text(encoding="utf-8").splitlines()
out = []
size = 0
while size < 5_000_000:
    for line in lines:
        out.append(line)
        size += len(line.encode("utf-8")) + 1
        if size >= 5_000_000:
            break
Path(sys.argv[2]).write_text("\n".join(out) + "\n", encoding="utf-8")
print("bench corpus: %d lines, %d bytes" % (len(out), size))
PY

rm -f "$BIN"
python3 -B "$ROOT/AIL_CURRENT/ail_chatgpt.py" compile "$ROOT/lab/infer/bpe.py" -o "$BIN" >/dev/null
SIZE=$(stat -c %s "$BIN")

cat > "$DEST/bench_tokenizers.py" <<'PY'
import json
import sys
import time
from pathlib import Path
from tokenizers import Tokenizer
from tokenizers.models import BPE
from tokenizers.pre_tokenizers import ByteLevel

directory, corpus = sys.argv[1], sys.argv[2]
vocab = json.loads((Path(directory) / "vocab.json").read_text(encoding="utf-8"))
merges = []
for line in (Path(directory) / "merges.txt").read_text(encoding="utf-8").splitlines():
    if line and not line.startswith("#"):
        left, right = line.split(" ", 1)
        merges.append((left, right))
tok = Tokenizer(BPE(vocab=vocab, merges=merges))
tok.pre_tokenizer = ByteLevel(add_prefix_space=False, use_regex=True)
lines = Path(corpus).read_text(encoding="utf-8").splitlines()
start = time.perf_counter()
total = 0
for line in lines:
    total += len(tok.encode(line, add_special_tokens=False).ids)
print("%.6f %d" % (time.perf_counter() - start, total))
PY

export OMP_NUM_THREADS=1
export RAYON_NUM_THREADS=1
export TOKENIZERS_PARALLELISM=false
ulimit -v 1500000

echo "run,ail_seconds,ail_rss_kb,py_seconds,py_rss_kb" > "$DEST/bench_raw.csv"
for run in 1 2 3 4 5; do
    /usr/bin/time -f "%e %M" -o "$DEST/ail_time.txt" "$BIN" encode "$GPT2" "$BENCH" > "$DEST/ail_ids.txt"
    read -r asec arss < "$DEST/ail_time.txt"
    /usr/bin/time -f "%e %M" -o "$DEST/py_time.txt" \
        python3 "$DEST/bench_tokenizers.py" "$GPT2" "$BENCH" > "$DEST/py_out.txt"
    read -r psec _ < "$DEST/py_time.txt"
    prss=$(awk '/Maximum resident/ {print $6}' "$DEST/py_time.txt" 2>/dev/null || true)
    if [ -z "${prss:-}" ]; then prss=0; fi
    echo "$run,$asec,$arss,$psec,0" | tee -a "$DEST/bench_raw.csv"
done

TOKENS=$(awk '{n += NF} END {print n}' "$DEST/ail_ids.txt")
python3 - "$DEST/bench_raw.csv" "$TOKENS" "$SIZE" <<'PY'
import csv
import statistics
import sys

rows = list(csv.DictReader(open(sys.argv[1])))
tokens = int(sys.argv[2])
size = int(sys.argv[3])
a = [float(r["ail_seconds"]) for r in rows]
p = [float(r["py_seconds"]) for r in rows]
rss = [int(r["ail_rss_kb"]) for r in rows]
ma, mp = statistics.median(a), statistics.median(p)
print()
print("tokens: %d" % tokens)
print("| implementation | median s | tokens/s | peak RSS | binary |")
print("| --- | ---: | ---: | ---: | ---: |")
print("| AIL `bpe.py` | %.3f | %.0f | %.1f MB | %d KB |" % (ma, tokens / ma, max(rss) / 1024.0, size // 1024))
print("| HF `tokenizers` | %.3f | %.0f | - | - |" % (mp, tokens / mp))
print("ratio AIL/tokenizers: %.2fx" % (ma / mp))
PY

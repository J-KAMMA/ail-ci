#!/bin/bash
# pipeline.sh: the whole job on a GitHub runner, like pipe.ps1 does in the sandbox:
#   worker -> reviewer -> one fix round -> reviewer, all with the OpenCode CLI (DeepSeek V4.1 Flash).
# Runs in the job checkout; the task is .agent/task.md, the review prompt .agent/review.md.
# Writes .agent/pipeline.md (the same sections as agents/pipe/<project>/<job>.txt) ending in "FINAL VERDICT: X".
# OpenCode's auth file must already be in $HOME; this script never sees the key.
set -u
OC="$HOME/opt/opencode/opencode"
log=.agent/pipeline.md
git branch -f work HEAD            # the reviewer diffs work..HEAD, as in the sandbox
echo "# job $(git rev-parse --abbrev-ref HEAD)  started $(date -u +%FT%TZ)  worker=oc reviewer=oc (GitHub)" > "$log"

# the same key also serves OpenCode Zen's free models: add that provider entry to the auth file (nothing is printed)
python3 - <<'EOF'
import json, os
p = os.path.expanduser('~/.local/share/opencode/auth.json')
a = json.load(open(p)); a['opencode'] = a['opencode-go']; json.dump(a, open(p, 'w'))
EOF
# $RUNNER_TEMP/free_out exists once the free quota is used up: the rest of this job uses the paid model (a file, because run_oc runs in a subshell)
# Qoder CLI: DeepSeek V4.1 Flash costs 0 credits there until 2026-11-01 00:00 UTC+8 (owner, 2026-10-24). Public code
# only (this repo is public). Tried first while the window is open and a token file exists; OpenCode otherwise.
QMODEL=""
qoder_setup() {
  [ -f "$RUNNER_TEMP/qoder.key" ] || return 1
  [ "$(date -u +%s)" -lt "$(date -u -d '2026-10-31T16:00:00Z' +%s)" ] || return 1
  [ -f "$RUNNER_TEMP/qoder.off" ] && return 1
  if [ -z "$QMODEL" ] && [ -f "$RUNNER_TEMP/qoder.model" ]; then QMODEL=$(cat "$RUNNER_TEMP/qoder.model"); fi
  [ -n "$QMODEL" ] && return 0
  command -v qodercli >/dev/null || command -v qoder >/dev/null || npm install -g @qoder-ai/qodercli@1.1.78 >/dev/null 2>&1
  QBIN=$(command -v qodercli || command -v qoder) || { touch "$RUNNER_TEMP/qoder.off"; return 1; }
  echo "$QBIN" > "$RUNNER_TEMP/qoder.bin"
  { echo "## qoder discovery"; "$QBIN" --version 2>&1 | head -2; "$QBIN" --help 2>&1 | grep -i -A3 'model' | head -12; } >> "$log"
  lm=$(QODER_PERSONAL_ACCESS_TOKEN=$(cat "$RUNNER_TEMP/qoder.key") timeout 120 "$QBIN" --list-models 2>&1)
  { echo "### --list-models"; printf '%s
' "$lm" | head -40; } >> "$log"
  cands=$(printf '%s
' "$lm" | grep -io '[A-Za-z0-9._-]*deepseek[A-Za-z0-9._-]*' | grep -i flash | sort -u)   # never DeepSeek V4 Pro (owner)
  for m in $cands DeepSeek-Flash; do
    out=$(QODER_PERSONAL_ACCESS_TOKEN=$(cat "$RUNNER_TEMP/qoder.key") timeout 120 "$QBIN" -p -o json --model "$m" "Reply with the single word: pong" 2>&1)
    printf '%s -> %s\n' "$m" "$(printf '%s' "$out" | tr '\n' ' ' | tail -c 600)" >> "$log"   # the tail holds the error text (the head is only usage counters)
    if printf '%s' "$out" | grep -qi pong; then QMODEL=$m; echo "$m" > "$RUNNER_TEMP/qoder.model"; return 0; fi
  done
  touch "$RUNNER_TEMP/qoder.off"; return 1
}
run_qoder() {  # $1 prompt file, $2 tag, $3 minutes -> final text on stdout; returns 1 if Qoder could not run
  qoder_setup || return 1
  local QBIN; QBIN=$(cat "$RUNNER_TEMP/qoder.bin")
  QODER_PERSONAL_ACCESS_TOKEN=$(cat "$RUNNER_TEMP/qoder.key") timeout "${3}m" "$QBIN" -p -o json --yolo --max-turns 250 \
    -w "$PWD" --model "$QMODEL" --attachment "$1" \
    "Do the task described in the attached file, in this directory. When finished, reply with a short final report." \
    > "$RUNNER_TEMP/$2.qoder.json" 2> "$RUNNER_TEMP/$2.qoder.err"
  local rc=$?
  if grep -qiE 'credit|quota|insufficient|unauthori|forbidden|rate limit' "$RUNNER_TEMP/$2.qoder.err" "$RUNNER_TEMP/$2.qoder.json" 2>/dev/null && [ ! -s "$RUNNER_TEMP/$2.qoder.json" ]; then
    touch "$RUNNER_TEMP/qoder.off"; return 1
  fi
  echo "[model qoder/$QMODEL]"
  python3 - "$RUNNER_TEMP/$2.qoder.json" <<'PY'
import json, sys
raw = open(sys.argv[1], encoding='utf-8', errors='replace').read()
text = ''
try:
    d = json.loads(raw)
    text = d.get('result') or d.get('text') or d.get('content') or ''
    if isinstance(text, list): text = ' '.join(str(x) for x in text)
except ValueError:
    text = raw[-4000:]
print(text or raw[-4000:] or '(no final text)')
PY
  [ $rc = 124 ] && echo "(cut off after $3 minutes)"
  return 0
}
wait_offpeak() {  # paid DeepSeek costs double Mon-Fri 01-04 and 06-10 UTC (OpenCode Go and Command Code alike):
  # before a paid model, wait for the window to end (owner, 2026-10-26: GitHub too, not only the local runner)
  local h d
  while :; do
    h=$(date -u +%-H); d=$(date -u +%u)
    if [ "$d" -le 5 ] && { [ "$h" -ge 1 ] && [ "$h" -lt 4 ] || [ "$h" -ge 6 ] && [ "$h" -lt 10 ]; }; then
      echo "(peak hours: waiting before the paid model)" >&2; sleep 600
    else return 0; fi
  done
}
run_cc() {  # $1 prompt file, $2 tag, $3 minutes -> final text on stdout; returns 1 if Command Code could not run
  wait_offpeak
  # Command Code CLI (GOAT plan, owner 2026-10-26), pinned; the key lives only in this process's environment
  [ -x "$RUNNER_TEMP/cc/node_modules/.bin/cmd" ] || npm install --prefix "$RUNNER_TEMP/cc" --no-fund --no-audit command-code@1.88.0 >/dev/null 2>&1 || return 1
  COMMAND_CODE_API_KEY=$(cat "$RUNNER_TEMP/cc.key") timeout "${3}m" "$RUNNER_TEMP/cc/node_modules/.bin/cmd" -p --model deepseek-v4.1-flash \
    --yolo -t --max-turns 250 --output-format json \
    < <(printf 'Do the task described below, in this directory. When finished, reply with a short final report.\n\n'; cat "$1") \
    > "$RUNNER_TEMP/$2.cc.json" 2> "$RUNNER_TEMP/$2.cc.err"
  echo "[model commandcode/deepseek-v4.1-flash]"
  python3 - "$RUNNER_TEMP/$2.cc.json" <<'PY'
import json, sys
final = None
for line in open(sys.argv[1], encoding='utf-8', errors='replace'):
    try:
        e = json.loads(line)
    except ValueError:
        continue
    if isinstance(e, dict) and (e.get('type') == 'result' or 'result' in e):
        # the last line is {"type": "result", ..., "finalText": "..."} (command-code 1.88.0)
        final = e.get('finalText') or final
print(final or '(no final text)')
PY
  grep -qs '"result"' "$RUNNER_TEMP/$2.cc.json"
}
run_oc() {  # $1 prompt file, $2 tag, $3 minutes -> final text on stdout
  # The free Zen build of the model first (zero retention, not used for training); the paid Go model when it fails.
  # When the free quota is used up OpenCode does not exit, it retries silently (2026-10-24), so a watchdog reads
  # OpenCode's own log and switches at once.
  local rc model mins pid quota cc_tried=0
  run_qoder "$1" "$2" "$3" && return 0
  for model in opencode/deepseek-v4.1-flash-free opencode-go/deepseek-v4.1-flash; do
    [ "$model" = opencode/deepseek-v4.1-flash-free ] && [ -f "$RUNNER_TEMP/free_out" ] && continue
    [ "$model" = opencode-go/deepseek-v4.1-flash ] && wait_offpeak
    # the paid stage tries Command Code first (owner, 2026-10-27: OpenCode Go had used half its month, Command Code
    # nothing); OpenCode Go is the fallback. CC_FIRST_HOURS=odd|even|all picks when (all for now)
    if [ "$model" = opencode-go/deepseek-v4.1-flash ] && [ -s "$RUNNER_TEMP/cc.key" ] &&        case "${CC_FIRST_HOURS:-all}" in all) true;; even) [ $(( $(date -u +%-H) % 2 )) = 0 ];; *) [ $(( $(date -u +%-H) % 2 )) = 1 ];; esac; then
      cc_tried=1; run_cc "$1" "$2" "$3" && return 0
    fi
    mins=$3; quota=0
    rm -rf "$HOME/.local/share/opencode/log"
    timeout "${mins}m" "$OC" run --format json --dir "$PWD" -m "$model" "Do the task described in the attached file, in this directory. When finished, reply with a short final report." -f "$1" > "$RUNNER_TEMP/$2.jsonl" 2> "$RUNNER_TEMP/$2.err" &
    pid=$!
    while kill -0 $pid 2>/dev/null; do
      sleep 20
      if [ "$model" = opencode/deepseek-v4.1-flash-free ] && grep -qs "Free usage limit reached\|Model access is disabled" "$HOME"/.local/share/opencode/log/*; then
        quota=1; touch "$RUNNER_TEMP/free_out"; pkill -P $pid 2>/dev/null; kill $pid 2>/dev/null; break
      fi
    done
    wait $pid; rc=$?
    [ $quota = 1 ] && { echo "(free quota used up; paid model from here)"; continue; }
    [ "$model" != opencode/deepseek-v4.1-flash-free ] && break
    grep -qiE '"type": ?"error".*(rate|limit|quota|429|503|free)' "$RUNNER_TEMP/$2.jsonl" || break
  done
  # OpenCode gave nothing (its week used up, 2026-10-26): the same model through the Command Code GOAT plan
  if [ $cc_tried = 0 ] && [ -s "$RUNNER_TEMP/cc.key" ] && ! grep -qs '"type": *"text"' "$RUNNER_TEMP/$2.jsonl"; then
    run_cc "$1" "$2" "$3" && return 0
  fi
  echo "[model $model]"
  python3 .agent/oc_report.py "$RUNNER_TEMP/$2.jsonl"
  python3 .agent/oc_steps.py "$RUNNER_TEMP/$2.jsonl" 2>/dev/null | sed "s/^/    /"
  [ $rc = 124 ] && echo "(cut off after $mins minutes)"
  return 0
}
commit_leftovers() {  # an agent's uncommitted edits still count as its work
  git add -A -- . ':(exclude).agent' ':(exclude)corpus'
  git diff --cached --quiet || git commit -q -m "$1: uncommitted edits"
}

rules=$(cat .agent/rules.txt 2>/dev/null)
# time boxes (minutes) for the worker, each review and the fix round. The bigint fix jobs are large: with 100/60/60
# nearly all of them were cut off mid-work and judged FIX (2026-10-26), so they get a longer first pass and the time
# left decides whether a second review still fits. They also skip the full suite here: their base (the bigint export)
# fails ~70 modules until all fixes are in, and the merged result runs the full suite in the private repo.
W0=100; RV=60; W1=60; SUITE=1; T_END=$(( $(date +%s) + 320 * 60 ))
case "$(git rev-parse --abbrev-ref HEAD)" in job-bigint-*) W0=170; RV=50; W1=70; SUITE=0;; esac
left() { echo $(( (T_END - $(date +%s)) / 60 )); }
cat .agent/task.md > "$RUNNER_TEMP/work0.md"
report=$(run_oc "$RUNNER_TEMP/work0.md" work0 $W0)
printf '\n## worker report 0\n%s\n' "$report" >> "$log"
commit_leftovers worker
if [ "$(git rev-list --count work..HEAD)" = 0 ]; then
  printf '\nFINAL VERDICT: NOCHANGE  %s  (the worker changed nothing; no review was run)\n' "$(date -u +%FT%TZ)" >> "$log"
  exit 0
fi
verdict=NONE
for i in 0 1; do
  { cat .agent/review.md; cat .agent/task.md; printf '\n--- WORKER REPORT ---\n%s\n' "$report"; } > "$RUNNER_TEMP/review$i.md"
  [ "$(left)" -lt $(( RV + 5 )) ] && { printf '\n## review %s skipped: only %s minutes left\n' "$i" "$(left)" >> "$log"; [ $i = 0 ] && verdict=ERROR; break; }
  rv=$(run_oc "$RUNNER_TEMP/review$i.md" "review$i" $RV)
  if ! grep -q 'VERDICT:' <<< "$rv"; then   # no verdict: an infrastructure failure, try once more
    printf '\n## review %s failed to run: %s\n' "$i" "$(tail -3 <<< "$rv" | tr '\n' ' ')" >> "$log"
    sleep 120; rv=$(run_oc "$RUNNER_TEMP/review$i.md" "review$i" $RV)
  fi
  printf '\n## review %s\n%s\n' "$i" "$rv" >> "$log"
  git reset -q --hard HEAD; git clean -qfd -e .agent -e corpus   # the reviewer only judges; drop anything it left
  if ! grep -q 'VERDICT:' <<< "$rv"; then verdict=ERROR; break; fi
  if grep -q 'VERDICT:[[:space:]]*ACCEPT' <<< "$rv"; then verdict=ACCEPT; break; fi
  if grep -q 'VERDICT:[[:space:]]*REJECT' <<< "$rv"; then verdict=REJECT; break; fi
  verdict=FIX
  [ $i = 1 ] && break
  { printf 'You work in this directory on the current branch (your earlier commits). The reviewer found defects. Fix every one of them, re-run the probes and the required tests, and commit.\n\n--- ORIGINAL TASK ---\n'
    cat .agent/task.md; printf '\n--- REVIEW ---\n%s\n%s\n' "$rv" "$rules"; } > "$RUNNER_TEMP/work1.md"
  w=$(( $(left) - RV - 10 )); [ $w -gt $W1 ] && w=$W1
  [ $w -lt 15 ] && { printf '\n## fix round skipped: only %s minutes left\n' "$(left)" >> "$log"; break; }
  report=$(run_oc "$RUNNER_TEMP/work1.md" work1 $w)
  printf '\n## worker report 1\n%s\n' "$report" >> "$log"
  commit_leftovers fix
done
# accepted work must also keep the full suite green, so the integration gate does not have to find out later
suite_new() {  # prints the test modules that fail now and are not in the known-failing list
  (cd AIL_CURRENT && timeout 75m python3 ../tools/par_check.py -j 4 > "$RUNNER_TEMP/suite.log" 2>&1)
  grep -oE 'FAIL test_ail_[a-z0-9_]+' "$RUNNER_TEMP/suite.log" | awk '{print $2}' | sort -u | grep -vxF -f .agent/integ_base_fail.txt 2>/dev/null
}
if [ "$verdict" = ACCEPT ] && [ $SUITE = 1 ]; then
  bad=$(suite_new)
  printf '\n## full suite\n%s\n' "${bad:-no new failures}" >> "$log"
  if [ -n "$bad" ]; then
    { printf 'Your change is accepted by the reviewer but breaks these test modules in the full suite: %s\n' "$(echo $bad)"
      printf 'Run each (cd AIL_CURRENT && python3 -m unittest -q <module>), find what your change broke, fix it while keeping your own fix and its test, and commit.\n'; } > "$RUNNER_TEMP/worksuite.md"
    report=$(run_oc "$RUNNER_TEMP/worksuite.md" worksuite 60)
    printf '\n## worker report (suite fix)\n%s\n' "$report" >> "$log"
    commit_leftovers suitefix
    bad=$(suite_new)
    printf '\n## full suite again\n%s\n' "${bad:-no new failures}" >> "$log"
    [ -n "$bad" ] && verdict=FIX
  fi
fi
printf '\nFINAL VERDICT: %s  %s\n' "$verdict" "$(date -u +%FT%TZ)" >> "$log"

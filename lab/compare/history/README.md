# compare-lab history

`runs.jsonl` keeps one normalised record per finished `compare-lab` workflow run, and `index.html`
is a static page drawn from it.  The entries are the `compare-report` artifact of each run: the six
columns (wall time, peak RSS, binary size, compile time, build disk, instructions) for every task
and every language the report contains.  A value the report does not carry is `null`; it is never
guessed or copied from another run.

Files:

- `runs.jsonl`: one compact JSON object per line, oldest first.  Each record has `run`, `commit`,
  `date` and `tasks`; `tasks[task][language]` has exactly the six keys `wall_ms`, `rss_kib`,
  `binary_bytes`, `compile_s`, `build_disk_kib`, `instructions`.
- `index.html`: generated; do not edit it by hand.  The six charts are inline SVG, one per column,
  and each point is the geomean of that column against Rust over the tasks present in the run.  A
  change of the task list breaks the line instead of joining incompatible points.  The per-task
  tables below the charts show the latest run with its commit.
- `tools/bench_history.py`: the collector and renderer.  It uses only the Python standard library;
  run it with `python3 -I` so no user site-packages or `PYTHONPATH` entries can change the result.

## Current contents

`runs.jsonl` ships with one record: run `41393616319` (commit `4f1245b`, 2026-11-02), built from the
committed `tools/testdata/compare-report.json` fixture.  On 2026-11-06 there were six finished
`compare-lab` runs on `integ`; the other five are missing here because downloading their artifact
zips needs a GitHub token, which this export did not have.  `collect` will append them (and any newer
runs) when it is run with `actions: read`.

## Usage

Collect new runs (needs the GitHub CLI and a token with `actions: read`; `gh auth login` is enough
locally, or export `GH_TOKEN`):

    python3 -I tools/bench_history.py collect

The collector makes one `gh run list` call, then at most one `gh run download` per finished run.  It
downloads into a fresh temporary directory, reads `compare-report.json` in a `python3 -I` child
process, skips run ids already in `runs.jsonl`, and appends the normalised records atomically.

Render the page after collecting:

    python3 -I tools/bench_history.py render

Options for offline or test use: `collect --runs FILE --repo OWNER/REPO --branch BRANCH --limit N`
and `render --runs FILE --out FILE`.

The page hash test uses the fixed three-run sample in `tools/testdata/bench_history/runs.jsonl`
(one task is missing peak RSS, and the third run changes the task list):

    python3 -m unittest AIL_CURRENT/test_ail_bench_history.py -v

## Owner step for the daily update

Agents may not edit `.github/workflows`, so the step below is for the owner.  Insert it as a new job
after `report` in `.github/workflows/compare-lab.yml`.  The job needs `actions: read` to download the
artifacts and `contents: write` to push the two generated files; the workflow's top-level
`permissions: contents: read` is overridden for this job only.  It uses the same pinned checkout
revision as the other jobs (`3d3c42e5aac5ba805825da76410c181273ba90b1`).

```yaml
  history:
    name: history
    needs: report
    if: always()
    runs-on: ubuntu-24.04
    permissions:
      actions: read
      contents: write
    steps:
      - uses: actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1
        with:
          ref: integ
          fetch-depth: 0
      - name: Collect and render compare-lab history
        env:
          GH_TOKEN: ${{ github.token }}
        run: |
          python3 -I tools/bench_history.py collect
          python3 -I tools/bench_history.py render
      - name: Commit the history
        run: |
          if git diff --quiet -- lab/compare/history/runs.jsonl lab/compare/history/index.html; then
            echo "history unchanged"
            exit 0
          fi
          git config user.name "compare-lab history"
          git config user.email "compare-lab@example.com"
          git add lab/compare/history/runs.jsonl lab/compare/history/index.html
          git commit -m "compare-lab: record history"
          git push origin HEAD:integ
```

`compare-lab` is manual today.  To make the collection daily without rerunning the lab, add a
`schedule:` trigger to the workflow and guard the measurement jobs with
`if: github.event_name == 'workflow_dispatch'`, leaving this `history` job to run on the schedule
(`if: always()` already lets it run when `report` is skipped).  Alternatively call the two commands
from an owner-maintained daily cron job; they do not need a checkout of the measured commit, only
the artifact metadata that `gh` returns.

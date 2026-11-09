# vibe3 run note (2026-11-09)

The opencode free-model quota ran out mid-run. `opencode run` answered
`AI_APICallError: Free usage limit reached` for every free model and
`Go usage limit exceeded` for the paid one, so every call after 10:25 UTC hung until the
harness timeout. The partial rows from that phase are kept in
`results3-opencode-partial.json` and are **not** mixed into `results3.json`.

The recorded numbers in `results3.json` come from the worker's own model,
`deepseek/deepseek-v4.1-flash` through the installed Command Code CLI (`cmd`), which is the
free model this worker runs on, called non-interactively with
`cmd -p --model deepseek/deepseek-v4.1-flash --yolo -t --max-turns 1 --output-format json`.

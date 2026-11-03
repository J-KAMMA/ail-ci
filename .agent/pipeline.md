# job job-fuzzpyb-11040506  started 2026-11-03T20:09:57Z  worker=oc reviewer=oc (GitHub)

## worker report 0
[model opencode/deepseek-v4.1-flash-free]
Done. Ran all 500 seeds: `summary.json` = silent 0, loud-ok 115, crash 0, refused 30, other 355 (346 identical + 9 stderr-only); typed path 257/500 (51.4%).

Filed 5 reduced findings in `lab/fuzzpy/findings/` — all stderr-only uncaught-trap text differences; no silent wrong outputs or crashes. `seed22` is a compile-time int64 refusal, counted loud-ok and not filed. `REPORT.md` and `DEVLOG.md` updated.

Commits `2464346..c718e7f` on `job-fuzzpyb-11040506`; not pushed per final instruction. `test_ail_files`, `test_ail_corpus_findings3`, `test_ail_safetynet` pass; the 20 CI shards were not run because pushing was disabled.
[cost $0.0000, opencode tokens {"total": 3192761, "input": 121695, "output": 10175, "reasoning": 15259, "cache.write": 0, "cache.read": 3045632}]
    tool time: bash 48.3 min
        515s bash   time python3 lab/fuzzpy/run.py --start 101 --count 100 --jobs 2 --out lab/fuzzpy/out 2>&1 | tail -40; python3 
        466s bash   time python3 lab/fuzzpy/run.py --start 201 --count 100 --jobs 2 --out lab/fuzzpy/out 2>&1 | tail -45; python3 
        457s bash   time python3 lab/fuzzpy/run.py --start 401 --count 100 --jobs 2 --out lab/fuzzpy/out 2>&1 | tail -50; python3 
        448s bash   time python3 lab/fuzzpy/run.py --start 301 --count 100 --jobs 2 --out lab/fuzzpy/out 2>&1 | tail -50; python3 
        397s bash   time python3 lab/fuzzpy/run.py --start 1 --count 100 --jobs 2 --out lab/fuzzpy/out 2>&1 | tail -35; python3 - 
        248s bash   python3 -B test_ail_files.py > /tmp/t_files.log 2>&1 & p1=$!; python3 -B test_ail_corpus_findings3.py > /tmp/t
        198s bash   python3 -B test_ail_safetynet.py > /tmp/t_safe.log 2>&1; r=$?; echo "safetynet rc=$r"; tail -8 /tmp/t_safe.log
         69s bash   time python3 lab/fuzzpy/run.py --start 1 --count 20 --jobs 2 --out lab/fuzzpy/out 2>&1 | tail -60

## review 0 failed to run: (free quota used up; paid model from here) [model commandcode/deepseek-v4.1-flash] 

## review 0
[model commandcode/deepseek-v4.1-flash]

FINAL VERDICT: ERROR  2026-11-03T21:27:31Z

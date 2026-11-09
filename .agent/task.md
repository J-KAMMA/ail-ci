Lane: dogfood

# dog1: first real use of AIL: an AI writes the gate-statistics tool in AIL (dogfooding)

Time budget: 150 minutes. Commit and push after each sub-step. Follow `.agent/` rules. No compiler change.

**Why (owner, 2026-11-09):** AIL's main front is "the language AI writes". It needs a real use, not only benchmarks.
The first real use is our own agent system: a tool that runs every few minutes for real. Every friction you meet
(refusal, unclear error, slow compile, missing stdlib piece) is the product of this job, as much as the tool.

**Input:** `lab/dogfood/gatestats/fixture/ci_integ.out` (create it from the fixture at the end of this task; it is a
log excerpt of the integration gate, no secrets). Lines look like:
`HH:MM:SS candidate cand-<id>: job1 job2 ...`, `HH:MM:SS merged cand-<id>: ...`, `HH:MM:SS red: ... retrying in halves`,
`HH:MM:SS red alone: <job> (<modules>)`, `HH:MM:SS culprit.yml unavailable (rc N, try K)`,
`HH:MM:SS red: <module> broken by <job> (found locally); sent back, ...`. Other lines are noise (git help text etc.).
Times have no date: a time smaller than the previous one means the next day.

**Tool** `lab/dogfood/gatestats/gatestats.py` (plain Python with annotations, compiled by `ailc` to a native binary):
read the log path from argv, print a fixed-format report: per day: candidates, merged jobs, red batches, red-alone
jobs, culprit-unavailable count, and hours between the first `red:` of a batch and its resolution (next candidate or
merge). Also the top 5 modules that broke most often. Output must be byte-identical between CPython and the AIL binary.

**Method:** write it the way a vibe coder would: write, compile with ailc, fix from the messages. Log every round in
`lab/dogfood/gatestats/FRICTION.md`: the error text, whether the message alone told you the fix, minutes lost, and
whether the program fell to the general path (say how you found out). Measure compile seconds, binary size, run time
and peak RSS vs CPython on the fixture (median of 5).

Files: `lab/dogfood/*` only. Report: the tool works (yes/no), the friction table, the numbers.
## Fixture (save verbatim as lab/dogfood/gatestats/fixture/ci_integ.out; add 3 noise lines of your own)
```
04:48:25 candidate cand-1101044745: rbstdlib25
05:21:05 merged cand-1101044745: rbstdlib25
09:06:42 candidate cand-1101090612: fz208
09:26:47 merged cand-1101090612: fz208
12:45:06 candidate cand-1101124419: covi64c1
13:35:27 merged cand-1101124419: covi64c1
14:41:49 candidate cand-1101144115: fepar2 i64base1
15:19:38 merged cand-1101144115: fepar2 i64base1
15:21:10 candidate cand-1101151949: covenv2 i64tests1 rbccsplit2 srvdef1
16:18:10 red: test_ail_packaging broken by rbccsplit2 (found locally); sent back, rest requeued as one: covenv2 i64tests1 srvdef1 
16:19:20 candidate cand-1101161840: covenv2 i64tests1 srvdef1
17:05:53 merged cand-1101161840: covenv2 i64tests1 srvdef1
17:06:54 candidate cand-1101170605: docints1 rbfailfast rbnoimpl
18:01:27 red: docints1 rbfailfast rbnoimpl (test_ail_packaging test_ail_pre246 test_ail_pre33); retrying in halves
18:02:15 candidate cand-1101180129: docints1 rbfailfast
18:33:06 red: test_ail_packaging broken by rbfailfast (found locally); sent back, rest requeued as one: docints1 
18:35:35 candidate cand-1101183315: rbnoimpl
19:13:25 red alone: rbnoimpl (test_ail_pre246 test_ail_pre33)
19:14:46 candidate cand-1101191405: docints1
20:04:52 merged cand-1101191405: docints1
20:06:28 candidate cand-1101200512: rbccsplit2 std_heapq std_pprint
21:03:56 merged cand-1101200512: rbccsplit2 std_heapq std_pprint
21:05:06 candidate cand-1101210412: rbfailfast rbi64edge1 std_csv std_datetime std_fractions std_statistics
22:14:34 red: test_ail_gpu_g1 broken by rbi64edge1 (found locally); sent back, rest requeued as one: rbfailfast std_csv std_datetime std_fractions std_statistics 
22:16:44 candidate cand-1101221518: rbfailfast std_csv std_datetime std_fractions std_statistics
22:51:39 merged cand-1101221518: rbfailfast std_csv std_datetime std_fractions std_statistics
22:52:57 candidate cand-1101225154: beatc1 rbnoimpl std_json std_random std_shlex
23:47:57 merged cand-1101225154: beatc1 rbnoimpl std_json std_random std_shlex
23:48:53 candidate cand-1101234810: cpyhyb1 std_base64
00:36:53 merged cand-1101234810: cpyhyb1 std_base64
02:21:03 candidate cand-1102022043: std_bisect
03:09:41 merged cand-1102022043: std_bisect
03:10:19 candidate cand-1102030954: rbi64edge1 tccdev1
04:11:55 merged cand-1102030954: rbi64edge1 tccdev1
04:12:32 candidate cand-1102041207: rbmanifs1 std_graphlib stdlib2
05:05:18 merged cand-1102041207: rbmanifs1 std_graphlib stdlib2
05:05:56 candidate cand-1102050530: std_string
06:15:14 merged cand-1102050530: std_string
06:16:08 candidate cand-1102061527: decexact2 prog1
07:40:31 red: decexact2 prog1 (test_ail_hostile_input); retrying in halves
07:40:54 candidate cand-1102074033: decexact2
09:14:41 red alone: decexact2 (test_ail_hostile_input)
09:15:16 candidate cand-1102091456: prog1
10:17:15 merged cand-1102091456: prog1
10:18:13 candidate cand-1102101732: cls1 mem1 prog2 prog3 prog5 std_array std_collections
11:40:52 merged cand-1102101732: cls1 mem1 prog2 prog3 prog5 std_array std_collections
11:42:02 candidate cand-1102114114: prog10 std_numbers tup1
12:49:31 merged cand-1102114114: prog10 std_numbers tup1
12:50:27 candidate cand-1102124950: prog11 rbstd_math
13:57:41 merged cand-1102124950: prog11 rbstd_math
16:26:16 candidate cand-1102162557: prog13
17:34:28 merged cand-1102162557: prog13
17:35:28 candidate cand-1102173447: prog12 prog15 prog19 prog21 prog22
18:57:05 merged cand-1102173447: prog12 prog15 prog19 prog21 prog22
20:08:21 candidate cand-1102200625: rbstd_decimal
20:55:49 merged cand-1102200625: rbstd_decimal
21:14:04 candidate cand-1102210146: rbprog8
21:52:27 merged cand-1102210146: rbprog8
21:53:14 candidate cand-1102215243: fecache1 prog27 rbprog16
22:43:10 merged cand-1102215243: fecache1 prog27 rbprog16
22:45:07 candidate cand-1102224400: fz216
23:51:57 merged cand-1102224400: fz216
23:52:58 candidate cand-1102235215: prog30 rbprog20
00:54:55 merged cand-1102235215: prog30 rbprog20
01:00:44 candidate cand-1103005905: rbprog7
02:02:52 merged cand-1103005905: rbprog7
02:04:35 candidate cand-1103020317: rbprog29 reldiag reltable
02:56:16 merged cand-1103020317: rbprog29 reldiag reltable
02:56:56 candidate cand-1103025633: rails1 spec1
03:39:28 merged cand-1103025633: rails1 spec1
03:40:07 candidate cand-1103033944: rbprog23 relpkgname relplatinstall
04:25:14 merged cand-1103033944: rbprog23 relpkgname relplatinstall
04:25:52 candidate cand-1103042531: arena1s1
05:07:54 merged cand-1103042531: arena1s1
06:14:13 candidate cand-1103061353: onelangs1
06:43:48 merged cand-1103061353: onelangs1
06:44:33 candidate cand-1103064404: relevalorder
07:27:19 merged cand-1103064404: relevalorder
11:31:32 candidate cand-1103113114: onelangs2
12:05:09 merged cand-1103113114: onelangs2
13:46:42 candidate cand-1103134618: relwheelfix
14:27:09 merged cand-1103134618: relwheelfix
18:03:47 candidate cand-1103180310: pyreachs1
18:38:00 merged cand-1103180310: pyreachs1
18:38:45 candidate cand-1103183816: onelangs4
19:43:43 merged cand-1103183816: onelangs4
22:15:28 candidate cand-1103221503: onelangs13
22:50:14 merged cand-1103221503: onelangs13
00:12:39 candidate cand-1104001213: fz220
00:54:23 merged cand-1104001213: fz220
00:57:23 candidate cand-1104005645: onelangs12b
02:04:58 merged cand-1104005645: onelangs12b
02:05:57 candidate cand-1104020521: onelangs5b
02:41:48 merged cand-1104020521: onelangs5b
04:03:20 candidate cand-1104040247: bces1
04:07:06 merged cand-1104040247: bces1
04:08:14 candidate cand-1104040734: arena1s4
04:12:08 merged cand-1104040734: arena1s4
05:06:34 candidate cand-1104050538: pyreachs4
05:13:21 merged cand-1104050538: pyreachs4
08:09:38 candidate cand-1104080912: ffiex1
08:13:32 merged cand-1104080912: ffiex1
09:28:20 candidate cand-1104092750: rails3b
09:32:07 merged cand-1104092750: rails3b
12:25:09 candidate cand-1104122423: relrterr3b std_re
12:28:58 merged cand-1104122423: relrterr3b std_re
13:50:19 candidate cand-1104135000: fz226
13:54:09 merged cand-1104135000: fz226
14:25:08 candidate cand-1104142445: ctimeprofc
14:28:50 merged cand-1104142445: ctimeprofc
14:46:33 candidate cand-1104144602: pyreachs3c
14:50:22 merged cand-1104144602: pyreachs3c
14:51:12 candidate cand-1104145051: std_sqlite3
14:54:57 merged cand-1104145051: std_sqlite3
14:55:37 candidate cand-1104145510: std_hashlib
14:59:27 merged cand-1104145510: std_hashlib
15:00:35 candidate cand-1104150000: selfhost1b
15:04:20 merged cand-1104150000: selfhost1b
15:06:27 candidate cand-1104150550: fuzzpyc
15:30:20 merged cand-1104150550: fuzzpyc
16:16:49 candidate cand-1104161615: stdcensus1
16:24:01 merged cand-1104161615: stdcensus1
16:25:16 candidate cand-1104162418: pkgcheck1
16:29:00 merged cand-1104162418: pkgcheck1
16:33:49 candidate cand-1104163315: tutproj1
16:37:33 merged cand-1104163315: tutproj1
16:38:15 candidate cand-1104163746: smoke1
16:42:01 merged cand-1104163746: smoke1
17:14:31 candidate cand-1104171357: infer1
21:18:30 test_ail_ail2py fails on integ too: ignored for this candidate
21:18:30 test_ail_argument_type_details fails on integ too: ignored for this candidate
21:18:30 test_ail_bce fails on integ too: ignored for this candidate
21:18:30 test_ail_bound_builtin fails on integ too: ignored for this candidate
21:18:30 test_ail_cc_split fails on integ too: ignored for this candidate
21:18:30 test_ail_check_repair_context fails on integ too: ignored for this candidate
21:18:30 test_ail_classnames fails on integ too: ignored for this candidate
21:18:30 test_ail_collections fails on integ too: ignored for this candidate
21:18:30 test_ail_cpython_hybrid fails on integ too: ignored for this candidate
21:18:30 test_ail_gpu_g1 fails on integ too: ignored for this candidate
21:18:30 test_ail_int64_default fails on integ too: ignored for this candidate
21:18:30 test_ail_onelang_twins fails on integ too: ignored for this candidate
21:18:30 test_ail_prog2 fails on integ too: ignored for this candidate
21:18:30 test_ail_prog21 fails on integ too: ignored for this candidate
21:18:30 test_ail_silent_diffs3 fails on integ too: ignored for this candidate
21:18:30 test_ail_source_check fails on integ too: ignored for this candidate
21:18:37 merged cand-1104171357: infer1
21:19:24 candidate cand-1104211851: bigbench1 cmpcand1 colorsys2 getopt1
22:40:40 test_ail_ail2py fails on integ too: ignored for this candidate
22:40:40 test_ail_bce fails on integ too: ignored for this candidate
22:40:40 test_ail_bound_builtin fails on integ too: ignored for this candidate
22:40:40 test_ail_cc_split fails on integ too: ignored for this candidate
22:40:40 test_ail_classnames fails on integ too: ignored for this candidate
22:40:40 test_ail_cpython_hybrid fails on integ too: ignored for this candidate
22:40:40 test_ail_gpu_g1 fails on integ too: ignored for this candidate
22:40:40 test_ail_int64_default fails on integ too: ignored for this candidate
22:40:40 test_ail_onelang_twins fails on integ too: ignored for this candidate
22:40:40 test_ail_prog2 fails on integ too: ignored for this candidate
22:40:40 test_ail_prog21 fails on integ too: ignored for this candidate
22:40:40 test_ail_silent_diffs3 fails on integ too: ignored for this candidate
22:41:16 merged cand-1104211851 here (shared-file conflicts resolved): bigbench1 cmpcand1 colorsys2 getopt1
22:42:03 candidate cand-1104224129: sdkdiag1
23:44:38 test_ail_ail2py fails on integ too: ignored for this candidate
23:44:38 test_ail_bce fails on integ too: ignored for this candidate
23:44:38 test_ail_bound_builtin fails on integ too: ignored for this candidate
23:44:38 test_ail_cc_split fails on integ too: ignored for this candidate
23:44:38 test_ail_classnames fails on integ too: ignored for this candidate
23:44:38 test_ail_cpython_hybrid fails on integ too: ignored for this candidate
23:44:38 test_ail_gpu_g1 fails on integ too: ignored for this candidate
23:44:38 test_ail_int64_default fails on integ too: ignored for this candidate
23:44:38 test_ail_onelang_twins fails on integ too: ignored for this candidate
23:44:38 test_ail_prog2 fails on integ too: ignored for this candidate
23:44:38 test_ail_prog21 fails on integ too: ignored for this candidate
23:44:38 test_ail_silent_diffs3 fails on integ too: ignored for this candidate
23:44:45 merged cand-1104224129: sdkdiag1
23:45:57 candidate cand-1104234502: rblsp1c
01:34:04 test_ail_ail2py fails on integ too: ignored for this candidate
01:34:04 test_ail_bce fails on integ too: ignored for this candidate
01:34:04 test_ail_bound_builtin fails on integ too: ignored for this candidate
01:34:04 test_ail_cc_split fails on integ too: ignored for this candidate
01:34:04 test_ail_classnames fails on integ too: ignored for this candidate
01:34:04 test_ail_cpython_hybrid fails on integ too: ignored for this candidate
01:34:04 test_ail_gpu_g1 fails on integ too: ignored for this candidate
01:34:04 test_ail_int64_default fails on integ too: ignored for this candidate
01:34:04 test_ail_onelang_twins fails on integ too: ignored for this candidate
01:34:04 test_ail_prog2 fails on integ too: ignored for this candidate
01:34:04 test_ail_prog21 fails on integ too: ignored for this candidate
01:34:04 test_ail_silent_diffs3 fails on integ too: ignored for this candidate
01:34:13 merged cand-1104234502: rblsp1c
01:34:58 candidate cand-1105013426: rbhybex1 relrterr4
03:06:49 test_ail_cpython_hybrid fails on integ too: added to the base list
03:07:06 test_ail_prog2 fails on integ too: added to the base list
03:07:50 test_ail_prog21 fails on integ too: added to the base list
03:07:57 merged cand-1105013426: rbhybex1 relrterr4
03:08:46 candidate cand-1105030811: bindgen1_rr1 cmpjoin1 pyperf1 rbcrate1 stdlex1 stdstat1
04:23:54 merged cand-1105030811: bindgen1_rr1 cmpjoin1 pyperf1 rbcrate1 stdlex1 stdstat1
04:24:41 candidate cand-1105042409: appmd1 arrt6_rr1 errux1 porting1 stats2_rr1
05:37:03 test_ail_pre1 passes on the candidate when re-run: flaky, ignored
05:37:11 merged cand-1105042409: appmd1 arrt6_rr1 errux1 porting1 stats2_rr1
05:38:00 candidate cand-1105053727: prog17_rr1 pyr3fix
07:12:56 red: test_ail_typed_blockers broken by prog17_rr1 (found locally); sent back, rest requeued as one: pyr3fix 
07:13:22 candidate cand-1105071257: pyr3fix
07:50:08 merged cand-1105071257: pyr3fix
07:50:57 candidate cand-1105075022: rbbces2c rbdifflib2 rbtoml1 rbtypeshed1
09:04:16 merged cand-1105075022: rbbces2c rbdifflib2 rbtoml1 rbtypeshed1
09:04:58 candidate cand-1105090431: rbdiffixed1
09:51:57 merged cand-1105090431: rbdiffixed1
09:58:04 candidate cand-1105095737: fz227
11:05:54 merged cand-1105095737: fz227
11:06:39 candidate cand-1105110611: rbprog17_rr1
12:15:04 merged cand-1105110611: rbprog17_rr1
12:15:51 candidate cand-1105121517: rbprog18_rr1 spec2c
13:21:44 red: test_ail_refuzz95 broken by rbprog18_rr1 (found locally); sent back, rest requeued as one: spec2c 
13:22:14 candidate cand-1105132145: spec2c
14:07:25 merged cand-1105132145: spec2c
14:09:34 candidate cand-1105140804: algos1 cmplog1 docsrun1 quopri1 typeshed2
15:10:53 merged cand-1105140804: algos1 cmplog1 docsrun1 quopri1 typeshed2
15:27:21 candidate cand-1105152625: rbprog18_rr1
16:55:39 merged cand-1105152625: rbprog18_rr1
16:56:36 candidate cand-1105165557: bces3 rbpyreachs5c_rr1 relver1
18:12:20 merged cand-1105165557: bces3 rbpyreachs5c_rr1 relver1
18:13:46 candidate cand-1105181304: pyreachs7
19:33:59 red alone: pyreachs7 (test_ail_prog5 test_ail_pyperf_lab)
19:35:09 candidate cand-1105193434: races1 rbpyproof1 rbsched1
20:51:33 merged cand-1105193434: races1 rbpyproof1 rbsched1
20:52:26 candidate cand-1105205152: rbrelcheck1 rc1
22:08:05 merged cand-1105205152: rbrelcheck1 rc1
22:09:23 candidate cand-1105220836: ctimes2 devcc2
23:47:56 merged cand-1105220836: ctimes2 devcc2
23:49:03 candidate cand-1105234823: cliexa1 cliexb1 safebnd1 safestop1 whyail1
01:26:21 merged cand-1105234823: cliexa1 cliexb1 safebnd1 safestop1 whyail1
01:27:38 candidate cand-1106012641: hard1 limits1 pyreachs7 races2 safeovf1
03:42:45 merged cand-1106012641: hard1 limits1 pyreachs7 races2 safeovf1
03:43:56 candidate cand-1106034310: ctimes3 fnvfix1 linecache1 rbbces4 rbtccprobe1 struct1 typeshed3_rr1
05:10:27 merged cand-1106034310: ctimes3 fnvfix1 linecache1 rbbces4 rbtccprobe1 struct1 typeshed3_rr1
05:11:31 candidate cand-1106051048: rbbces7 rc2 fcspec0
06:57:07 merged cand-1106051048: rbbces7 rc2 fcspec0
06:58:22 candidate cand-1106065731: advparse1 docffiq1 docmigr1 imghdr1 mdtable1 netrc1 opustest1 safeiter1
08:08:09 merged cand-1106065731: advparse1 docffiq1 docmigr1 imghdr1 mdtable1 netrc1 opustest1 safeiter1
08:09:07 candidate cand-1106080829: jsonpp1 races3 safetype1 shfiles1 shfixpt1 shseed1 fbgenint1 fcclass1
09:28:13 merged cand-1106080829: jsonpp1 races3 safetype1 shfiles1 shfixpt1 shseed1 fbgenint1 fcclass1
09:29:13 candidate cand-1106092833: chunk1 cmpbfs1 devcc1_rr1 fbred1 shdeps1 xdrlib1 callinf1 pyreachs6b
13:15:52 red: chunk1 cmpbfs1 devcc1_rr1 fbred1 shdeps1 xdrlib1 callinf1 pyreachs6b (test_ail_pre70 test_ail_std_re); retrying in halves
13:16:53 candidate cand-1106131554: chunk1 cmpbfs1 devcc1_rr1 fbred1
14:22:05 merged cand-1106131554: chunk1 cmpbfs1 devcc1_rr1 fbred1
14:22:48 candidate cand-1106142207: shdeps1 xdrlib1 callinf1 pyreachs6b
17:41:35 red: shdeps1 xdrlib1 callinf1 pyreachs6b (test_ail_pre70 test_ail_std_re); retrying in halves
17:42:34 candidate cand-1106174141: shdeps1 xdrlib1
18:28:06 merged cand-1106174141: shdeps1 xdrlib1
18:29:08 candidate cand-1106182808: callinf1 pyreachs6b
20:48:05 test_ail_std_re fails on integ too: added to the base list
22:21:43 culprit.yml unavailable (rc 2, try 1)
22:32:05 candidate cand-1106222938: pyreachs6b
22:33:38 candidate cand-1106223224: fdarr1
23:27:35 merged cand-1106222938: pyreachs6b
23:31:58 candidate cand-1106233123: bces6 cmpwrap1 ctimes1_rr1 devcc3 fbpmap1 fbred2 feinf2 ffasync0 ffcrate2
23:36:04 candidate cand-1106233545: fdarr1
00:22:15 merged cand-1106233123: bces6 cmpwrap1 ctimes1_rr1 devcc3 fbpmap1 fbred2 feinf2 ffasync0 ffcrate2
00:27:07 candidate cand-1107002623: fddbg1_rr1 ffdash1 ffembed1 ffpkg0 ffre1 ffwasm1_rr1 rbfbnarrow1_rr1
00:52:17 candidate cand-1107005154: fdarr1
01:35:16 merged cand-1107002623: fddbg1_rr1 ffdash1 ffembed1 ffpkg0 ffre1 ffwasm1_rr1 rbfbnarrow1_rr1
01:39:12 candidate cand-1107013849: roadmap2
02:08:29 candidate cand-1107020805: fdarr1
02:44:19 red alone: roadmap2 (test_ail_docs_why)
02:48:59 candidate cand-1107024826: fz235 fz236 rails2_rr1 rbfdgpu1 rbfdinf1 rbfdlsp1
03:35:28 merged cand-1107020805: fdarr1
03:39:45 candidate cand-1107033913: rbffbig0 rbffdocs1 rbffice1 rbffrepro1 recstop1 relnotice1_rr1
03:58:10 candidate cand-1107035742: fz235 fz236 rails2_rr1 rbfdgpu1 rbfdinf1 rbfdlsp1
06:08:40 culprit.yml unavailable (rc 2, try 1)
06:14:46 red: test_ail_third_party_notices broken by relnotice1_rr1 (found locally); sent back, rest requeued as one: rbffbig0 rbffdocs1 rbffice1 rbffrepro1 recstop1 
06:15:09 merged cand-1107035742: fz235 fz236 rails2_rr1 rbfdgpu1 rbfdinf1 rbfdlsp1
06:18:56 candidate cand-1107061828: rbffbig0 rbffdocs1 rbffice1 rbffrepro1 recstop1
06:19:27 candidate cand-1107061902: fdarr3
07:34:14 merged cand-1107061828: rbffbig0 rbffdocs1 rbffice1 rbffrepro1 recstop1
07:38:31 candidate cand-1107073800: cmprival1 fbpmap2 fbred3 ffembed2 ffre2 proof1 robo1 vibe1
07:49:57 candidate cand-1107074933: fdarr3
08:50:10 merged cand-1107073800: cmprival1 fbpmap2 fbred3 ffembed2 ffre2 proof1 robo1 vibe1
08:54:23 candidate cand-1107085356: rbpyreachs2_rr1 rbrbarena1s2c_rr1 rbrbpyreachs8_rr1
09:12:47 candidate cand-1107091224: fdarr3
10:06:25 merged cand-1107085356: rbpyreachs2_rr1 rbrbarena1s2c_rr1 rbrbpyreachs8_rr1
10:10:20 candidate cand-1107100958: roadmap2
10:39:05 candidate cand-1107103842: fdarr3
11:25:53 merged cand-1107100958: roadmap2
11:29:54 candidate cand-1107112923: fdgpu2 rbroof1 rbs4gc1 rbtcc1
11:55:49 merged cand-1107103842: fdarr3
12:25:18 candidate cand-1107122451: rbfclist1
12:48:11 merged cand-1107112923 here (shared-file conflicts resolved): fdgpu2 rbroof1 rbs4gc1 rbtcc1
13:25:39 candidate cand-1107132514: arena1s3_rr1
13:26:10 merged cand-1107122451: rbfclist1
13:37:12 candidate cand-1107133643: rbrundiff1_rr1
14:19:40 candidate cand-1107141919: arena1s3_rr1
14:45:49 merged cand-1107133643: rbrundiff1_rr1
14:53:33 candidate cand-1107145301: fbpmap3
15:07:34 candidate cand-1107150655: arena1s3_rr1
15:34:16 merged cand-1107145301: fbpmap3
15:38:15 candidate cand-1107153750: rbctpred1_rr1
16:15:09 candidate cand-1107161438: arena1s3_rr1
16:42:12 merged cand-1107153750: rbctpred1_rr1
17:08:40 candidate cand-1107170817: pyreach10
17:18:58 merged cand-1107161438: arena1s3_rr1
19:46:11 candidate cand-1107194539: rbpyreach9
19:50:22 candidate cand-1107194947: pyreach10
21:14:51 merged cand-1107194947: pyreach10
21:18:59 candidate cand-1107211817: pyreach11
21:30:06 merged cand-1107194539: rbpyreach9
21:35:01 candidate cand-1107213402: rbemit1 rberr1 rbfe1
22:38:24 red alone: pyreach11 (test_ail_docs_migrating test_ail_prog29)
22:39:39 merged cand-1107213402: rbemit1 rberr1 rbfe1
22:45:54 candidate cand-1107224416: energy1
23:53:47 candidate cand-1107235316: pyreach11
23:54:13 merged cand-1107224416: energy1
23:58:53 candidate cand-1107235813: vibe2
00:54:47 merged cand-1107235316: pyreach11
01:00:04 candidate cand-1108005852: setord1
01:14:22 merged cand-1107235813: vibe2
03:10:26 candidate cand-1108030940: err2
03:25:58 red alone: setord1 (test_ail_bigint test_ail_examples_algos test_ail_fuzz81 test_ail_pyreach_dictrows test_ail_re_value test_ail_std_difflib test_ail_std_pprint)
03:39:25 candidate cand-1108033512: strat1
04:18:13 red alone: err2 (test_ail_packaging test_ail_sdk_environment)
04:22:54 candidate cand-1108042216: logo1
04:26:46 merged cand-1108033512: strat1
04:31:51 candidate cand-1108043108: layout1
05:00:24 merged cand-1108042216: logo1
05:16:30 candidate cand-1108051557: cpyhyb2d
05:34:23 merged cand-1108043108: layout1
06:11:09 candidate cand-1108061032: setord1
06:15:21 candidate cand-1108061458: cpyhyb2d
06:37:12 test_ail_owned_join_take passes on the candidate when re-run: flaky, ignored
06:50:03 red alone: setord1 (test_ail_re_value)
06:54:48 candidate cand-1108065421: err2 fz239
07:23:06 merged cand-1108061458: cpyhyb2d
07:27:22 candidate cand-1108072656: err2 fz239
08:40:11 candidate cand-1108083945: err2b
08:40:36 merged cand-1108072656: err2 fz239
10:29:29 candidate cand-1108102847: setord1
11:02:55 candidate cand-1108110214: shtok1
11:14:00 merged cand-1108102847: setord1
12:07:48 candidate cand-1108120656: err2_fix1
12:12:13 candidate cand-1108121142: shtok1
12:44:34 merged cand-1108120656: err2_fix1
12:49:08 candidate cand-1108124829: wedge1
13:14:17 merged cand-1108121142: shtok1
15:42:36 candidate cand-1108154155: shast1
15:42:59 merged cand-1108124829: wedge1
16:28:00 candidate cand-1108162659: fbnarrow3
17:01:08 merged cand-1108154155: shast1
17:59:59 candidate cand-1108175750: fddbg2
18:20:39 red alone: fbnarrow3 (test_ail_server)
18:28:47 candidate cand-1108182755: wedge2
18:51:11 merged cand-1108175750: fddbg2
18:55:44 candidate cand-1108185511: ffpkg1
19:06:51 merged cand-1108182755: wedge2
19:15:36 candidate cand-1108191506: mypyc1_rr1
20:06:13 merged cand-1108185511: ffpkg1
20:10:45 candidate cand-1108201013: ffsbom1 ffwasm2 fz240
20:32:46 merged cand-1108191506: mypyc1_rr1
20:37:21 candidate cand-1108203644: fbnarrow3
21:06:12 merged cand-1108201013: ffsbom1 ffwasm2 fz240
21:17:40 candidate cand-1108211709: rbstdfall2c
21:32:34 candidate cand-1108213210: fbnarrow3
22:51:32 merged cand-1108211709: rbstdfall2c
22:56:10 candidate cand-1108225532: aiknow1
23:03:59 candidate cand-1108230337: fbnarrow3
00:08:38 merged cand-1108225532: aiknow1
00:12:38 candidate cand-1109001216: secign1
00:20:31 candidate cand-1109002004: fbnarrow3
01:07:01 merged cand-1109001216: secign1
01:11:28 candidate cand-1109011057: rbfdlsp2 rbsetord2_rr1
01:29:33 merged cand-1109002004: fbnarrow3
01:50:06 candidate cand-1109014938: fz241
04:36:51 culprit.yml unavailable (rc 2, try 1)
06:14:48 culprit.yml unavailable (rc 2, try 2)
06:14:48 red: rbfdlsp2 rbsetord2_rr1 (test_ail_bigint); retrying in halves
06:15:25 merged cand-1109014938: fz241
06:22:42 candidate cand-1109061849: rbfdlsp2
06:24:38 candidate cand-1109062242: rbsetord2_rr1
07:33:14 merged cand-1109061849: rbfdlsp2
07:51:50 red alone: rbsetord2_rr1 (test_ail_bigint)
07:56:09 candidate cand-1109075539: augidx1 obs1
07:57:34 candidate cand-1109075645: fbnarrow4 fbred4_rr2 fbregion1 fz243 rberr3 rbwedge4 shparse1
08:33:18 merged cand-1109075539: augidx1 obs1
08:37:42 candidate cand-1109083712: fz244
10:16:20 culprit.yml unavailable (rc 2, try 1)
11:52:33 culprit.yml unavailable (rc 2, try 2)
11:52:33 red: fbnarrow4 fbred4_rr2 fbregion1 fz243 rberr3 rbwedge4 shparse1 (test_ail_docs_site test_ail_par_reduce_rt); retrying in halves
11:52:58 merged cand-1109083712: fz244
11:56:46 candidate cand-1109115615: fbnarrow4 fbred4_rr2 fbregion1 fz243
11:57:16 candidate cand-1109115646: rberr3 rbwedge4 shparse1
12:37:57 red: test_ail_docs_site broken by rbwedge4 (found locally); sent back, rest requeued as one: rberr3 shparse1 
12:41:47 candidate cand-1109124116: rberr3 shparse1
14:24:35 culprit.yml unavailable (rc 2, try 1)
14:30:55 red: test_ail_par_reduce_rt broken by fbred4_rr2 (found locally); sent back, rest requeued as one: fbnarrow4 fbregion1 fz243 
14:31:15 merged cand-1109124116: rberr3 shparse1
14:35:07 candidate cand-1109143434: fbnarrow4 fbregion1 fz243
14:36:25 candidate cand-1109143543: pypy1 rbobs2 rbsetord2_rr1
15:36:31 merged cand-1109143434: fbnarrow4 fbregion1 fz243
15:41:03 candidate cand-1109154030: pypy1 rbobs2 rbsetord2_rr1
15:42:13 candidate cand-1109154137: rbwedge4 wedge3 wedge3b wedge3d
16:46:34 merged cand-1109154030: pypy1 rbobs2 rbsetord2_rr1
16:47:20 red: wedge3 own tests fail; sent back, rest requeued as one: rbwedge4 wedge3b wedge3d 
16:51:16 candidate cand-1109165043: wedge3b wedge3d
```

**Rules for every job.**
- **Load:** you are one of up to five agents on a 16 GB PC. Keep local parallelism at 2 (`-j 2`) and never run the whole suite; the full suite runs on CI after merge.
- **Commits:** commit with explicit `git add` on your branch. Messages end with a `Co-Authored-By:` line naming the model you actually are (Claude: `Claude Opus 5.5 <noreply@anthropic.com>` or `Claude Sonnet 5.5 <noreply@anthropic.com>`; other models: omit the line).
- **Forbidden:** push, stash, rebase, reset, and deletion outside /tmp.
- **Records:**
  - New DIFFERENCES rows use placeholder ids `C?-<your branch>-N`.
  - Add a DEVLOG entry at the top with today's date.
  - Register a new test module: if `AIL_CURRENT/tests.d/` exists, add `AIL_CURRENT/tests.d/<module>.txt` containing the module
    name and do NOT edit the tuple in `ail_check.py`; otherwise append it to the `MODULES` tuple.
  - `git add` new files, run `python3 tools/update_manifest.py`, then `--check`. Do not hand-edit `MANIFEST.json` or `manifest.d/`.
- **Required tests:** the targeted modules for what you touch, plus test_ail_safetynet, test_ail_files and test_ail_corpus_findings3. Run them on your final commit, not an earlier one.
- **Mandatory self-check before you report.** A reviewer will repeat it, and past reports were wrong about half the time.
  1. Write probe programs in /tmp/probes/ for every behaviour you changed. Cover the boundaries your implementation implies, not only the example: types, widths, empty, negative, aliasing, values reaching the code through an argument, a list item, an attribute and a dict value, and both builds.
  2. Run each probe with `bash ~/tools/cmp.sh /tmp/probes/<p>.py $PWD`.
  3. Every probe must match CPython or be refused by name.
  4. List the probes and their results in the report.
- **Never claim something works unless a probe or test you ran shows it.** If you did not verify something, say so.
- **Tokens:** use grep -n, narrow reads, and `tail` on long logs.
- **Budget:** stop at the budget note, leaving a committed, consistent state.
- **Report:** keep it brief, with numbers.
- Test data: email addresses only on example.com / example.org (the public export audit rejects any other domain).

**Work in few steps** (each step costs model time):
- Write all probe programs first, then run them together with one command, for example a loop over `bash ~/tools/cmp.sh`, instead of one command per program.
- Search only inside the repository (`grep -rn ... AIL_CURRENT tools`), never across `/home` or `/tmp`.
- Read a file once, using a range that is large enough, instead of many small reads.
- Do not re-run a test that already passed unless you changed code since.

**Where you run:** a GitHub Actions runner (4 cores). Commit your work on the current branch; do not push.

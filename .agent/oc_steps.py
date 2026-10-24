# oc_steps.py LOG: where an OpenCode run spent its time. Prints the slowest tool calls (seconds, tool, command) and totals.
import json, sys
rows, total = [], {}
for line in open(sys.argv[1], encoding='utf-8', errors='replace'):
    try:
        e = json.loads(line)
    except ValueError:
        continue
    p = e.get('part') or {}
    if p.get('type') != 'tool':
        continue
    st = p.get('state') or {}
    t = st.get('time') or {}
    if not (t.get('start') and t.get('end')):
        continue
    sec = (t['end'] - t['start']) / 1000
    inp = st.get('input') or {}
    what = inp.get('command') or inp.get('filePath') or inp.get('pattern') or ''
    rows.append((sec, p.get('tool', '?'), str(what).replace('\n', ' ')[:110]))
    total[p.get('tool', '?')] = total.get(p.get('tool', '?'), 0) + sec
print('tool time:', ', '.join(f'{k} {v/60:.1f} min' for k, v in sorted(total.items(), key=lambda x: -x[1])))
for sec, tool, what in sorted(rows, reverse=True)[:8]:
    print(f'{sec:7.0f}s {tool:6} {what}')

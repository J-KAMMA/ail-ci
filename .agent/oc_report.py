# oc_report.py LOG: final text and usage from an OpenCode `run --format json` event stream
import json, sys
text, tokens, cost = [], {}, 0.0
for line in open(sys.argv[1], encoding='utf-8', errors='replace'):
    try:
        e = json.loads(line)
    except ValueError:
        continue
    part = e.get('part') or {}
    if part.get('type') == 'text' and part.get('text'):
        text.append(part['text'])
    if part.get('type') == 'step-finish':
        cost += part.get('cost') or 0
        for k, v in (part.get('tokens') or {}).items():
            if isinstance(v, (int, float)):
                tokens[k] = tokens.get(k, 0) + v
            elif isinstance(v, dict):
                for k2, v2 in v.items():
                    tokens[k + '.' + k2] = tokens.get(k + '.' + k2, 0) + (v2 or 0)
print(text[-1] if text else '(no final text)')
print('[cost $%.4f, opencode tokens %s]' % (cost, json.dumps(tokens)))

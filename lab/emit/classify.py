#!/usr/bin/env python3
"""Sub-classify the `other` instruction class from analyze.py's per-line dump.

attrib.py (lab/roof) splits emitted-line Ir into overflow, bounds, refcount,
alloc/free, copies and boxing; the remainder (`other`) is the shape of the
emitted code.  This script measures that shape and writes data/causes.json.

    python3 lab/emit/classify.py                    # reads data/lines.json
    python3 lab/emit/classify.py --lines /tmp/l.json

Every row is one emitted program.c line with its callgrind Ir, so a cause's Ir
is the sum of the lines assigned to it, not an estimate.  The hand-edit bounds
in bounds.py say what removing a construct is worth; this says where the
instructions currently are.

The assignment is two-level.  A line is first given attrib.py's check class
(overflow, bounds, refcount, alloc/free, copies, boxing) if one matches.  Else,
if the line is inside an emitted runtime helper, it takes that helper's role by
function name.  Else (inside user code: py_main, pack, readvar, ev__d, ...) it
is classed by line shape: call-frame prologue/epilogue, one-statement-per-op
temporaries, a call to a generic helper, a width conversion, or loop control.
"""
import argparse
import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
sys.path.insert(0, str(REPO / 'lab' / 'roof'))
sys.path.insert(0, str(HERE))
import attrib  # noqa: E402
import analyze  # noqa: E402

TASKS = ['ticket_audit', 'echo_pack', 'tree_fold', 'ledger_bin', 'tally_lang', 'berth_sim']

# A generated runtime helper's role, by name.  Ordered: first match wins.  gcc suffixes
# .isra/.constprop/.part; the name is normalised first.  These are the emitted helpers that
# carry the `other` Ir.
ROLES = [
    ('overflow-helper', re.compile(r'^(ck_|ail_int_)')),
    ('container-invariant', re.compile(
        r'^(ail_blist_meta|ail_stab_check|ail_sdict_check|ail_list_check|ail_slist_check|'
        r'ail_idict_check|ail_sset_check|ail_tab_check|ail_pslist_check|ail_blist_index|'
        r'ail_blist_add|ail_blist_payload|ail_bsplit_span|ail_bytes_decode_utf8|'
        r'ail_utf8_decode_error|ail__need_elems|ail__bcap|ail_list_span_len)$')),
    ('list-helper', re.compile(
        r'^(ail_blist|ail_list|ail_slist|ail_pslist|ail__bpay|ail__blist_|ail__bl_|ail_perm_apply|'
        r'ail_numfield|ail_list_span|ail_bsplit)')),
    ('dict-table-helper', re.compile(
        r'^(ail_sdict|ail_idict|ail_tab|ail_stab|ail_sset|ail_shash|ail_hash|ail_keysort|'
        r'ail__keysort|ail__key_|AIL_KEYSORT|AIL_NUMFIELD|AIL_)')),
    ('byte-string-helper', re.compile(
        r'^(ail__utf8_validate|ail_utf8_decode_error|ail_bytes_to_int|ail_bytes_get|ail_bytes_eq|'
        r'ail__str_|ail_str_|ail_bytearray_|ail_stdin_readline|ail_view|ail_slice|ail_bt_|'
        r'ail_str_to_int|ail_bsplit_span|ail_cleanup)')),
    ('allocator', re.compile(r'^(ail_sarena|ail_barena|ail_alloc|ail__blk_|ail_free)')),
    ('exception-unwind', re.compile(r'^(ail_raise|ail_exception|ail_die|ail_frame)')),
]

# Inside user-code functions (py_main, pack, readvar, ev__d, ...) classify each emitted line.
USER_RULES = [
    ('call-frame (prologue/epilogue)', re.compile(
        r'^[A-Za-z_][\w \t\*]*\b\w+\s*\([^;{]*\)\s*\{\s*$|^\}\s*$')),
    ('recursion-depth-guard', re.compile(r'AIL_MAX_RECURSION_DEPTH')),
    ('exception-unwind', re.compile(
        r'\bail_ir_try\b|AIL_IR_EXC|ail_exc_code|ail_cleanup_top|ail_unwind|ail_pending')),
    ('temporaries/one-statement', re.compile(r'\b(v__t\d+|ir\d+|_r\d+|_key|_value|_argument|_index)\b')),
    ('call-to-generic-helper', re.compile(
        r'\bail_(bytes_to_int|str_catn|str_from_int|list_span_get|list_span_len|blist_view|'
        r'list_pop|pslist_at|pslist_push|slist_push|idict_|sdict_|sset_|tab_|need_elems|'
        r'bytes_get|decode_utf8|key)\b|ck_(add|sub|mul|shl|div|mod)')),
    ('width/int-float conversion', re.compile(
        r'\((int64_t|uint64_t|int32_t|uint32_t|uintmax_t|size_t|double|int|char|uint8_t)\)')),
    ('loop/condition', re.compile(r'^(if|for|while|switch)\b')),
    ('other-user-lines', re.compile(r'.')),
]

CK = [name for name, _ in attrib.CATS]
CAUSES = CK + [n for n, _ in ROLES] + [n for n, _ in USER_RULES]


def check_class(text):
    """attrib.py's check category of a line, or None."""
    for name, _ in attrib.CATS:
        if attrib.classify(text, name):
            return name
    return None


def role_of(fn):
    base = re.sub(r'(\.isra|\.constprop|\.part|\.cold)(\.\d+)*$', '', fn)
    for name, rx in ROLES:
        if rx.search(base):
            return name
    return None


def classify(ail_rows, c_rows, c_ranges):
    out = {name: 0 for name in CAUSES}
    for row in ail_rows:
        text, fn, ir = row['text'], row['fn'], row['ir']
        ck = check_class(text)
        if ck:
            out[ck] += ir
            continue
        role = role_of(fn)
        if role:
            out[role] += ir
            continue
        if fn in ('?', '__attribute__'):
            # Macro-generated helpers (AIL_KEYSORT_*, AIL_NUMFIELD_*) have no DWARF function
            # name for their expanded lines; assign by what the line touches.
            if re.search(r'\bk\[|AIL_KEY|\brev\b|ail__keysort|ail_hash', text):
                out['dict-table-helper'] += ir
            elif re.search(r'L->|data\[index\]|index < .*count|T->used|T->ent|T->cap', text):
                out['list-helper' if 'T->' not in text else 'dict-table-helper'] += ir
            else:
                out['other-user-lines'] += ir
            continue
        for name, rx in USER_RULES:
            if rx.search(text):
                out[name] += ir
                break
    c_by_fn = {}
    for row in c_rows:
        for (first, last, name) in c_ranges:
            if first <= row['line'] <= last:
                c_by_fn[name] = c_by_fn.get(name, 0) + row['ir']
                break
    return out, c_by_fn


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--lines', default=str(HERE / 'data' / 'lines.json'))
    ap.add_argument('--out', default=str(HERE / 'data' / 'causes.json'))
    ap.add_argument('--top', type=int, default=10)
    args = ap.parse_args()
    data = json.loads(Path(args.lines).read_text())
    result = {'method': {'lines': str(args.lines),
                         'checks': 'lab/roof/attrib.py CATS on the line text',
                         'roles': 'function name, then line shape inside user functions'},
              'tasks': {}}
    for task in data['tasks']:
        if task not in TASKS:
            continue
        ail_rows = data['tasks'][task]['ail']
        c_rows = [r for r in data['tasks'][task]['c'] if r['ir']]
        csrc = REPO / 'lab' / 'compare' / 'src' / task / 'main.c'
        c_ranges = analyze.func_ranges(csrc)
        causes, c_by_fn = classify(ail_rows, c_rows, c_ranges)
        total = sum(r['ir'] for r in ail_rows)
        ctotal = sum(r['ir'] for r in c_rows)
        funcs = {}
        for r in ail_rows:
            funcs[r['fn']] = funcs.get(r['fn'], 0) + r['ir']
        top = sorted(funcs.items(), key=lambda kv: -kv[1])[:args.top]
        ctop = sorted(c_by_fn.items(), key=lambda kv: -kv[1])[:args.top]
        result['tasks'][task] = {
            'ail': total, 'c': ctotal, 'extra': total - ctotal,
            'causes': causes,
            'top_emitted': [[n, ir] for n, ir in top],
            'top_c': [[n, ir] for n, ir in ctop],
        }
        print('==', task, 'ail', total, 'c', ctotal, 'extra', total - ctotal)
        for k, v in sorted(causes.items(), key=lambda kv: -kv[1]):
            if v:
                print('   %-32s %14d  %5.1f%% of AIL  %5.1f%% of extra'
                      % (k, v, 100.0 * v / total, 100.0 * v / max(1, total - ctotal)))
        print('   top:', top[:6])
        print('   top C:', ctop[:6])
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result, indent=1) + '\n')
    print('wrote', out)


if __name__ == '__main__':
    main()

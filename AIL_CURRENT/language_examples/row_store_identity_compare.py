"""Research-only same-pointer stores for generated local slots; no adoption."""
import argparse
from contextlib import redirect_stdout
import io
import json
from pathlib import Path
import re
import signal
import subprocess
import struct
import sys

import row_locals_compare as compare

HERE = Path(__file__).resolve().parent
CURRENT = HERE / 'integer_row_stream.ail'
DEFINITION = re.compile(r'static (?P<type>ail_obj_\w+) \*ail_obj_store_(?P<name>(?!local_)\w+)\((?P=type) \* volatile \*slot, (?P=type) \*value, int adopt\) \{\n(?P<body>.*?)\n\}', re.S)
BODY = '    if (!adopt) ail_obj_retain(value);\n    ail_obj_release(*slot);\n    *slot = value;\n    return value;'
LOCAL_CALL = re.compile(r'\bail_obj_store_((?!local_)\w+)\(&([A-Za-z_]\w*)\s*,')
PROBE_SOURCE = '''use integer_row_stream;
struct Holder {item:IntegerRowStreamState;}
fn main()->int {
 let state=IntegerRowStreamState(1,0,0,b"");
 let holder=Holder(state);holder.item=state;return 0;
}
'''
PROBE_MAIN = r'''
#undef main
#include <inttypes.h>
static unsigned drops, drop_slot_old, drop_newrefs;
static ail_obj_IntegerRowStreamState * volatile *watched_slot;
static ail_obj_IntegerRowStreamState *new_value;
static void probe_drop(void *value) {
 drops++;
 if(watched_slot) {
  drop_slot_old=(*watched_slot==value);
  drop_newrefs=new_value?(unsigned)new_value->_ail_header.refs:0;
 }
}
static ail_obj_IntegerRowStreamState *make_value(size_t refs) {
 ail_obj_IntegerRowStreamState *value=calloc(1,sizeof *value);
 if(!value)abort();value->_ail_header.refs=refs;value->_ail_header.drop=probe_drop;return value;
}
int main(int argc,char **argv) {
 if(argc!=4)return 99;
 int mode=atoi(argv[1]),adopt=atoi(argv[2]);
 size_t refs=(size_t)strtoumax(argv[3],NULL,10);
 ail_obj_IntegerRowStreamState *old=NULL,*value=NULL,* volatile slot=NULL,*result;
 ail_obj_Holder holder={0};
 if(mode==0 || mode==5) {old=value=make_value(refs);slot=old;}
 else if(mode==1) {old=make_value(refs);value=make_value(1);slot=old;}
 else if(mode==2 || mode==6) {value=make_value(1);}
 else if(mode==3) {old=make_value(refs);slot=old;}
 else if(mode!=4)return 99;
 if(mode==5) {IDENTITY_STORE((ail_obj_IntegerRowStreamState * volatile *)(uintptr_t)1,value,0);return 98;}
 watched_slot=&slot;new_value=value;
 if(mode==6) {
  watched_slot=&holder.f_item;
  result=ail_obj_store_IntegerRowStreamState(&holder.f_item,value,adopt);
  slot=holder.f_item;
 } else result=IDENTITY_STORE(&slot,value,adopt);
 size_t newrefs=value?value->_ail_header.refs:0;
 size_t oldrefs=old?(old==value?newrefs:(drops?0:old->_ail_header.refs)):0;
 printf("{\"refs\":%zu,\"oldrefs\":%zu,\"drops\":%u,\"slot\":%u,\"result\":%u,\"drop_slot_old\":%u,\"drop_newrefs\":%u}\n",
        newrefs,oldrefs,drops,(unsigned)(slot==value),(unsigned)(result==value),drop_slot_old,drop_newrefs);
 int old_live=old && old!=value && !drops;
 watched_slot=NULL;new_value=NULL;
 if(value) {value->_ail_header.refs=1;ail_obj_release(value);}
 if(old_live) {old->_ail_header.refs=1;ail_obj_release(old);}
 return 0;
}
'''


def patch_local_stores(code):
    originals = list(DEFINITION.finditer(code))
    if not originals:
        raise ValueError('managed store definitions missing')
    for match in originals:
        if match['body'] != BODY:
            raise ValueError('managed store body changed: ' + match['name'])
        declaration = f"static {match['type']} *ail_obj_store_{match['name']}({match['type']} * volatile *, {match['type']} *, int);\n"
        if code.count(declaration) != 1:
            raise ValueError('managed store forward declaration changed')
        code = code.replace(declaration, declaration + declaration.replace('ail_obj_store_', 'ail_obj_store_local_', 1), 1)
    def clone(match):
        helper = match[0].replace('ail_obj_store_', 'ail_obj_store_local_', 1)
        guard = ('    if (!adopt && value) {\n'
                 '        ail_obj_header *h = (ail_obj_header *)value;\n'
                 '        if (!h->refs || h->refs == SIZE_MAX) abort();\n'
                 '        if (*slot == value) { *slot = value; return value; }\n'
                 '    }\n')
        helper = helper.replace(BODY, guard + BODY, 1)
        return match[0] + '\n' + helper
    code = DEFINITION.sub(clone, code)
    code = LOCAL_CALL.sub(lambda match: 'ail_obj_store_local_' + match[1] + '(&' + match[2] + ',', code)
    # Original definitions and every complex field/slot call must remain exact.
    if [match[0] for match in DEFINITION.finditer(code)] != [match[0] for match in originals]:
        raise ValueError('original managed store definitions changed')
    return code


def static_counts(code):
    simple = len(LOCAL_CALL.findall(code))
    calls = re.findall(r'\bail_obj_store_(?!local_)(\w+)\(&([^\n,]+),', code)
    complex_calls = [slot for _, slot in calls if not re.fullmatch(r'[A-Za-z_]\w*', slot.strip())]
    return dict(original_local_calls=simple, local_fast_calls=len(re.findall(r'\bail_obj_store_local_\w+\(&', code)),
                original_complex_calls=len(complex_calls), original_field_calls=sum('->' in slot or '.' in slot for slot in complex_calls),
                original_definitions=len(DEFINITION.findall(code)),
                local_definitions=len(re.findall(r'static ail_obj_\w+ \*ail_obj_store_local_\w+\([^;]+\) \{', code)))


def probes(work, variants, gcc, rustc, report, generated):
    maximum = (1 << (8 * struct.calcsize('P'))) - 1
    cases = []
    def expected(refs, oldrefs=0, drops=0, drop_slot_old=0, drop_newrefs=0):
        return dict(refs=refs, oldrefs=oldrefs, drops=drops, slot=1, result=1,
                    drop_slot_old=drop_slot_old, drop_newrefs=drop_newrefs)
    for refs in (1, 2, maximum - 1):
        cases.append(('alias_' + str(refs), 0, 0, refs, expected(refs, refs)))
    cases.append(('alias_adopt', 0, 1, 2, expected(1, 1)))
    for refs in (0, maximum):
        cases.append(('poison_invalid_' + str(refs), 5, 0, refs, None))
    for adopt in (0, 1):
        retained = 2 - adopt
        for oldrefs in (1, 2):
            drops = int(oldrefs == 1)
            cases.append(('nonalias_' + str(adopt) + '_' + str(oldrefs), 1, adopt, oldrefs,
                          expected(retained, oldrefs - 1, drops, drops, retained if drops else 0)))
            cases.append(('to_null_' + str(adopt) + '_' + str(oldrefs), 3, adopt, oldrefs,
                          expected(0, oldrefs - 1, drops, drops)))
        cases.extend([('from_null_' + str(adopt), 2, adopt, 0, expected(retained)),
                      ('null_null_' + str(adopt), 4, adopt, 0, expected(0)),
                      ('field_null_' + str(adopt), 6, adopt, 0, expected(retained))])
    results = {}
    for variant, directory in variants.items():
        source = directory / 'identity_probe.ail'
        source.write_text(PROBE_SOURCE, encoding='utf8')
        code = generated(source)
        counts = static_counts(code)
        if counts['original_field_calls'] < 1:
            raise ValueError('probe field path missing or patched')
        helper = 'ail_obj_store_' + ('local_' if variant == 'candidate' else '') + 'IntegerRowStreamState'
        code = '#define main original_probe_main\n' + code + '\n#define IDENTITY_STORE ' + helper + '\n' + PROBE_MAIN
        binary = compare.build(work, 'identity_probe_' + variant, code, gcc, rustc, report)
        results[variant] = []
        report['identity_probes'] = results
        for name, mode, adopt, refs, wanted in cases:
            process = subprocess.run([str(binary), str(mode), str(adopt), str(refs)], cwd=work, capture_output=True, timeout=30)
            actual = compare.observed(process)
            if wanted is None:
                passed = process.returncode == -signal.SIGABRT and not process.stdout
            else:
                try:
                    payload = json.loads(process.stdout)
                except (ValueError, UnicodeError):
                    payload = None
                passed = process.returncode == 0 and process.stderr == b'' and payload == wanted
            item = dict(case=name, passed=passed, expected=wanted, expected_signal='SIGABRT' if wanted is None else None, actual=actual)
            results[variant].append(item)
            if not passed:
                raise ValueError('store identity probe failed: ' + variant + '/' + name)
    if [(item['case'], item['actual']) for item in results['baseline']] != [(item['case'], item['actual']) for item in results['candidate']]:
        raise ValueError('store identity probe observations differ')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists() or args.output.is_symlink():
        raise ValueError('fresh JSON output required')
    watched = [Path(__file__), Path(compare.__file__)]
    before = {str(path): compare.row.pin(path) for path in watched}
    original_generated = compare.row.generated
    original_private = compare.private_controls
    original_argv = sys.argv[:]
    counts = []
    def generated(path, *positional, **keywords):
        code = original_generated(path, *positional, **keywords)
        prior = static_counts(code)
        candidate = Path(path).parent.name == 'candidate_sources'
        if candidate:
            complex_before = re.findall(r'\bail_obj_store_\w+\(&([^\n,]*(?:->|\.)[^\n,]*),', code)
            code = patch_local_stores(code)
            complex_after = re.findall(r'\bail_obj_store_(?!local_)\w+\(&([^\n,]*(?:->|\.)[^\n,]*),', code)
            if complex_before != complex_after:
                raise ValueError('complex/field call paths changed')
        counts.append(dict(source=str(path), candidate=candidate, before=prior, after=static_counts(code),
                           generated_sha256=compare.digest(code.encode())))
        return code
    def private(work, variants, gcc, rustc, report):
        original_private(work, variants, gcc, rustc, report)
        probes(work, variants, gcc, rustc, report, generated)
    try:
        compare.row.generated = generated
        compare.private_controls = private
        sys.argv = [str(Path(__file__)), '--output', str(args.output), '--candidate', str(CURRENT)]
        with redirect_stdout(io.StringIO()):
            status = compare.main()
    finally:
        compare.row.generated = original_generated
        compare.private_controls = original_private
        sys.argv = original_argv
    report = json.loads(args.output.read_text(encoding='utf8'))
    report.update(research='local same-pointer non-adopt store fast path', static_call_counts=counts,
                  local_slot_profile='single thread; normally generated local pointer slots only',
                  unqualified_slot_profiles=['MMIO', 'invalid slots with valid headers', 'synchronous signal mutation', 'concurrent mutation'],
                  source_profile='baseline and candidate use identical current standard module/main; candidate generated C local-call patch only',
                  prior_sample_price=dict(run='37912208329', job='113759790104', head='dff971b', status='QUALIFIED',
                      runtime_sha256='780cb52ce3410bd4808367febf5188d0c577ccde71855c6c3140a8410d40f155',
                      rows=65537, cols=17, rc_samples=974, total_samples=4681,
                      sampled_all_rc_cpu_fraction=974/4681, process_cpu_over_wall=0.8167733,
                      estimated_all_rc_wall_share=0.16995026182844836,
                      ideal_all_rc_zero_cost_amdahl=1.204747, all_rc_half_cost_amdahl=1.092866,
                      current_over_c=dict(median=0.844048, interval=[0.836280, 0.859621]),
                      current_over_rust=dict(median=1.397965, interval=[1.373323, 1.424734]),
                      local_slot_wall_share=None, physical_roof_measured=False,
                      assumed_physical_roof_fraction=None,
                      scope='qualified runner-specific sampled RC attribution; all-RC upper bound only; local-slot guard cost unisolated; no causal or physical-roof claim',
                      baseline_scope='current codec-integrated compiler; distinct from historical R774 baseline'),
                  identity_script_pins_before=before, identity_script_pins_after={str(path): compare.row.pin(path) for path in watched})
    if report['identity_script_pins_before'] != report['identity_script_pins_after']:
        report.update(status='FAILED', quality_passed=False, beats_c_and_rust=False, failure='identity script/source changed')
        report.pop('paired_summary', None)
        status = 1
    args.output.write_text(json.dumps(report, indent=2) + '\n', encoding='utf8')
    print(json.dumps({key: report[key] for key in ('status', 'quality_passed', 'beats_c_and_rust', 'memory_measurement')}))
    return status


if __name__ == '__main__':
    raise SystemExit(main())

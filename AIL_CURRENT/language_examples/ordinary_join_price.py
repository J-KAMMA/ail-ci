"""Requested-memory and coarse copy cost for an ordinary immediate join return."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import tempfile
import time
import sys
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT),str(ROOT/'python/pkg-v12')]
from pyfunc import to_c
from test_ail_owned_join_take import OwnedJoinTakeTests
from record_report_profile import HEADER
SOURCE='''def run(n: int) -> str:
    words: list[str] = ["abcd" for i in range(n)]
    return "|".join(words)
'''

def main():
    parser=argparse.ArgumentParser();parser.add_argument('output',type=Path);args=parser.parse_args()
    if args.output.exists():raise FileExistsError(args.output)
    generated=OwnedJoinTakeTests().generated(SOURCE)
    anchor='static ail_str ail_str_return_owned(ail_str s) {'
    if generated.count(anchor)!=1:raise ValueError('owned copy boundary changed')
    begin=generated.index(anchor);end=generated.index('\n}',begin)+2
    original=generated[begin:end].replace(anchor,'static ail_str copy_raw(ail_str s) {')
    wrapper='''static uint64_t copy_ns,copy_alloc,copy_requested;
static ail_str ail_str_return_owned(ail_str s) {
 uint64_t a=resource_alloc_calls[6],b=resource_alloc_bytes[6],start=profile_now();
 ail_str out=copy_raw(s);copy_ns+=profile_now()-start;
 copy_alloc+=resource_alloc_calls[6]-a;copy_requested+=resource_alloc_bytes[6]-b;return out;
}
'''
    generated=generated[:begin]+original+wrapper+generated[end:]
    host=r'''
#undef malloc
#undef calloc
#undef realloc
#undef free
#undef memcpy
#undef memmove
#undef memset
int main(void) {
 uint64_t start=profile_now();ail_str value=run(262145);
 uint64_t body_ns=profile_now()-start;
 fprintf(stderr,"COST %llu %llu %llu %llu %zu %zu %lld\n",(unsigned long long)body_ns,
 (unsigned long long)copy_ns,(unsigned long long)copy_alloc,(unsigned long long)copy_requested,
 peak_bytes,live_bytes,(long long)value.n);
 for(int64_t i=0;i<value.n;i++)fputc((int)ail_chr(value,i),stdout);
 resource_free((void*)value.p);DRAIN
 if(live||live_bytes)return 4;return 0;
}
'''
    drain='for(int64_t i=0;i<ail__blk_cache_n;i++)resource_free(ail__blk_cache[i].p);ail__blk_cache_n=0;ail__blk_cache_bytes=0;' if 'ail__blk_cache_n' in generated else ''
    drain += ('for(int j=0;j<ail__ba_cache_n;j++){resource_free(ail__ba_cache[j]->p);resource_free(ail__ba_cache[j]);}ail__ba_cache_n=0;' if 'ail__ba_cache_n' in generated else '')  # parked bytearrays (cruntime ail__ba_cache)
    allocator=(ROOT/'language_examples/numeric_pipeline_allocator.c').read_text()
    code=HEADER+allocator+generated+host.replace('DRAIN',drain)
    watched=[ROOT/'python/pkg-v12/pyfunc.py',ROOT/'python/pkg-v12/cruntime.py',Path(__file__)]
    pins={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in watched}
    with tempfile.TemporaryDirectory(prefix='ail-join-price-') as folder:
        source=Path(folder)/'price.c';binary=Path(folder)/'price'
        source.write_text(code)
        command=['gcc','-std=gnu11','-O2',str(source),'-lm','-o',str(binary)]
        built=subprocess.run(command,capture_output=True,timeout=120)
        if built.returncode:raise RuntimeError(built.stderr.decode()[-2000:])
        start=time.perf_counter_ns();result=subprocess.run([str(binary)],capture_output=True,timeout=120);wall=time.perf_counter_ns()-start
        expected='|'.join(['abcd']*262145).encode()
        if result.returncode or result.stdout!=expected:raise ValueError('independent whole output differs')
        _,body,copy,alloc,requested,peak,retained,length=result.stderr.decode().split()
        fraction=int(copy)/wall
        report=dict(status='measured_memory',whole_output_equal=True,wall_ns=wall,body_ns=int(body),copy_ns=int(copy),copy_allocations=int(alloc),copy_requested_bytes=int(requested),requested_peak_bytes=int(peak),returned_live_bytes=int(retained),units=int(length),copy_wall_share=fraction,conditional_copy_amdahl=1/(1-fraction),timing_qualified=False,physical_roof_measured=False,roof_fraction_assumed=None,roof_fraction_achieved=None,projection_reason='memory request removal only; no speedup projection or C/Rust advantage',cleanup_live_bytes=0,source_sha256=hashlib.sha256(code.encode()).hexdigest(),command=command,pins_before=pins,pins_after={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in watched})
        if report['pins_before']!=report['pins_after']:raise ValueError('source changed')
    args.output.write_text(json.dumps(report,indent=2));print(json.dumps(report))

if __name__=='__main__':main()
import sys, subprocess, tempfile
from pathlib import Path
REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / 'lab/compare')); import run_task
for t in sys.argv[1:] or 'berth_sim chain_relax echo_pack ledger_bin rail_transfer scar_life tally_lang term_rank ticket_audit tree_fold'.split():
    work = Path(tempfile.mkdtemp(prefix='a2p-')); conv = work / 'main.py'
    subprocess.run([sys.executable, '-B', str(REPO / 'tools/ail2py.py'), str(REPO / f'lab/compare/src/{t}/main.ail'),
                    '-o', str(conv)], check=True)
    run_task.CURRENT_TASK = t
    check = run_task.make_check_cases(t, work); expected = run_task.reference_outputs(t, check, work)
    env_cmd = [sys.executable, '-B', str(conv)]
    bad = []
    for kind, name, case in check:
        out = work / 'o.out'
        p = run_task.exec_prog([], env_cmd, case, out, 60)    # PYTHONPATH must contain AIL_CURRENT (for ail.py)
        if (p.returncode, out.read_bytes()) != expected[(kind, name)]:
            bad.append(f'{kind}/{name}')
    print(t, 'cases', len(check), 'mismatches', len(bad), bad[:3])

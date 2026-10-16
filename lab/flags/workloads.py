"""Program list for the flags study: the public bench/apps plus small public programs in programs/.

build_spec() returns dict(source, options, prepare, case) where case = {args, expected_stdout?,
expected_file?}. Inputs are deterministic (fixed seeds)."""
import importlib.util, random
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
APPS = ['binary_cursor_records', 'binary_search', 'csv_table', 'json_query', 'numeric_scale_binary']
SMALL = ['sieve', 'collatz', 'nbody_lite', 'lcg_hash']


def _load_app(name):
    spec = importlib.util.spec_from_file_location('app_' + name, REPO / 'bench/apps' / (name + '.py'))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def names():
    return APPS + SMALL + ['text_count']


def build_spec(name, work, smoke):
    work = Path(work)
    work.mkdir(parents=True, exist_ok=True)
    root = REPO / 'AIL_CURRENT'
    if name in APPS:
        app = _load_app(name)
        return dict(source=root / app.AIL_SOURCE, options=[o.replace('{work}', str(work)) for o in app.AIL_OPTIONS],
                    prepare=getattr(app, 'prepare_ail', None), case=app.generate(work, smoke))
    if name in SMALL:
        return dict(source=HERE / 'programs' / (name + '.ail'), options=[], prepare=None, case=dict(args=[]))
    if name == 'text_count':
        rnd = random.Random(7)
        words = ['alpha', 'beta', 'gamma', 'delta', 'epsilon', 'zeta', 'eta', 'theta', 'iota', 'kappa']
        n = 40000 if smoke else 1500000
        text = ' '.join(rnd.choice(words) for _ in range(n)) + '\n'
        (work / 'text.txt').write_text(text, encoding='utf8')
        (work / 'needle.txt').write_text('eta del', encoding='utf8')
        return dict(source=root / 'language_examples/text_count_main.ail', options=[], prepare=None,
                    case=dict(args=[str(work / 'text.txt'), str(work / 'needle.txt')]))
    raise KeyError(name)

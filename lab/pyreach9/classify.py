#!/usr/bin/env python3
"""Classify the strict-mode blockers of lab/pyreach9/census.jsonl into reason categories.

    python3 lab/pyreach9/classify.py [--dump]

For every general/refused program the census recorded the full blocker list from
`compile --strict --json` (strictmode.collect).  This script maps each blocker to a reason
with an ordered pattern list, then counts, per reason:

  programs   general/refused programs with at least one blocker of the reason
  sole       programs whose blocker list contains only that reason: removing it would let
             the program type, when the collected list is complete (the census records
             strict_incomplete; see RESULTS.md for the per-corpus caveat)
  blockers   blocker instances
  c/v/g      how many of those programs came from compare / vibe / gdev

A program whose strict collector produced nothing (a parse-stage refusal, or a script the
collector cannot enter) falls back to its default-path note / first refusal as one reason.
"""
import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
CENSUS = HERE / 'census.jsonl'

# Ordered rules: (category, regex over `construct :: why :: function`).  First match wins.
RULES = [
    ('int64-literal', r'int64 literal out of range|does not fit in a 64-bit signed integer|'
                      r'integer literal out of signed 64-bit|shifts beyond int64'),
    ('generated-prelude', r'\b_ail_|_AIL_|_AilArray|_AilDeque|_AilNT|_AilT_|_AilCSV|_AilIntEnum|'
                          r'AIL_ARRAY_PRELUDE|\bAilArray\b'),
    ('none-optional', r'the constant None|d\.get\(k\) with one argument|'
                      r'with one argument needs Optional|only a class type can be None|'
                      r'\bOptional\b|None for a missing key|\| None|None\]|'
                      r'returns? None|is None\b|\bNone\b.*(sentinel|null|holds one)'),
    ('generator-yield', r'^yield$|\byield\b|this language has no generators'),
    ('nested-def-in-loop', r'nested def inside a loop'),
    ('dict-of-containers', r'dict of containers|field `v` is a list or dict|a nested annotation|'
                           r'a tuple inside a tuple|is annotated dict\[|'
                           r'is a list\[list\[|nested list holds rows'),
    ('class-dunders', r'dunder method|print\(\) given a .* object|__init__ must|'
                      r'arithmetic on a class|has no __init__|must take plain positional|'
                      r'only __init__ is supported'),
    ('class-shape', r'decorator on|\bdecorator\b|multiple inheritance|\binheritance\b|'
                    r'names a base class|__dataclass_fields__|__mro__|class attribute|'
                    r'\bclassmethod\b|\bstaticmethod\b|\bproperty\b'),
    ('module-level-constant', r'module-level name assigned to a (Call|Constant|Attribute)|'
                              r'module-level (list|dict) of non-|module-level table|'
                              r'module-level dict that a function cannot read|'
                              r'is a module-level .* assigned|'
                              r'module-level name assigned'),
    ('unsupported-module', r"import of '|this compiler builds only the modules|"
                           r'is not available|module the typed path|'
                           r're module is built|'
                           r'itertools\.[a-z]+ (is )?not built|'
                           r'functools\.|json\.(loads|dumps|dump|JSONEncoder)|'
                           r'statistics\.|tempfile\.|with .* as |'
                           r'reduce, lru_cache|'
                           r'Counter|OrderedDict|defaultdict'),
    ('unsupported-builtin', r'call to (set|min|max|dict|next|isinstance|enumerate|sorted|sum|len|'
                           r'zip|map|filter|any|all|abs|str|int|float|bytes|list|tuple|range|open|'
                           r'input|type|super|id|hash|repr|print|divmod|pow|round|format|chr|ord|'
                           r'hex|bin|oct|callable|iter|reversed|globals|locals|vars|getattr|'
                           r'setattr|hasattr|delattr|compile|eval|exec|fn)\(\)'),
    ('tuple-unpack', r'a tuple target over|tuple assignment (from|to)|a pair target|'
                     r'tuple target over|a tuple used where a single value|cannot be walked inline'),
    ('bytes-str-methods', r'a bytes has no method|bytes\.translate|\.hex\(\)|'
                          r'\.decode\(\)|bytes\.maketrans|has no method .*'
                          r'(isdigit|lstrip|strip|index|append|decode)'),
    ('slice-for-number', r'slice used where a single number|a slice is a str or bytes value'),
    ('bytes-sequence-param', r'wants a sequence|passing a bytes where|passing Subscript where'),
    ('mixed-return-kind', r'returns? .* on one path and|returning a tuple, but this function returns|'
                          r'returning a dict, but this function returns|no return path used a shape|'
                          r'never returns a value|return annotation .* disagrees'),
    ('mixed-container', r'appended both a str and a non-str|list or dict that gets the bool|'
                        r'mixes bools and numbers|a list holds integers|'
                        r'numeric binding requires a number|assigning (dict|int|str) is unsupported|'
                        r'is declared (int|bool|str|flist)|'
                        r"declared (int|bool|str|flist)$|a list of str holds one kind|"
                        r"requires (str|int|bytes)$|string list field append requires str|"
                        r'field list\[bool\]|is appended both'),
    ('numeric-kind', r'list\[float\] accepts only float|declared list\[float\]|'
                     r'sum\(\) over a list of floats|is annotated list\[float\] in the source|'
                     r'declared flist'),
    ('generic-annotation', r"is annotated (list\[T\]|Type\[|Any|BaseException|int \| tuple|"
                          r"callable|tuple\[str, \.\.\.\]|re\.Match|dict\[str, Any\])|"
                          r"annotated `?Any|annotated object"),
    ('parameter-readonly', r'is a parameter and cannot be reassigned|list parameter, which is read-only|'
                           r'typed dict.*parameters are read-only|typed dict and set parameters are read-only|'
                           r'typed dict parameters are read-only'),
    ('annotation-caller-conflict', r'in the source, but the caller also supplies|is declared int'),
    ('value-kind-lost', r'subscripting (a )?(int|Subscript|Attribute)|a method on (Call|Subscript)|'
                        r"'[^']+' used as a value|field '[^']+' requires a class instance|"
                        r'an int has no method|a str has no method|a float has no method|'
                        r'is a (2-tuple|sdict|sset)|typed dict comparisons|'
                        r'typed dict requires a str key|an unannotated dict literal'),
    ('buffer-io', r'sys\.stdin\.buffer|sys\.stdout\.buffer|sys\.stdin\.buffer\.readline|'
                  r'only sys\.stdin'),
    ('str-number-compare', r'comparing a str with a number'),
    ('while-else', r'while-else'),
    ('key-argument', r'with key= columns|key= columns|key= is only supported'),
    ('exceptions', r'raise requires a built-in exception|bound exception name|exception value'),
    ('comprehension', r'comprehension'),
    ('records-annotation', r'records annotation'),
    ('str-number-concat', r'concatenating a number with a str'),
    ('tuple-holds', r'a tuple cannot hold|an empty tuple appended'),
]


def category(blocker):
    text = ((blocker.get('construct') or '') + ' :: ' + (blocker.get('why') or '') +
            ' :: ' + (blocker.get('function') or ''))
    for name, pat in RULES:
        if re.search(pat, text, re.I):
            return name
    return 'other'


def fallback_category(rec):
    text = (rec.get('default_note') or '') + ' :: ' + (rec.get('strict_first') or '') + \
        ' :: ' + (rec.get('default_first') or '')
    # A note carries the compiler's reason followed by explanatory "write instead"
    # prose.  The prose names unrelated constructs (it explains what to write, not
    # what the program does), so only the reason before it may pick the category.
    text = re.split(r'\bwrite instead\b|\bwrite_instead\b|; run with --strict', text)[0]
    for name, pat in RULES:
        if re.search(pat, text, re.I):
            return name
    if not text.strip():
        return 'no-reason-recorded'
    return 'other'


def load():
    return [json.loads(line) for line in CENSUS.open() if line.strip()]


def program_categories(rec):
    cats = [category(b) for b in (rec.get('strict_blockers') or [])]
    if not cats:
        cats = [fallback_category(rec)]
    return cats


def main():
    recs = load()
    dump = '--dump' in sys.argv
    counts = Counter()
    programs_in = defaultdict(list)
    sole = Counter()
    sole_programs = defaultdict(list)
    corpus_sole = defaultdict(Counter)
    corpus_all = defaultdict(Counter)
    for r in recs:
        if r['path'] == 'typed':
            continue
        cats = program_categories(r)
        uniq = set(cats)
        for c in cats:
            counts[c] += 1
        for c in uniq:
            programs_in[c].append(r['name'])
            corpus_all[c][r['corpus']] += 1
        if len(uniq) == 1:
            c = next(iter(uniq))
            sole[c] += 1
            sole_programs[c].append(r['name'])
            corpus_sole[c][r['corpus']] += 1
        if dump:
            print('%-8s %-9s %-50s %s' % (r['corpus'], r['path'], r['name'],
                                          ', '.join('%s%s' % (c, '' if cats.count(c) == 1 else 'x%d' % cats.count(c))
                                                    for c in sorted(uniq))))
    print()
    print('%-26s %5s %5s %6s  %s' % ('reason', 'progs', 'sole', 'blk', 'appears (c/v/g)'))
    order = sorted(counts, key=lambda c: (-sole[c], -len(programs_in[c]), c))
    for c in order:
        a = corpus_all[c]
        print('%-26s %5d %5d %6d  c%d/v%d/g%d' % (
            c, len(programs_in[c]), sole[c], counts[c], a['compare'], a['vibe'], a['gdev']))
    print('\nsole-category programs:')
    for c in sorted(sole, key=lambda c: -sole[c]):
        sp = corpus_sole[c]
        print('%-26s %d (c%d/v%d/g%d): %s' % (c, sole[c], sp['compare'], sp['vibe'], sp['gdev'],
                                              ', '.join(sole_programs[c])))


if __name__ == '__main__':
    main()

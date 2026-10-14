"""AIL IR (docs/design/IR_OWNERSHIP_DESIGN_v2.md), stage S0.

Modules:
  ir       types, values, instructions, regions, functions, programs, the op table
  effects  effect records, the runtime catalogue, per-function summaries
  text     printer and parser of the textual form (round-trippable)
  verify   the structural verifier
  lower    Python AST (as the legacy front end leaves it) -> IR, for the S0 subset
  emit_c   IR -> C for the S0 subset
  driver   the per-function switch (env AIL_IR) with fallback to the legacy emitter
"""

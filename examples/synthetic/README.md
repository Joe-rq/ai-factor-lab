# Synthetic example

This is the seam that lets the repository run without a data provider.

## What is synthetic

- 30 fields, generated from a fixed seed.
- Two fields lead next-day returns; one field is a negative control built to
  have no linear edge; one field is constant.
- Returns are generated once and stored; the simulator never looks ahead.

## Run it

```bash
uv run python examples/synthetic/run_demo.py
```

Useful flags:

```bash
--candidates 40        # fewer rows, same pipeline
--seed 7               # a different world
--db path/to/run.db    # keep the ledger
--report path/to/report.txt
```

The report is a view of the ledger, not the ledger itself. The database file
is the record.

## Expression language

```
expr := term (('+' | '-') term)*
term := ['+'] ['-'] ['rank('] field [')']
```

`rank(X)` is a rolling percentile over a 60-day window mapped to `[-1, 1]`.
Raw `X` uses the standardized value directly.

## Why the control matters

`rank(f_29)` must not be recognized. If it is, the harness is not
discriminating and the demo exits non-zero. See
[`docs/positive-controls.md`](../../docs/positive-controls.md).

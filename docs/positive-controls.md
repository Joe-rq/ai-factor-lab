# Positive controls

## The principle

A gate that never fires is indistinguishable from a gate that does not exist.
A test suite that only checks the happy path will pass forever, including
after the gate has been disconnected.

A positive control is a pair of inputs with known, different expected outputs:

- one input that **must** make the gate fire;
- one input that **must not**.

If both produce the same answer, the gate is broken. This catches the two
degenerate failures: always-pass and always-fail.

## What the demo uses

The synthetic world contains a field (`f_29`) that is orthogonalized against
realized future returns. A linear expression over it has no edge by
construction. The demo includes `rank(f_29)` as a named negative control and
asserts that it is **not** recognized.

It also includes `rank(f_28)`, where `f_28` is constant. Its signal has zero
variance, so Sharpe is undefined. The expected result is
`operational_error` — not `no_value`. This is the control for the
"missing measurement" path: if a constant feed were classified as a failed
value gate, the system would be lying about what it measured.

The demo exits non-zero if the negative control is recognized.

## Writing a control

A useful control has three properties:

1. **A known answer.** "Probably bad" is not a control. The synthetic control
   is orthogonal by construction.
2. **A distinct expected status.** One control should pass and one should
   fail; otherwise a constant gate passes the test.
3. **A recorded trace.** The demo prints the rationale, so a reader can see
   which gate fired and on what value.

## Failure modes this catches

| Failure | What the control shows |
|---|---|
| Gate always passes | Negative control is recognized |
| Gate always fails | Known positive is not recognized |
| Gate reads missing data as zero | Constant field becomes `no_value`, not `operational_error` |
| Classifier collapses classes | `effective_negative` and `no_value` become one bucket |
| Rule changed after the run | Prereg digest in the report no longer matches the plan |

## What it does not catch

A control cannot tell you whether the thresholds are sensible. A world built
to make the positive control pass proves the plumbing, not the research. That
distinction is the reason the third verification layer exists.

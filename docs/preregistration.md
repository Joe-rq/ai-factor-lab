# Preregistration

## The problem

A rule written after seeing the data will fit the data. That is not a moral
failure; it is what rules do. The only defense is to write the rule down
before the run and make it expensive to pretend otherwise.

This repository does not prevent a researcher from changing their mind. It
makes the change visible: a new rule has a new digest, and a new digest is a
new plan.

## What a rule contains

```json
{
  "hypothesis": "A signal built from a field that leads next-day returns can clear a 2.0 Sharpe bar.",
  "gates": [
    {"name": "sharpe_floor", "metric": "sharpe", "op": ">=", "threshold": 2.0, "kind": "value"},
    {"name": "direction", "metric": "mean_pnl", "op": ">", "threshold": 0.0, "kind": "direction"}
  ],
  "decisions": {
    "pass": "recognized",
    "fail": "no_value, or effective_negative when the direction gate fails",
    "not_measured": "operational_error; nothing was decided"
  },
  "invalid_slots": ["sharpe_floor:not_measured", "direction:not_measured"]
}
```

Three properties matter:

1. **Named gates.** A finding can cite the exact gate that fired.
2. **Typed kinds.** `value` gates measure strength; `direction` gates measure
   sign. The distinction is what separates "not good enough" from "tested and
   wrong".
3. **Mandatory not-measured slots.** Every gate must declare what happens when
   the metric is missing. The constructor rejects a rule that omits one.

## Why the not-measured slot is mandatory

The most expensive mistake in empirical work is not a false positive. It is a
run that produced no usable measurement being read as a negative result. Once
that happens, every data outage looks like evidence.

The slot forces the author to answer, in advance, the question "what will we
conclude if this gate cannot be evaluated?" The only acceptable answer in this
repository is: nothing. `not_measured` maps to `operational_error`, not to
`no_value`.

## Freezing

```python
prereg = Preregistration(...)
digest = prereg.digest()  # SHA-256 over canonical JSON
plan = ledger.create_plan(cid, digest, seed)
```

The plan row stores the digest. The demo report prints it. A reader can
recompute it from the rule and check that the plan was created under the rule
it claims.

## Anti-patterns this rejects

- **A binary gate.** If the only outcomes are pass and fail, missing data has
  nowhere to go.
- **A rule without a hypothesis.** Gates without a claim are just filters.
- **A metric outside the closed set.** An unknown metric is either a typo or a
  new concept; both need an explicit edit, not a silent pass.
- **A decision table that omits a branch.** The constructor checks all three
  slots: pass, fail, not measured.

# Architecture

## Shape

The repository is a pipeline with one branch:

```
candidate (expression + settings)
    -> identity          content hash; idempotent registration
    -> plan              freezes (candidate, prereg digest, seed)
    -> attempt           one execution of one plan
    -> observation       metrics attached to a completed attempt
    -> outcome           one closed class + a rationale
```

The branch is the gate evaluation: a plan may be attempted without a
measurement (operational error), and the outcome still has to be recorded.
Nothing may leave the pipeline unclassified.

## Modules

| Module | Responsibility | Must not |
|---|---|---|
| `identity.py` | Normalize, hash, derive IDs | Know about storage or gates |
| `ledger.py` | Persist the five tables; enforce terminal outcomes | Judge a result |
| `prereg.py` | Define and validate a frozen rule | Evaluate a rule |
| `gates.py` | Evaluate gates against metrics | Decide what an outcome means |
| `classify.py` | Map gate results to a closed vocabulary | Invent a new class at runtime |
| `synthetic.py` | Produce a deterministic world and metrics | Encode the decision rule |

The boundaries are the point. A module that both computes a number and decides
what the number means cannot be tested independently.

## Invariants

1. **Identity is content.** A candidate ID is derived from the normalized
   expression and settings. There is no random or sequential ID for candidates.
2. **The rule is frozen before the run.** A plan stores the preregistration
   digest; changing the rule creates a different digest.
3. **Outcomes are terminal.** SQLite triggers reject `UPDATE` and `DELETE` on
   `outcomes`.
4. **Measurement is not zero.** A missing metric is `None`, and `None` produces
   `not_measured`, never a passing or failing comparison.
5. **One class per outcome.** `outcome_class` is a `CHECK`-constrained closed
   set.
6. **Observation content is addressable.** The observation ID covers the
   attempt and the metric payload.

## Deliberately absent

- **A platform adapter.** The production system has one; this repository does
  not, by design. `synthetic.py` is the seam.
- **Account, pool, and submission tables.** They only make sense with a live
  platform.
- **Research thresholds and field conclusions.** Those are findings, not
  method. They stay private.
- **A scheduler or agent loop.** The loop is the caller's responsibility. The
  repository supplies the record, not the autonomy.

## Why SQLite

The ledger is a file, not a service. That keeps the demo runnable offline and
makes the schema reviewable in one sitting. The schema uses SQLite features
that carry their weight: foreign keys, `CHECK` constraints, triggers, and
JSON validity checks. A production system can replace the storage layer
without changing the identity, gate, or classification semantics.

# Workflow

The loop is deliberately small. The expensive part is not running it; it is
refusing to skip a step.

## The loop

```
1. Hypothesis      a falsifiable claim about a mechanism
2. Candidate       expression + settings, registered by content
3. Preregistration the decision rule, frozen before the run
4. Plan            (candidate, rule digest, seed)
5. Simulate        positions taken before returns are realized
6. Record          metrics attached to a completed attempt
7. Classify        recognized / effective_negative / no_value / operational_error
8. Decide          human judgment on what to do next
```

Steps 2–7 are executable. Steps 1 and 8 are not.

## Artifacts

| Step | Artifact | Where |
|---|---|---|
| Hypothesis | a written claim with a falsifiable prediction | your notes |
| Candidate | normalized expression + settings | `candidates` table |
| Rule | typed gates + decision table | `prereg.py` object, digest in `plans` |
| Plan | candidate + rule + seed | `plans` table |
| Measurement | metrics | `observations` table |
| Outcome | one class + rationale | `outcomes` table |

The ledger is the source of truth. A report is a view, not a record.

## Ordering rules

1. **The rule must exist before the first simulation.** The demo constructs
   the preregistration, hashes it, and only then starts the world.
2. **A re-run is a new attempt.** It is not an edit of an earlier outcome.
3. **A not-measured gate blocks classification.** It is not a soft failure.
4. **Changing the rule invalidates the plan.** A new digest is a new plan, not
   a continuation.

## Human and AI

The split is a design constraint, not a slogan:

- **Human:** which question, which hypothesis, whether to authorize the rule,
  what counts as worth acting on, and when to publish.
- **AI:** draft the preregistered rule, expand a hypothesis into candidates,
  execute at volume, fill the ledger, produce the first reading.
- **Neither alone:** changing a gate after seeing results. That requires a
  human decision and a written reason.

## When a run is not measured

Do not reinterpret it. The outcome is `operational_error`, and the next action
is to fix the measurement, not to call the hypothesis rejected. If the same
measurement failure happens repeatedly, the finding is about the instrument,
not about the market.

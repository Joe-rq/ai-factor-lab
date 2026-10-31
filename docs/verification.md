# Verification

There are three questions, and they need three different judges.

| Layer | Question | Judge | Automatable |
|---|---|---|---|
| Rule | Is the record structurally sound? | Machine | Yes |
| Criterion | Did this candidate pass the frozen rule? | Machine + written criteria | Yes |
| Effectiveness | Was the research worth doing? | Human and the world | No |

## Rule layer

The rule layer decides what can be decided without judgment:

```bash
uv run pytest
uv run ruff check . && uv run ruff format --check .
uv run python scripts/check-structure.py
uv run python scripts/check-hygiene.py
```

`check-structure.py` verifies required files, forbids network imports in the
core package, requires module docstrings, and enforces a per-module line
budget. `check-hygiene.py` scans for identifiers, absolute paths, and
credential-shaped strings.

These checks are cheap and always on. They are not a substitute for review;
they exist so review does not spend attention on things a machine can answer.

## Criterion layer

The criterion layer is the preregistered rule plus the classifier. It answers
a narrower question than "is this a good factor": it answers "did this
candidate pass the rule that was frozen before the run".

Two properties make the answer trustworthy:

- The rule is content-addressed and recorded in the plan.
- The gate result is three-valued. `not_measured` is a first-class outcome.

What this layer **cannot** do is decide whether the rule is the right rule.
That is a research judgment, and it is reviewed by a human.

## Effectiveness layer

The third layer asks whether the work mattered: whether the hypothesis was
worth testing, whether the result survives out of sample, and whether anyone
should act on it.

No repository can automate this. The honest position is to name the red line
rather than pretend the rule layer covers it.

## What this repository verifies about itself

- The positive control is rejected.
- The zero-variance candidate is `operational_error`.
- Outcomes are immutable.
- A missing metric is not measured.
- The demo is deterministic across runs.

These are all in `tests/`. They are necessary conditions, not proof that the
research method is sound.

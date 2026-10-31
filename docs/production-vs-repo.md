# Production vs. public repository

> The public repository is a **rewrite around the same invariants**, not an
> export. This page states what is the same, what was replaced, and what was
> deliberately left out.

## Why a rewrite

The production system is coupled to a live platform: a client, a submission
path, account-level pool checks, and a large schema that carries platform
state. Exporting it would produce a repository that does not run without the
platform, and would risk carrying private identifiers into history.

The public version keeps the parts that are method and replaces the boundary:

| Concept | Production | Public | Same logic? |
|---|---|---|---|
| Candidate identity | content hash over normalized expression + settings | `identity.py` | Yes, reduced |
| Ledger | SQLite with platform, submission, and pool tables | `ledger.py`, five tables | Same invariants, smaller schema |
| Preregistration | typed gates + decision table + invalid slots | `prereg.py` | Yes |
| Gate evaluation | threshold and direction gates | `gates.py` | Yes, reduced |
| Outcome vocabulary | recognized / effective_negative / no_value / operational_error / pending | `classify.py` | Yes |
| Positive controls | device registry with paired inputs | demo controls | Same principle, fewer devices |
| Execution | live platform simulation | `synthetic.py` | Replaced |
| Submission and pool | platform-specific | absent | Deliberately omitted |

## What "same invariants" means

The public repository preserves the properties that make the record
trustworthy:

- identity is content-addressed;
- outcomes are terminal;
- missing measurements never become failures;
- the rule is frozen before the run;
- every gate has an explicit not-measured branch.

It does not preserve the production schema, the platform adapter, or any
research finding.

## What was left out, and why

| Left out | Reason |
|---|---|
| Platform client, auth, sessions | No platform integration belongs in a public method repo |
| Account and pool tables | Meaningless without a platform account |
| Submission workflow | Platform-specific and outside the method |
| Real expressions, alpha IDs, metrics | Research assets, not method |
| Field-level findings and thresholds | The edge, not the method |
| Cron jobs and agent orchestration | Environment-specific |

## What this means for a reader

You can run the full loop, inspect the record, and check the invariants. You
cannot reproduce the private research results, and the repository does not
claim that you can. The production system is where the data lives; this is
where the method is shown.

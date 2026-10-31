# Security

## Scope

This repository contains method, not data. It has no platform client, no
credentials, no account information, and no real market data.

## Reporting a vulnerability

Use GitHub Security Advisories on this repository. Do not open a public issue
for a security report.

Please include:

- the affected file or command;
- a minimal reproduction;
- the impact you believe it has.

There is no bounty and no response-time guarantee. Reports about the accuracy
of a synthetic metric are not security reports.

## What is in scope

- Code execution through crafted input files or expressions.
- A path that writes outside the working directory.
- A dependency or build step that exfiltrates data.
- A leak of a credential or personal identifier in the repository itself.

## What is not in scope

- Investment performance, model accuracy, or factor quality.
- The behavior of any external platform.
- Missing features.

## Handling secrets

The rule is simple: secrets never enter the repository. Configuration that
looks like a secret is rejected by `scripts/check-hygiene.py`, which runs in
CI. If a secret is committed by mistake, rotate it first, then rewrite
history; deleting the file in a later commit is not enough.

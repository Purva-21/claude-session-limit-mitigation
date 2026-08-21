# Security Policy

This repo is a field report plus a handful of small, dependency-free Python
and shell tools (`tools/`) for auditing and cleaning up an agent's working
directory. There is no server, no service, and no user data collected —
everything runs locally against files you point it at.

## Reporting a vulnerability

If you find a security issue in one of the scripts (for example, something
that could let a crafted filename or file content lead to unintended code
execution or path traversal), please report it privately rather than opening
a public issue:

- Preferred: use GitHub's [private vulnerability reporting](../../security/advisories/new)
  for this repository.
- Otherwise: email purvagohil5@gmail.com with a description and, if possible,
  steps to reproduce.

Please do not open a public issue for security reports until it has been
triaged.

## What's in scope

- `tools/*.py`, `tools/*.sh` — the audit, cleanup, forensics, and salvage
  scripts.
- `site/` and `index.html` — the static GitHub Pages explainer.

Everything else in this repo (`docs/`, `prompts/`, `examples/`) is
documentation and has no execution surface.

## Response

This is a solo-maintained project. There's no formal SLA, but reports will be
acknowledged and looked at as soon as possible.

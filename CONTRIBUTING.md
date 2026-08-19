# Contributing

This repo is a field report plus two small tools. The most valuable
contribution is **another data point**.

If you hit a session limit in a way this document does not explain, please open
an issue with:

1. `python3 tools/context_audit.py <your project> --json` output (redact paths
   if you need to — the numbers are what matter),
2. roughly what the session was doing when it hit the limit,
3. whether anything was lost, or only delayed.

Please keep claims separated the way the docs do: what you **observed** and
what you **infer**. The value of this repo is that the two are not mixed.

Code contributions: keep `tools/` dependency-free (standard library only) so
the audit can run anywhere, including inside a constrained agent sandbox.

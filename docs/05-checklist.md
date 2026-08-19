# 05 — One-page checklist

Paste this into your own runbook.

## Before starting a long agent session

> Automated: `tools/prep_workspace.sh /path/to/project --apply` covers the first
> four boxes. Then paste `prompts/session-start.md` for the "During" section.


- [ ] `python3 tools/context_audit.py .` — is the worst case under budget?
- [ ] No file in the top-10 that you wouldn't open by hand.
- [ ] Notebook outputs stripped (`tools/nb_strip.py --inplace`, or install
      `nbstripout` as a git filter so they never come back).
- [ ] Build artifacts in `artifacts/`, **and** `AGENTS.md` says not to read it.
- [ ] Superseded versions of files deleted, not kept "just in case".
- [ ] `STATE.md` created, even if empty.

## During the session

- [ ] Edits to large structured files go through a **patch script**, never a
      rebuild.
- [ ] Verification is **one** batched command, not ten.
- [ ] Diagnostics run in-process; anything delegated writes results to disk
      incrementally.
- [ ] Intermediates deleted once consumed — but small evidence kept for
      diagnosis.
- [ ] Before disputing any external finding: diff the delivered artifact
      against the local copy.

## At every natural boundary

- [ ] Patch script encodes all edits so far and re-runs cleanly from scratch.
- [ ] `STATE.md` updated: done / pending / ruled out and why.
- [ ] Current validator and test output saved.
- [ ] Re-run the audit — the directory grows during a session.
- [ ] If the checkpoint is complete, **start a fresh session.**

## Red flags that you are burning budget invisibly

- A one-line fix required regenerating a file larger than 20 KB.
- You have re-read the same artifact three rounds running to confirm unchanged
  state.
- The directory contains more than one version of the thing you are building.
- A notebook in the working directory has stored outputs.
- Work you cannot afford to lose is running inside a sub-agent.
- You are arguing that a report is stale without having diffed it.

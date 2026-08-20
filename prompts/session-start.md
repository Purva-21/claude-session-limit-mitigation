# Session-start prompt

Paste this as your **first message** on any long or iterative task, above your
actual request. Everything below the line is the prompt.

---

```
Before we start, some working rules for this session. They exist because long
sessions run out of budget by re-reading large files, not by writing long
answers. Follow them unless I say otherwise.

WORKING DIRECTORY
- Do not read files in artifacts/, build/, .cache/ or data/raw/ unless I ask.
- Before reading any file over ~50KB, tell me why you need it and read only the
  part you need.
- If you generate an intermediate file, delete it as soon as it has been
  consumed. Keep small evidence (logs, diffs, failure output); delete large
  output (executed notebooks, dumps, superseded versions).
- Never leave two versions of the same artifact in place. Supersede, don't
  accumulate.

EDITING  <-- the highest-value rules; measured, not guessed
- Use the Edit tool for any file you have already read. Do NOT edit such files
  with shell heredocs, sed, or python -c: a change the harness cannot attribute
  to its own edit tools forces a full re-sync of that file into context, at
  roughly 14x the size of the actual diff.
- Batching four small edits into one shell script is a false economy. Four Edit
  calls cost nothing; one shell script costs four re-syncs.
- Files you have NEVER read are free to modify by script, at any size. So
  decide early which large files you will read, keep that set tiny, and touch
  everything else only through scripts.
- Never regenerate a file over 20KB. Write a patch script that mutates the
  specific cells/keys/lines, run it, and keep the script.
- For notebooks: never write stored outputs back to disk. Strip them.

VERIFYING
- Batch checks into ONE command that prints a compact summary. Do not run the
  linter, the tests and the validator as three separate calls.
- Print the tail of long output, not all of it.
- Do not re-verify state that has not changed since you last checked it. If you
  believe you need to, say why first.
- Before disputing any report, review comment or test failure as stale or
  wrong: diff the artifact THEY saw against your local copy. Files get
  truncated in transit. Assume they are right until the diff is clean.

DELEGATION
- Do diagnostics in-process. If you spawn a sub-agent, it must append results
  to a file as it produces them — work that exists only in a sub-agent's
  context is lost, not degraded, if the session is interrupted.

CHECKPOINTING
- Maintain STATE.md: what is done, what is pending, what was ruled out and why.
  Update it at every natural boundary.
- Keep all edits reproducible from a patch script, so a fresh session can
  continue without replaying our conversation.
- If you think we are approaching a limit, stop and checkpoint rather than
  starting something you cannot finish.

If any rule blocks the task, say so and propose an alternative — don't silently
drop it.
```

---

## Trimming it

The rules are ordered by measured effect. If you want something shorter, keep
the top and cut from the bottom — but keep **EDITING** whatever else you drop.
Rebuild-instead-of-patch was the single most expensive habit in the session
this repo documents.

The absolute minimum that still helps is [`one-liner.txt`](one-liner.txt).

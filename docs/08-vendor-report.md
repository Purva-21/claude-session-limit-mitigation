# 08 — Report for the tool vendor

A paste-ready write-up for a bug tracker or feedback channel. Deliberately
short, and deliberately conservative about what it claims. If you are filing
this, feel free to cut everything below "Severity" — the top half is the report.

---

## Title

Files already in context are re-sent in full after shell-mediated writes;
~34% of re-sent bytes are byte-identical duplicates

## Summary

In a long agentic coding session, a file already present in the model's context
is re-injected in full whenever it is modified by something the harness cannot
attribute to its own edit tools (a shell command, a script, a build step).

The resynchronisation itself is correct and necessary — an agent patching
against a stale copy produces broken patches. Three aspects of *how* it is done
appear to be avoidable cost:

1. **The resync sends a window of the file, not a diff.** Measured against
   `git diff`: a 562-byte edit produced an 8,156-byte re-injection (14.5×). The
   harness holds both versions and could send the delta.

2. **Byte-identical content is re-sent repeatedly.** 13 of 26 re-syncs were
   exact repeats (same MD5) of files unchanged between deliveries — 39,573 of
   114,931 bytes, **34.4%**. One 665-byte file was delivered four separate
   times. A content-hash comparison before emitting would eliminate this
   entirely.

3. **A read-only operation is the largest trigger.** 15 of 28 events followed a
   file-delivery tool call that modifies nothing. It cannot dirty a file, but it
   does mark a turn boundary — consistent with a pending-resync set that is
   appended to on shell writes, flushed on turn boundaries, and never emptied by
   a successful flush. *(This causal account is inference; the counts are not.)*

## Evidence

Parsed from the session transcript (`~/.claude/projects/<slug>/<id>.jsonl`),
where re-injections appear as `edited_text_file` attachments.

| | |
|---|---:|
| `Edit` / `Write` / `NotebookEdit` calls | 82 |
| re-injections following one | **0** |
| `Bash` calls | 103 |
| re-syncs of files already in context | 73 |
| total re-injected | 295,044 B (~82,000 tokens) |
| byte-identical duplicates | **57 events, 195,663 B (66.3%)** |
| worst single case | a 665-byte file delivered **15 times** |

Trigger breakdown for the 75 events: `SendUserFile` 43, `Bash` 16, `WebFetch`
10, `AskUserQuestion` 4, initial reads 2. **`WebFetch` and `AskUserQuestion`
cannot touch the filesystem**, and neither can `SendUserFile` — so 57 of 75
events cannot be change detection. They are a queue flushing at turn
boundaries.

The four most-duplicated files had not been edited for hours; the session had
moved to unrelated work in a different directory. They were re-sent unchanged
anyway. The duplicate share grew from 21.5% → 34.4% → 66.3% across three
measurements of the same session, which indicates the pending set accumulates
and is never emptied.

Fifty-four in-context edits produced zero re-injections; every re-sync followed
a shell-mediated change or a re-flush of one. The split is clean and held as the
sample doubled mid-session (13 events → 28).

The `Edit` path is visibly instrumented — its tool result reads *"file state is
current in your context — no need to Read it back"* — which is consistent with
the harness tracking changes it makes itself and resyncing only when it cannot.

## Reproduction

`tools/transcript_forensics.py` in this repo parses a transcript and reports
re-injection events, triggers, duplicate hashes and totals:

```bash
python3 tools/transcript_forensics.py ~/.claude/projects/*/<session-id>.jsonl
```

A tool-agnostic behavioural A/B (native edit vs shell edit vs a no-op `touch`)
is in `prompts/replication-test.md`.

## Suggested fixes, cheapest first

1. **Skip the resync when the content hash matches what was last delivered.**
   Removes finding 2 outright — a third of the cost — with no behaviour change.
2. **Emit a unified diff instead of a file window.** Addresses finding 1.
3. **Hash-compare after shell tool calls** rather than treating any
   shell-mediated write as an unknown change. Files whose bytes are unchanged
   (e.g. after `touch`, or a script that rewrites identical content) need no
   resync at all.
4. **Expose per-turn input attribution** — conversation vs file re-injection vs
   tool results. This was diagnosable only by parsing the transcript by hand;
   a breakdown in the UI would have surfaced it in minutes rather than days.

## Severity

Low per event, meaningful in aggregate, and invisible to the user. Roughly a
sixth of a 200k-token budget went on re-sending files the agent already had, in
a session whose actual deliverable was a few dozen KB of markdown. The effect
scales with file size, so most projects will never notice it; projects with
large notebooks, generated JSON or big fixtures will.

---

## What this report deliberately does not claim

Worth keeping if you file it — it makes the rest more credible, not less.

- **This is n = 1.** One harness, one version, one working directory. The
  duplicate behaviour in particular could be version-specific or transient.
- **The queue-flush explanation is inference.** The duplicate *counts* are
  byte-exact; the reason for them is a guess that fits.
- **It is not a model defect.** No evidence of looping, hidden generation or
  retry storms; output volume per turn was unremarkable. This is a file-tracking
  layer, not reasoning.
- **The largest single contributor was the user's own setup, not the harness.**
  The working directory carried 277,530 tokens of exposure before any work
  started — build output never read again, four superseded copies of the same
  notebook, ~108 KB of stored cell outputs in one file. Cleaning that up cut it
  6.9×. The agent's habit of editing in-context files via shell heredocs
  (instead of the edit tool) manufactured most of the resync events.

The harness could fix findings 1–3 and this session would still have been
expensive. That is the honest framing.

---

## Where to send it

- **In-product feedback** — the thumbs-down control on a response is the most
  direct route to the team, and it carries session context automatically.
  Mention "session transcript forensics" and link this repo.
- **Public issue tracker** — check the tracker for the specific tool you were
  using; agentic products from the same vendor may have separate ones.
- **Link, don't paste, the long version.** Point at
  [`docs/07-the-actual-bug.md`](07-the-actual-bug.md) for the timeline and
  `tools/transcript_forensics.py` for the parser. A short report with a
  reproducible tool behind it gets read; a wall of text does not.

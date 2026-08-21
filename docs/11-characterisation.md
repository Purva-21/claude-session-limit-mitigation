# 11 — Characterising the re-flush defect

Doc 07 established *that* files already in context are re-sent. This file
characterises the defect: what the set is, what adds to it, what removes from
it, how often it flushes, and what it costs at steady state.

Everything below is derived from one session's transcript with
[`tools/transcript_forensics.py`](../tools/transcript_forensics.py) and the
turn-level analysis described in §Reproducing. It is **n = 1**; the controlled
tests that would make it n-many are in §What still needs testing.

---

## The model, stated

The harness appears to maintain a **pending-resync set** of files.

| | rule | evidence |
|---|---|---|
| **Added** | when a file already in context is written by something outside the harness's own edit tools (shell command, script, build step) | all 73 re-syncs followed such a write; 82 `Edit`/`Write` calls produced 0 |
| **Removed** | *only* when the harness's own `Edit`/`Write` tool writes that file | see the eviction table below |
| **Flushed** | on a minority of turn boundaries — 21 of 296 turns — emitting **every** member, in full | flush turns are sparse but each carries the whole set |
| **Never expires** | membership survives indefinitely; no timeout, no read-based clearing | one file was flushed across a span of 234 turns |

## The eviction rule — the sharpest result

Split the files by whether an `Edit`/`Write` occurred *after* they entered the
set:

| file | last `Edit`/`Write` | flushes after it | outcome |
|---|---:|---|---|
| `README.md` | turn 200 | **none** | evicted |
| `00-diagrams.md` | turn 162 | **none** | evicted |
| `01-observed-behaviour.md` | turn 11 | 14 | **stuck** |
| `04-reproduction.md` | turn 22 | 14 | **stuck** |
| `05-checklist.md` | turn 23 | 15 | **stuck** |
| `mid-session.md` | turn 44 | 15 | **stuck** |

The two files that were later opened with `Edit` stopped being re-sent, cleanly
and permanently. The four whose only edit-tool contact *predates* their entry
into the set have been re-sent on every flush since — one of them across 234
turns.

**No `Read` occurred on any stuck file after it entered the set**, so reading is
not what evicts. The only observed eviction is a write through the harness's own
tool.

## Steady state

- Flush size grew and then **plateaued at 4** — the size of the stuck set.
- 21 flushes × the stuck set = the cost floor for the remainder of the session.
- `mid-session.md` is **665 bytes** and was delivered **15 times**, byte-identical.
- Duplicate share of all re-injected bytes, measured three times on the same
  session: **21.5% → 34.4% → 66.3%**.

The trend is the important part. The set accumulates, nothing leaves it
unassisted, so the duplicate fraction rises monotonically for as long as the
session runs.

## What the flush is *not*

57 of 75 events follow `SendUserFile` (43), `WebFetch` (10) or
`AskUserQuestion` (4). **None of those three can write to the filesystem.** So
the emission is not change detection at the moment of emission — it is a queue
being drained at a turn boundary, and those tools merely mark boundaries.

## Minimal reproduction

```
1. Create a small text file, F.
2. Read F, so it enters context.
3. Modify F with a shell command  (e.g. sed -i / a python heredoc).
   -> F enters the pending set.
4. Continue the session doing unrelated work in a different directory.
   Never touch F again.
   -> F is re-sent, byte-identical, on every flush, indefinitely.
5. Now edit F once with the harness's Edit tool.
   -> F stops being re-sent.
```

Step 5 is both the diagnostic and the workaround.

## Practical workaround, today

If a session feels expensive and the same filenames keep reappearing in
file-change notices: **open each of them once with the edit tool** — a
whitespace-neutral change is enough — to evict them from the set. Cheaper still,
avoid step 3: use the edit tool for any file already in context, and reserve
shell-mediated edits for files that were never read.

## Fixes, cheapest first

1. **Compare a content hash before emitting.** If the file's current content
   matches what was last delivered, drop the entry. Removes 66.3% of the cost
   here and is a few lines.
2. **Clear the entry on successful delivery.** The entry exists to inform the
   agent once; keeping it after a successful flush is what makes the cost
   unbounded.
3. **Emit a diff rather than a window.** Separately measured at 14.5×
   amplification (562 B edit → 8,156 B).
4. **Evict on any confirmed-current read, not just a write** — a cheap
   secondary path out of the set.

## Resolved: the payload is fresh, but the region set accumulates

The open question — *is the flushed payload a stale snapshot?* — was settled by a
controlled probe run inside the same session.

**Method.** `prompts/mid-session.md` had been stuck for 17 consecutive flushes,
delivering a byte-identical 665-byte window covering **lines 79–99** — the region
touched by the shell edit that originally queued it. A marker string was then
inserted at **line 3** by a shell command, deliberately far from that window. A
second stuck file, `docs/04-reproduction.md`, was left untouched as a control.

**Result.**

```
ARM A  prompts/mid-session.md
  deliveries  1-17   hash f58064   665 B   lines 79-99   marker absent
  delivery      18   hash 7c8b54   977 B   lines  1-99   marker PRESENT

ARM B  docs/04-reproduction.md  (control)
  every delivery     hash b58567  5236 B   lines 1-120   unchanged
```

**Two conclusions.**

1. **It is not a stale snapshot.** The payload refreshed as soon as the file
   genuinely changed, and the marker appeared. So the agent is not being handed
   outdated content. **This is an efficiency defect, not a correctness one** —
   the less alarming of the two possibilities, and worth stating plainly.

2. **The dirty-region set accumulates within an entry.** The window did not move
   to line 3. It expanded to cover **lines 1–99** — the new region *and* the
   original one, together. The 665-byte payload became 977 bytes, and that larger
   payload is what every future flush now carries.

So the leak is two-dimensional:

| dimension | what accumulates | what would clear it |
|---|---|---|
| set membership | files never leave | only an `Edit`/`Write` to that file |
| entry payload | dirty regions never retire | nothing observed |

Each shell-mediated edit to an already-stuck file permanently enlarges its
per-flush cost. A file edited by shell ten times in different places would carry
all ten regions on every subsequent flush, forever.

The 17 identical deliveries preceding the change are also the cleanest available
proof of the duplicate behaviour itself: the payload was provably constant across
17 flushes while the file sat untouched.

## What still needs testing

These cannot be settled from one transcript. Each is a controlled experiment:

| # | question | how to test |
|---|---|---|
| 1 | Does it reproduce in a fresh session? | run the minimal repro above from a clean start |
| 2 | Is eviction really write-specific? | after step 3, `Read` F and continue — does it still flush? |
| 3 | Is the set bounded? | dirty 10 files via shell; does the flush carry all 10? |
| 4 | What makes a turn a flush turn? | only 21 of 296 flushed — log tool types per turn and correlate |
| 5 | ~~Does the payload refresh?~~ | **Answered above.** It refreshes, but the old region is retained alongside the new one |
| 6 | Does it survive compaction? | this session compacted early; check whether the set persisted across it |

Question 5 has since been answered by direct experiment — see the section above.
The payload is **not** stale, which keeps this an efficiency defect rather than a
correctness one. The probe did however expose the second dimension of the leak:
dirty regions accumulate within a file's entry and are never retired.

## Reproducing the analysis

```bash
python3 tools/transcript_forensics.py ~/.claude/projects/*/<id>.jsonl
```

The turn-level eviction analysis is a short script over the same records: walk
the transcript counting `user` records as turns, log every `tool_use` with a
`file_path` and every `edited_text_file` attachment, then compare each file's
last edit-tool turn against its flush turns.

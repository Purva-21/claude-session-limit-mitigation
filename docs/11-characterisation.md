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
5. Modify F AGAIN by shell, in a different part of the file.
   -> the payload does not move to the new region; it expands to cover both,
      and stays larger for the rest of the session.
6. Now edit F once with the harness's Edit tool.
   -> F stops being re-sent.
```

Steps 4 and 5 demonstrate the two dimensions separately — membership that never
sheds files, and entries that never shed regions. Step 6 is both the diagnostic
and the workaround.

Keep this section even though the probe above already establishes the behaviour:
the probe is evidence from one session that a maintainer cannot re-run, whereas
these six steps are something they can execute in five minutes on their own
machine. A defect report needs both.

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

## What a compaction boundary carries

This session compacted. That is worth a section of its own — partly for what
the boundary carried, partly for what it destroyed on the way past, and partly
because it is the first event other than an `Edit`/`Write` that *might* empty
the set. Whether it does is the subject of the next section; this one is only
about what can be read directly off the rewritten transcript.

The rewritten transcript opens with the summary record, followed by eight
attachments. Five of them name a file:

| file | attachment kind | payload |
|---|---|---:|
| `docs/11-characterisation.md` | `file` | lines 1–191, whole file, 8,838 B |
| `docs/08-vendor-report.md` | `file` | lines 1–162, whole file, 7,505 B |
| `prompts/mid-session.md` | `file` | lines 1–100, whole file, 2,832 B |
| `README.md` | `compact_file_reference` | name only — "too large to include" |
| `hs/leak.html` | `compact_file_reference` | name only |

Every one of the three `file` payloads has `startLine = 1` and
`numLines == totalLines`. They are whole-file `Read` results preserved across
the boundary. A flush payload does not look like that: it is an
`edited_text_file` carrying a *window* — `startLine = 79`, part of a file.
**The rewritten transcript contains no `edited_text_file` attachment at all.**

Three of the four stuck files are simply absent.
`01-observed-behaviour.md`, `04-reproduction.md` and `05-checklist.md` appear in
no post-compaction attachment. `mid-session.md` does appear — but as a
2,832-byte whole file, not as the window it had been carrying as a set member
(665 B over lines 79–99 for seventeen deliveries, then 977 B over lines 1–99
once the probe enlarged it). Different attachment kind, different shape,
different size. Its presence is explained by a `Read` in the continuation, not
by membership.

That is suggestive, not sufficient: an empty flush and a set with nothing left
to flush look identical from outside. §The post-compaction probe separates them.

## The post-compaction probe

**Design.** Three treatment files, three controls.

Each treatment is created fresh after the boundary, `Read` into context, then
dirtied by `sed -i` — exactly the sequence that put the original six files into
the set. The controls are `01-observed-behaviour.md`, `04-reproduction.md` and
`05-checklist.md`: the three files still stuck when the session compacted,
deliberately untouched by `Read`, `Edit` or shell. Whatever happens to them is
the answer.

The first version of this probe had a single treatment in `/tmp`, on the
reasoning that somewhere isolated could not be contaminated by ordinary edit
traffic. That reasoning was wrong, and in the direction that matters: every
file ever observed in the set lived under `/root`, so if tracking is scoped by
directory, a `/tmp` file could never join the set and its silence would mean
nothing. **A negative result from an arm that cannot produce a positive is not
a result.** Two more arms were added to close it:

| arm | path | controls for |
|---|---|---|
| A | `/tmp/flushprobe/probe_a.md` | nothing — outside every tracked tree |
| B | `/root/probe_b.md` | same tree as the stuck files, outside the repo |
| C | `docs/probe_c.md` | the exact directory that held four of the six |

If C is silent, directory scope is not the explanation.

**Discriminator.** The next `edited_text_file` flush after the shell edits.

| what the flush carries | conclusion |
|---|---|
| a treatment only | compaction cleared the set; the mechanism still works |
| a treatment + any control | membership survived the boundary |
| nothing, indefinitely | the set is gone *and* not refillable — the strongest claim, and the one needing the most patience |

The third row is why the probe needs treatment arms at all. Without a file
known to be freshly queued, silence proves nothing: a set that was cleared and a
set that simply has not flushed yet look identical from outside.

**Positive control.** Before reading anything into silence, check the machinery
is still switched on. Every `Edit` this session still returns *"file state is
current in your context — no need to Read it back"* — the same instrumentation
string quoted in [`08`](08-vendor-report.md) as evidence that the harness tracks
its own writes. The file-tracking layer is alive after the boundary. Whatever is
not happening, it is not that the subsystem stopped running.

**Result, snapshot at post-compaction turn 70.** The session was still running
when this was written, so these counts are a floor; re-run the census below to
refresh them.

| | pre-compaction | post-compaction |
|---|---:|---:|
| turns | 296 | 70 |
| turns since a treatment was queued | — | 56 (arm A) / 39 (arms B, C) |
| `Bash` calls | 103 | 36 |
| `SendUserFile` calls | — | 2 |
| `WebFetch` calls | — | 1 |
| **`edited_text_file` events** | **75** | **0** |

The three tools behind 69 of the 75 pre-compaction events — `SendUserFile` 43,
`Bash` 16, `WebFetch` 10 — have all been exercised since. Three files have been
queued by the exact `Read` → `sed -i` sequence that queued the originals, in
three different directory scopes. Nothing has flushed.

```bash
python3 - <<'EOF'
import json, collections
p = "PATH/TO/transcript.jsonl"
turns = 0; flushes = 0; tools = collections.Counter()
for line in open(p):
    line = line.strip()
    if not line: continue
    try: r = json.loads(line)
    except ValueError: continue
    if r.get("type") == "user": turns += 1
    if r.get("type") == "assistant":
        for c in (r.get("message") or {}).get("content") or []:
            if isinstance(c, dict) and c.get("type") == "tool_use":
                tools[c.get("name")] += 1
    if r.get("type") == "attachment" and (r.get("attachment") or {}).get("type") == "edited_text_file":
        flushes += 1
base = 1 - 21/296                      # measured pre-compaction flush rate
print(turns, "turns,", flushes, "flushes,", dict(tools))
print("P(0 by chance) = %.4f" % base**turns)
EOF
```

**Verdict: a trend, not a finding.** Pre-compaction, 21 of 296 turn boundaries
carried a flush — a base rate of **7.1%**. Zero post-compaction boundaries have.
How unlikely that is depends on which arm you are willing to assume actually
joined the set, and the two answers are far apart:

| assumption | arms counted | turns queued | P(0 flushes by chance) |
|---|---|---:|---:|
| only `/root` is tracked | B, C | 39 | **0.057** — 1 in 18 |
| `/tmp` is tracked too | A, B, C | 56 | **0.016** — 1 in 62 |

**Report the top row.** Arm A is the one whose membership is least defensible —
it sits outside every tree in which a tracked file has ever been observed — so
leaning on it to claim significance would be assuming the conclusion. On the
conservative reading this is one chance in eighteen: right at the edge, and on
the wrong side of it.

Consistent with compaction having cleared the set. Not yet evidence of it.

### Why this probe can never do better than "suggestive"

Every further quiet turn multiplies that p-value by 0.929. It was 0.20 an hour
ago; it was 0.057 at turn 70; it crossed 0.05 shortly after, and it will keep
falling for as long as the session runs without flushing.

**That is not a result arriving. That is optional stopping.** A p-value computed
from a series the analyst is watching, with the stopping point chosen after
seeing it, is not a p-value. If the rule is "keep looking until it drops below
0.05" then it drops below 0.05 eventually with probability 1, whether or not
compaction does anything at all. Quoting the number from the moment it happened
to cross would be the single most misleading thing this repo could do, and it
would be easy, and it would look rigorous.

So the figure is frozen at turn 70 above and labelled as a snapshot, and the
conclusion stays at "trend". The honest way to settle this is a **fresh session
with the turn budget fixed in advance**: pick N before starting, run the probe
for exactly N turns, report whatever it says. That is the sixth row of the table
below, and it is the one experiment in this document that has not been run.

The same caution applies to the pre-compaction numbers, and there it does not
bite: those were counted from a completed transcript over a fixed window, not
watched as they accrued.

Two honest limits on top of that:

- **The controls are currently uninformative.** `01-observed-behaviour.md`,
  `04-reproduction.md` and `05-checklist.md` have not reappeared — but nothing
  has, so their silence adds no information beyond the boundary observation.
  They only become evidence once *some* flush occurs.
- **Arm membership is unverifiable from inside.** There is no way to confirm a
  probe file entered the set except by watching it leave. If the queueing
  behaviour itself changed after compaction, all three arms are empty and the
  whole probe is measuring nothing. This cannot be ruled out from the client
  side; it can be answered from the source in a minute.

The probe stays running. If a flush fires later in this session, the row it
lands on in the table above is the answer.

## What compaction destroyed

The turn-314 experiment — evict `mid-session.md` with `Edit`, then watch for its
absence from the next flush — can no longer be settled. Compaction rewrote the
transcript in place: 296 turns of records became 48 lines. No flush fired
between the revert and the boundary, so the deliberate eviction was never
observed, and the records that would have shown it are gone from disk.

Two things follow.

1. The eviction rule stands exactly where it was — six files, observational,
   n = 1. The confirmation was **lost, not refuted**.
2. **Copy the transcript before the session compacts.** A single
   `cp ~/.claude/projects/<slug>/<id>.jsonl /tmp/` is the difference between
   holding the evidence and describing it from memory. Every number in this
   repo survives only because it was parsed into [`07`](07-the-actual-bug.md)
   while the records still existed. This is the one operational lesson worth
   taking from a defect report about a session that ran out of room.

## What still needs testing

These cannot be settled from one transcript. Each is a controlled experiment:

| # | question | how to test |
|---|---|---|
| 1 | Does it reproduce in a fresh session? | run the minimal repro above from a clean start |
| 2 | Is eviction really write-specific? | after step 3, `Read` F and continue — does it still flush? |
| 3 | Is the set bounded? | dirty 10 files via shell; does the flush carry all 10? |
| 4 | What makes a turn a flush turn? | only 21 of 296 flushed — log tool types per turn and correlate |
| 5 | ~~Does the payload refresh?~~ | **Answered above.** It refreshes, but the old region is retained alongside the new one |
| 6 | Does it survive compaction? | **Trending no; p ≈ 0.06 conservatively at turn 70.** The boundary carried no flush payload and dropped three of four stuck files; 70 turns and three freshly-queued files later, nothing has flushed. Settling it needs a fresh session with the turn budget **fixed in advance** — see §Why this probe can never do better than "suggestive" |

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

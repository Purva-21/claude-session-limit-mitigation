# 07 — The actual bug

> **Status: measured, not inferred.** Everything in this file comes from
> parsing the session transcript
> (`~/.claude/projects/<slug>/<session-id>.jsonl`) with
> [`tools/transcript_forensics.py`](../tools/transcript_forensics.py), which is
> checked in so you can re-run it on your own. This supersedes the hypothesis
> in [02-root-cause.md](02-root-cause.md), which was written before the
> transcript was examined.

[01-observed-behaviour.md](01-observed-behaviour.md) established *that*
re-reading was happening. This file answers the question that was still open:
**what triggers it, and why.**

---

## The finding in one line

Re-injection fires when a file that is **already in context** is modified by
something the harness **cannot attribute to its own edit tools** — a shell
command, a script, a build step. Edits made with the `Edit`/`Write` tools never
trigger it.

---

## The control that proves it

Across the transcript, re-measured at the end of the session:

| | count |
|---|---:|
| `Edit` / `Write` / `NotebookEdit` calls | **54** |
| `Bash` calls | 46 |
| File re-injection events | 28 |
| Re-injections attributable to `Edit`/`Write` | **0** |

Fifty-four in-context edits, zero re-injections. Every single re-injection
followed a shell-mediated change or a queue re-flush of one. This is not a
subtle correlation — it is a clean split, and it held as the sample grew.

> **The numbers in this file were measured twice.** An earlier pass, midway
> through the session, saw 13 events / 57,631 B / 3 duplicates. By the end it
> was 28 / 114,931 / 13. The mechanism did not change; the sample did. Where
> both are informative, the growth is noted — it is the clearest evidence that
> the duplicate behaviour is systematic rather than a one-off.

The reason is visible in the transcript itself. After an `Edit`, the tool result
carries:

> *file state is current in your context — no need to Read it back*

The harness knows exactly what changed, because it made the change. After a
shell command it does not, so it has to resynchronise — and it resynchronises
by **re-sending the file**.

---

## What that cost, exactly

```
FILE RE-INJECTIONS
  events                  : 28
  bytes                   : 114,931  (~31,925 tokens)
  duplicated events       : 13  (39,573 B of identical content re-sent)

BY TRIGGERING TOOL
  Bash                     n=11      49,796 B
  SendUserFile             n=15      48,809 B
  (initial reads)          n=2       16,326 B
```

Twenty-six of the twenty-eight were re-syncs of files already in context. Two
were genuine first reads.

Roughly **32,000 tokens** — about a sixth of a 200k budget — spent re-sending
files the agent had already been given, in a session whose actual deliverable
was a few dozen kilobytes of markdown.

---

## Amplification: the re-sync is not a diff

The harness has both versions of the file. It could send a unified diff. It
sends a window of the file instead — and for a small file, the whole thing.

One commit, measured against `git diff`:

| file | bytes actually changed | bytes re-injected | ratio |
|---|---:|---:|---:|
| `README.md` | 562 | 8,156 | **14.5×** |
| `docs/05-checklist.md` | 573 | 2,163 | 3.8× |
| `prompts/mid-session.md` | 307 | 665 | 2.2× |
| `docs/00-diagrams.md` | (new file, 196 lines) | 7,081 | 1.0× — legitimate |

A 562-byte edit to the README cost 8,156 bytes of context. The information
needed to update the agent's view was the diff; what arrived was a large slice
of the file.

This is inefficiency rather than incorrectness — the resync is *right*, just
expensive. But at 14.5× it is the difference between a session that finishes
and one that doesn't.

---

## The defect: identical content re-sent

This one looks like a straightforward bug rather than a design cost.

```
DUPLICATE CHECK (same file + identical content hash re-sent)
  mid-session.md            sent 4 times
  README.md                 sent 4 times
  05-checklist.md           sent 3 times
  04-reproduction.md        sent 3 times
  01-observed-behaviour.md  sent 3 times
  00-diagrams.md            sent 2 times
  duplicate events: 13 of 26   (39,573 B, ~11,000 tokens)
```

**34.4% of every re-injected byte was content the agent had already received
verbatim.** Not a rounding error — a third of the mechanism's entire cost is
pure repetition.

The first measurement caught this as 3 events over one idle gap, which looked
like it might be a one-off. It is not. The same small set of files kept being
re-delivered, unchanged, turn after turn, and the count grew monotonically:
`mid-session.md` — a 665-byte file — was sent four separate times.

The timeline shows the shape of it:

```
2026-08-19T17:34:49   REINJECT 00-diagrams.md   7081 B  hash=a0a5aeb0
2026-08-19T17:42:28   REINJECT mid-session.md    665 B  hash=f580648d
2026-08-19T17:42:28   REINJECT README.md        1149 B  hash=24fb29f3
        ... session idle overnight ...
2026-08-20T05:06:25   REINJECT 00-diagrams.md   7081 B  hash=a0a5aeb0   <-- again
2026-08-20T05:06:25   REINJECT mid-session.md    665 B  hash=f580648d   <-- again
2026-08-20T05:06:25   REINJECT README.md        1149 B  hash=24fb29f3   <-- again
```

Byte-identical payloads, same MD5, delivered a second time on the first user
turn after an idle gap — for files that had not changed in between.

**Hypothesised cause:** pending-notification state is marked for delivery but
not cleared once delivered, so later flushes re-emit it. That specific
inference is not confirmable from the transcript alone, but the *symptom* is
counted and byte-exact.

The second oddity strengthens it. **Fifteen of the twenty-eight events — the
single largest bucket, 48,809 bytes — follow `SendUserFile`**, a read-only
delivery operation that modifies nothing at all. A tool that cannot dirty a
file should never be able to trigger a resync. What it *can* do is mark a turn
boundary at which a pending queue gets flushed. Every one of those fifteen was
a repeat or a delayed delivery of a notice generated by an earlier shell edit.

Taken together: the harness appears to keep a set of "files needing resync"
that is appended to on shell-mediated writes and flushed on turn boundaries,
but not reliably emptied by a successful flush.

---

## What led to it — the part that is my fault, not the harness's

The trigger condition is "in-context file modified out of band". Two habits in
this session manufactured that condition repeatedly:

**1. Editing files through shell heredocs instead of the `Edit` tool.** To make
several small edits at once I wrote `python3 - <<'PY' ... PY` blocks that opened
files, did string replacements, and wrote them back. Convenient, one tool call
for four files — and each one converted a free edit into a full resync. Every
one of the seven `Bash`-triggered re-injections was this pattern.

**2. Reading large files into context that never needed to be there.** A file
that was never read is never re-injected, no matter how large or how often it
changes. `docs/img/solution.svg` (131 KB) was rewritten by a build step and cost
nothing, because it was never read. `task1770.ipynb` cost 30k tokens because it
was.

So the honest causal chain is:

```
oversized directory          (my setup)
  → agent reads large files  (my instruction)
    → agent edits via shell  (my convenience)
      → harness cannot attribute the change
        → full-file resync, ~14× the diff
          → occasionally delivered twice
            → session limit
```

Only the last two links belong to the harness. The first three were choices.

---

## Correction to M4 in [03-mitigations.md](03-mitigations.md)

This finding partly contradicts advice I gave earlier in this repo, so it needs
stating plainly rather than quietly amending.

M4 says "emit a patch script, never a rebuilt file". That is still right, but
the reasoning was incomplete, and applied naively it makes things **worse**:

- A patch script runs via `Bash`. If the target file is **already in context**,
  running it triggers exactly the resync described above. You pay the patch
  script *and* the resync.
- The patch script only wins when the target file was **never read into
  context**. Then the edit is genuinely free.

**Corrected rule:**

| situation | cheapest tool |
|---|---|
| File is in context, small change | `Edit` — zero resync |
| File is in context, large restructure | `Edit` repeatedly, or accept one resync |
| File was never read, any change | patch script via shell — free |
| File is huge and you can avoid reading it | **never read it**; script all changes |

The strategic version: decide up front which large files the agent is allowed
to read, keep that set as small as possible, and touch everything else only
through scripts. "Don't read it" is a stronger mitigation than "edit it
cheaply".

---

## What a harness could change

Ranked by the measured cost of not doing it:

1. **Don't re-send content already delivered.** Track delivered hashes; skip
   the resync if the file's current content matches what the agent last
   received. Would have saved 39,573 B — a third of the total — for free.
2. **Send a diff, not a window.** Both versions are known. A 562-byte change
   should cost roughly 562 bytes, not 8,156.
3. **Attribute shell-mediated writes where possible.** A `Write`-equivalent
   performed by a script is not observably different from an `Edit` in its
   effect; a content hash comparison after each `Bash` call would let the
   harness skip resyncs for files whose content is unchanged, and diff the rest.
4. **Expose the number.** A per-turn breakdown of input tokens by source would
   have made this diagnosable in minutes instead of days. `context_audit.py`
   and `transcript_forensics.py` exist only because that breakdown isn't there.

---

## Reproduce this yourself

```bash
ls -t ~/.claude/projects/*/*.jsonl | head        # find your transcript
python3 tools/transcript_forensics.py <that file>
```

Look for: re-injections clustered after `Bash`, a zero count after
`Edit`/`Write`, and any non-zero `duplicated events`. If your numbers look like
the ones above, the same mechanism is operating on your session.

## …and on a different tool

This is **n = 1**. One harness, one version, one directory. Everything above
could be universal or could be an artefact of this specific setup, and I cannot
tell which from inside it.

[`prompts/replication-test.md`](../prompts/replication-test.md) is a neutral
five-minute A/B you can run on another coding agent or another Claude harness:
make the same edit with the native edit tool, then with
a shell command, then with a `touch` that changes nothing, and compare what
comes back. It is deliberately written not to lead the model, and it treats a
null result as a first-class finding — a harness that handles this correctly is
the most valuable data point available, because it proves the cost is
avoidable rather than inherent.

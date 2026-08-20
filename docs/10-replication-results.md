# 10 — Replication results

One row per tool tested. **Null results belong here as much as positive ones** —
a harness that handles this correctly is the most valuable entry in the table,
because it proves the cost is a choice rather than a law.

Protocol: [`prompts/replication-test.md`](../prompts/replication-test.md).
Gemini CLI specifics: [09-gemini-cli-runsheet.md](09-gemini-cli-runsheet.md).

---

## Results

Deltas are **input tokens added by that turn**, measured against turn D (the
"say ok" control), which is the floor cost of any turn. `D` itself is the
absolute floor, not a delta.

| Tool | Version | Model | D (floor) | A (native edit) | B (shell edit) | C (`touch`) | Reading |
|---|---|---|---:|---:|---:|---:|---|
| Claude Code / Cowork | *(session of 17–19 Aug 2026)* | claude-opus-5 | n/a | **0** | resync | not tested | Re-sync on shell-mediated writes only; 14.5× amplification; 34.4% duplicates |
| claude.ai (`view` / `bash_tool`) | 20 Aug 2026 | Claude | n/a | no content | no content | no content | **INCONCLUSIVE** — precondition failed + wrong observation window. See below |
| Gemini CLI | | | | | | | |
| Aider | | | | | | | |
| Cline | | | | | | | |
| Cursor | | | | | | | |
| | | | | | | | |

> The Claude row is filled from transcript parsing rather than the A/B/C
> protocol, which did not exist yet when that session ran. Its `A = 0` is
> strong (54 native edits, zero re-syncs) but it is not the same measurement as
> the other rows will be. **Re-run the protocol against Claude Code too**, so
> the table compares like with like. Until then the row is marked as what it
> is.

## How to read a row

| Pattern | Conclusion |
|---|---|
| B ≫ A, both ≫ D | Resyncs on out-of-band writes only — the documented mechanism |
| A ≈ B ≫ D | Resyncs on every change — more expensive, but at least predictable |
| A ≈ B ≈ D | No resync. Either it diffs, or it tracks without re-sending |
| C ≫ D | Keyed on mtime rather than content hash — unchanged bytes still cost |
| `cache` rises, `input` flat | Re-sending, but provider-cached. Cheap, so a different story |

---

## Per-tool notes

### Claude Code / Cowork

Measured by parsing the session transcript
(`~/.claude/projects/<slug>/<id>.jsonl`) with
[`tools/transcript_forensics.py`](../tools/transcript_forensics.py). Full
analysis in [07-the-actual-bug.md](07-the-actual-bug.md).

- 54 `Edit`/`Write` calls → 0 re-injections
- 26 re-syncs of in-context files, all following shell-mediated writes
- 114,931 bytes re-injected (~32,000 tokens)
- 13 byte-identical duplicates, 39,573 B (34.4%)
- n = 1 session, one version

### claude.ai surface (`view` / `bash_tool` / string-replace edit) — INCONCLUSIVE

A different harness from Cowork/Claude Code: different tool names, different
file semantics. Run against the **first version** of the protocol, which had two
design flaws. The run is recorded because it is what *found* them.

**Reported observations** (accurate as far as they go):

- Native edit returned only `Successfully replaced string in /home/claude/test_subject.txt`
- Shell edit returned only `{"returncode":0,"stdout":"","stderr":""}`
- `touch` returned the same
- No file content in any of the three tool results
- **No token or context counter exposed by any available tool** — correctly
  reported as "genuine no data", not estimated
- `/mnt/transcripts` exists as a mount point but was empty; no transcript written

**Why this cannot be scored as a null:**

1. **The precondition failed and the run continued anyway.** The `view` call
   returned lines 1–149 and 652–801 with `< truncated lines 150-651 >` in
   between. ~500 lines were never in context. The mechanism under test only
   applies to files fully held in context — so there was nothing to re-send.
   The test never started.

2. **The observation window was inside the turn.** The protocol said "immediately
   report", and the session correctly did. But in the Cowork session where this
   was originally measured, resync notices arrive as system messages at the
   **start of the following turn**, never in the tool result. Checking inside
   the turn looks before they arrive.

3. **No usage counter.** The strongest available axis — a measured input-token
   delta — was simply unavailable. Two of three instruments dead.

All three biases point the same way: **toward a false negative.**

**What it did establish, and these are real:**

- This harness **truncates large file reads** (~150 lines in, ~150 at the end,
  middle elided). That is itself a context-exposure mitigation: a file that is
  never fully read can never be fully re-sent. Worth noting as a design choice
  other harnesses could adopt.
- No usage instrumentation is exposed to the model on this surface, which makes
  self-report the only channel — and self-report is exactly what this protocol
  should not rely on.
- Shell working directory does not persist between `bash_tool` calls; each
  invocation starts fresh. Incidental, but consistent with Cowork behaviour.

**Retest required** with the multi-turn protocol and a 200-line file.

### Gemini CLI

*(fill in)*

Raw `/stats` output:

```
```

`gemini --version`:

Notes:

### Aider

*(fill in)*

### Cline

*(fill in)*

### Cursor

*(fill in)*

---

## Interpretation, once there are ≥3 rows

Write it here, and keep it proportionate to the evidence:

- If most tools show the pattern → this is a **class of behaviour in agentic
  tooling**, not one vendor's defect, and the interesting question becomes
  which design avoids it and at what cost.
- If most don't → the original finding is **version- or vendor-specific**, which
  is a smaller but perfectly honest result. Say so plainly.
- If the duplicate behaviour appears nowhere else → that specific defect is
  narrow, and the generalisable contribution is the **measurement method**, not
  the bug.

Whichever it is, state it in one paragraph and resist making it larger than the
rows support. The table is the finding; the prose is commentary.

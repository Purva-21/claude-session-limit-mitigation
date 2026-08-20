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

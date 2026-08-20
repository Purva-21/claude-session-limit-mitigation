# 02 — Mechanism

> **Status: superseded in part — read [07-the-actual-bug.md](07-the-actual-bug.md)
> first.** This file was written as a hypothesis, before the session transcript
> was examined. The transcript has since been parsed
> ([`tools/transcript_forensics.py`](../tools/transcript_forensics.py)) and the
> core mechanism is now **measured**: re-injection fires when a file already in
> context is modified out of band (by a shell command or script), and never
> after an `Edit`/`Write` — 37 in-context edits produced 0 re-injections, while
> every one of the 11 re-syncs followed a shell-mediated change.
>
> The reasoning below still holds and is worth reading for the alternatives it
> rules out. But where this file says "inferred", doc 07 has the number.

## The claim

The session limit was reached primarily through **input amplification**, not
output volume. A long agentic session pays for its working directory on every
turn, not once.

## The mechanism, step by step

1. An agent reads a file to work on it. That file's contents enter context.
2. The agent edits the file — or a tool, a build step, or a sync process
   changes it.
3. The harness detects that a file already in context has changed on disk, and
   re-sends the current contents so the agent is not reasoning from a stale
   copy. This is correct and necessary behaviour: an agent editing against a
   stale view of a file produces broken patches.
4. Steps 2–3 repeat for every iteration.

The cost per turn is therefore proportional to **the size of the files being
touched**, not to the size of the change. A one-line fix in a 106 KB notebook
costs approximately 106 KB.

## Why this fits the observations

- **Symptom 1** (limit out of proportion to visible work) follows directly: the
  expensive part of the turn is invisible in the transcript.
- **The measured 5.5× budget overrun** is the quantitative form of it. Fifteen
  hot files, 277,530 estimated tokens for a single full read, and an iterative
  workflow that touches several of them per round.
- **Symptom 4** (rebuild-instead-of-patch) is the amplifier: regenerating a
  notebook guarantees the change-detection path fires on the largest file
  present.
- **Symptom 3** (repeated re-verification) multiplies the number of rounds over
  which the fixed cost is paid.

## Contributing factors, ranked by measured weight

| # | factor | evidence | est. weight |
|---|---|---|---|
| 1 | Oversized working directory (15 hot files, 277k tokens) | auditor output | dominant |
| 2 | Stored notebook outputs (~108 KB in one file alone) | auditor `--json` notes | large, and trivially removable |
| 3 | Rebuild rather than patch | 106 KB notebook regenerated repeatedly | large |
| 4 | Superseded artifacts never deleted | 4 obsolete notebooks, ~110k tokens | large |
| 5 | Repeated verification rounds over unchanged state | 4 rounds re-proving one fix | moderate |
| 6 | Sub-agent work not checkpointed to disk | blind-gate round lost entirely | moderate; catastrophic when it fires |

Note that factors 1–4 are all the same underlying thing viewed from different
angles: **too much large, unnecessary material within reach of the agent.**

## Alternative explanations considered

- **The model generated hidden or looping output.** Not supported — visible
  output volume per turn was unremarkable, and no retry loops were observed.
- **The task was simply long.** Partly true, and not a competing explanation.
  A three-day iterative task is expensive. But a 5.5× measured overrun on the
  directory alone accounts for the shortfall without needing the task's length
  to be pathological.
- **Sub-agents are inherently expensive.** Likely true and relevant, but the
  observed failure was that the sub-agent was *killed*, not that it was costly.
  That is a scheduling/precedence behaviour, not an amplification one — hence
  its separate mitigation.

## What would settle it

None of these are available from inside a session, and all of them are things a
harness could expose:

- A per-turn breakdown of input tokens by source (conversation vs. file
  re-injection vs. tool results).
- A log line whenever a file's contents are re-sent, with the byte count.
- A warning when a single file crosses some fraction of the turn budget.
- Graceful degradation for sub-agents at the limit: checkpoint and report
  partial state rather than terminate.

Until then, `tools/context_audit.py` is a proxy: it measures the *exposure*,
which is the part you control.

## The practical consequence

Because the mechanism is amplification of input you chose to make available,
**the fix is in your working directory, not in your prompt.** Every mitigation
in [03-mitigations.md](03-mitigations.md) reduces exposure, and they all work
irrespective of whether the amplification is happening exactly as described
here.

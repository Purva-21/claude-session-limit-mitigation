# 06 — When it happens anyway

The rest of this repo is prevention. This page is the incident runbook: what to
do in the ninety seconds before the limit lands, and how to recover when it has
already landed and you have no checkpoint.

Prevention fails sometimes. That is not a reason to have no plan for it.

---

## Phase 1 — Warning signs (you still have a few turns)

You are close if you notice any of these:

- Responses getting slower or shorter, or the agent summarising instead of
  doing.
- The agent re-reading a file you know it has already read this session.
- A rebuild of something large just started.
- You are three or more hours into iterative work on the same directory.
- Any harness warning about context or usage.

**Do this immediately, in one message:**

```
We may be close to a session limit. Stop starting new work.
1. Capture every edit so far in a re-runnable patch script and verify it
   reproduces the current state from the original input.
2. Write STATE.md: goal / done / pending / ruled out and why / open questions /
   which files to read and which not to.
3. Save the current test and validator output to a file.
Then stop.
```

This is [`prompts/checkpoint.md`](../prompts/checkpoint.md) compressed. Ninety
seconds spent here saves a day.

**Do not** start a "quick last thing". The last thing is what gets truncated
mid-write.

---

## Phase 2 — It just hit

The session is gone. Nothing you type brings it back, and the transcript is not
the recovery path — the files are.

**Do not** immediately open a fresh session and say "carry on". You do not yet
know what state the disk is in, and an agent that starts editing a
half-written file will produce confident nonsense on top of corruption.

**Run triage first:**

```bash
python3 tools/salvage.py /path/to/project --since 120 --write-state
```

It reports, read-only:

| section | why it matters |
|---|---|
| Corrupt / truncated JSON and notebooks | a file that no longer parses was being written when the kill landed |
| Zero-byte files | a write killed at `open()` truncates before it writes |
| `.tmp` / `.partial` / `.swp` leftovers | often hold newer content than the real file |
| Files written in the danger window | the newest entry is where the session died |
| Competing versions (`x.ipynb` vs `x_patched.ipynb`) | decide which is authoritative *before* an agent reads both |
| Patch scripts present | re-run these from pristine input rather than trusting output files |
| Git state | what is recoverable, and what was never committed |

It exits `1` if anything is corrupt, and `--write-state` drafts a `STATE.draft.md`
with the machine findings appended.

### The order of recovery

1. **Fix corruption first.** `git checkout -- <file>`, or re-run the patch
   script from the original input. Never hand-repair a truncated notebook —
   you will miss something.
2. **Resolve competing versions.** Pick one, move the losers into
   `artifacts/`. Two files that disagree about which is current is how a
   session's worth of work gets silently discarded.
3. **Fill in `STATE.draft.md` by hand and rename it.** The generated headings
   are deliberately empty. Only you know what was ruled out and why, and
   **that is the expensive part** — the findings, the numbers, the approaches
   that looked right and weren't. Everything else can be re-derived from the
   files.
4. **Run `tools/prep_workspace.sh --apply`.** The directory is now bigger than
   when you started; it grew all session.
5. **Open the fresh session with [`prompts/resume.md`](../prompts/resume.md)**,
   and make it summarise its understanding *before* it touches anything.

---

## Phase 3 — The lockout window

You are told the limit resets at some time. That interval is not dead time; it
is the only unhurried moment you will get.

Useful things to do without an agent:

- **Write the `STATE.md` properly.** With no agent to lean on, you write what
  you actually know. These are usually the best handoff notes you'll produce.
- **Run the audit and clean up.** `context_audit.py`, then delete what nothing
  reads. No agent required.
- **Reconstruct the patch script by hand** if edits were made directly. Tedious
  once; then it's re-runnable forever.
- **Decide what to cut.** Sessions die on scope as much as on tokens. Ask which
  part of the task is actually load-bearing — in the case study behind this
  repo, an entire computed output (a per-cell stress tensor) was carried
  through the whole task and consumed by nothing.
- **Commit.** If the directory is not a git repo, make it one now. Every
  recovery above is easier with a commit to diff against, and half are
  impossible without one.

---

## Phase 4 — The post-mortem question

Once recovered, ask one question: **was the work lost, or only delayed?**

- *Only delayed* — you had a checkpoint. The system worked. Nothing to change.
- *Lost* — something was in flight with no on-disk trace. That is the thing to
  fix, and it is almost always one of:
  - work running in a sub-agent that wasn't writing results incrementally,
  - a rebuild in progress instead of a patch script,
  - a finding that existed only in the conversation and was never written down.

The case study behind this repo lost a blind clean-room measurement to exactly
the first of those, and could not even diagnose it afterwards because earlier
attempts had been deleted for tidiness. Both failures were free to prevent and
expensive to suffer.

---

## The uncomfortable one

If you are hitting limits repeatedly on the same task, the honest reading is
usually not that the limit is too low. It is that the task is too big to be one
task.

Splitting it — three sessions of two hours joined by handoff artifacts, instead
of one six-hour session holding everything — costs a little redundancy and buys
you a workflow where no single failure loses more than one interval. Diagram 5
in [`00-diagrams.md`](00-diagrams.md) is that shape.

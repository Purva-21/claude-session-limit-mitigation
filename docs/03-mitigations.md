# 03 — Mitigations

Ranked by measured or estimated effect in the session described in
[01-observed-behaviour.md](01-observed-behaviour.md). Each entry states what to
do, why it works, and how to verify it worked.

---

## M1 — Audit the working directory before you start (biggest single win)

**Do:**

```bash
python3 tools/context_audit.py /path/to/project --turns 3
```

Anything marked `critical` or `high` is a file whose full contents will be
carried repeatedly. Move it, strip it, or delete it before the agent ever sees
it.

**Why:** the session's directory measured 277,530 tokens for one full read of
its hot files, against a 200k budget. The overrun was structural — present
before any work happened.

**Verify:** re-run the auditor; `worst case over N edits` should be under your
budget. The script exits `1` when it isn't, so:

```bash
python3 tools/context_audit.py . --budget 200000 || echo "reduce before starting"
```

---

## M2 — Strip notebook outputs

**Do:**

```bash
python3 tools/nb_strip.py /path/to/project --inplace
# or, equivalently, with jupyter installed:
jupyter nbconvert --clear-output --inplace *.ipynb
```

Add a guard so they don't come back:

```bash
pip install nbstripout && nbstripout --install   # git filter, strips on commit
```

**Why:** `executed_solution.ipynb` was 163 KB of which ~108 KB was stored
output — images, arrays, tracebacks that nothing read. That is a 66% reduction
on the largest file in the directory from a single command.

**Verify:** `python3 tools/context_audit.py . --json | grep -c "stored outputs"`
should print `0`.

---

## M3 — Move build artifacts out of reach

**Do:** keep generated output in a directory the agent is told not to read.

```
project/
  src/            # agent works here
  tests/          # agent works here
  artifacts/      # generated; agent never reads unless asked
```

Declare it. An `AGENTS.md` or `CLAUDE.md` at the repo root is read by most
agent harnesses — see `examples/AGENTS.md.sample`.

**Why:** four superseded notebooks (`executed_solution.ipynb`,
`epithelial_activity_scicode_{task,solution}.ipynb`,
`scicode_..._length_scale.ipynb`) carried roughly 110k estimated tokens and
were consumed by nothing after the round that produced them.

**Verify:** the auditor's top-10 should contain only files you would actually
open by hand.

---

## M4 — Emit a patch script, never a rebuilt file

**Do:** when a large structured file (notebook, JSON, generated config) needs
changing, write a script that mutates the specific cells or keys, and run it.
See `examples/patch_template.py`.

```python
# not this
nb = build_entire_notebook()          # regenerates 106 KB
json.dump(nb, open(path, "w"))

# this
nb = json.load(open(path))
nb["cells"][26]["source"] = restored_background   # one cell
json.dump(nb, open(out, "w"))
```

**Why, four separate reasons:**

- The patch is the size of the change, not the size of the file.
- **It survives session death.** A patch script is re-runnable in a fresh
  session; a half-finished rebuild is not.
- It is reviewable — a human can see exactly what changed.
- It preserves whatever else touched the file (metadata, sync-side edits) that
  a rebuild would silently overwrite.

**Verify:** diff the before/after and confirm only the intended cells moved.

---

## M5 — Don't put verification in a sub-agent

**Do:** run diagnostics, validators and test suites in-process. If you must
delegate, make the sub-agent **write its result to disk as it goes**, so a kill
leaves a partial artifact rather than nothing.

**Why:** the session's most expensive single loss was a blind clean-room
measurement killed mid-run. Sub-agents appear to be shed first when a limit is
reached, and an unfinished measurement is worth zero, not "less".

**Verify:** kill the session deliberately mid-run in a test. If nothing usable
is on disk, the delegation is unsafe.

---

## M6 — Batch verification into one command

**Do:** one shell invocation that runs the validator, the test suite and the
structural checks and prints a compact summary — instead of ten calls whose
outputs each re-enter context.

```bash
python3 qc/run_all.py 2>&1 | tail -40
```

**Why:** each tool call carries its own output into context permanently. Ten
50-line outputs cost more than one 40-line summary, and tell you less.

**Verify:** count tool calls per verification round. Target is one.

---

## M7 — Delete intermediates the moment they are consumed

**Do:** if a file was produced to feed exactly one downstream step, remove it
after that step. Especially executed notebooks, cached JSON and superseded
versions.

**But:** do not delete anything you may need to *diagnose*. In this session a
set of blind-gate attempts was deleted for tidiness, and when the next round
failed there was nothing left to compare against. The rule is: delete large
outputs, keep small evidence.

**Verify:** the directory should contain no file older than the current round
that isn't source or input.

---

## M8 — Checkpoint into re-runnable artifacts, and split the session

**Do:** at each natural boundary, produce something that lets a *fresh* session
resume without replaying history:

- a patch script that encodes all edits so far,
- a short `STATE.md` recording what is done, what is pending, what was ruled
  out and why,
- the current test/validator output.

Then start a new session.

**Why:** limits are per-session. A session that can be abandoned cheaply is
never a disaster. One that holds the only copy of three days of reasoning is.

**Verify:** hand the checkpoint to a colleague (or a fresh session) and ask
them to continue. If they need to ask you anything, the checkpoint is
incomplete.

---

## M9 — Diff the delivered artifact against your local copy before disputing anything

**Do:** before arguing that a report, judge finding or reviewer comment is
stale, confirm you and they are looking at the same bytes.

```python
import json
a = json.load(open('synced.ipynb'))['cells']
b = json.load(open('local.ipynb'))['cells']
S = lambda c: ''.join(c['source'])
for i in range(min(len(a), len(b))):
    if S(a[i]).strip() != S(b[i]).strip():
        print(i, 'synced=%d ch  local=%d ch' % (len(S(a[i])), len(S(b[i]))))
```

**Why:** three rounds were spent dismissing correct findings as stale. The
synced copy had been truncated from 22,624 characters to 2,875 — an 87% cut
that removed exactly the content the reviewers said was missing. Each wasted
round paid the full directory cost again.

**Verify:** a clean diff. A large size drop on a prose cell is the tell.

---

## Combined effect — measured, not estimated

M1–M4 were applied in stages to a copy of the session's actual working
directory, re-running the auditor after each stage. Reproduce with
[`04-reproduction.md`](04-reproduction.md).

| stage | action | hot tokens, one full read |
|---|---|---:|
| 0 | baseline | 273,468 |
| 1 | delete 6 superseded artifacts | 100,895 |
| 2 | strip remaining notebook outputs | 100,880 |
| 3 | move 4 generators to `artifacts/` **and declare it off-limits** | 55,418 |

**4.9× reduction**, from changes that alter no code. The modelled worst case
over three edit turns falls from 1,093,872 to 221,672 tokens — from 5.5× a
200k budget to 1.11×.

Two honest notes on that table, because both are instructive:

- **Stage 2 saved almost nothing (15 tokens).** Not because stripping outputs
  is useless — it is M2 for good reason — but because the output-heavy
  notebooks had *already been deleted* in stage 1. The two wins overlap. If you
  cannot delete the notebooks, stripping recovers most of the same ground; if
  you can, do that first and the strip is free insurance.

- **Stage 3 only works if you declare the directory off-limits.** Moving files
  into `artifacts/` changed the measurement by exactly zero until the auditor
  was told to skip it (`--exclude artifacts`). An agent walks subdirectories
  too. The reduction comes from the *instruction* in `AGENTS.md`, not from the
  `mv`. This is the single easiest mitigation to believe you have applied when
  you have not.

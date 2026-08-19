# Surviving session limits in long agentic coding sessions

A field report and a toolkit. During a multi-day task (building and debugging a
SciCode benchmark notebook) a Claude Opus 5 Cowork session repeatedly hit its
session limit mid-work — including killing a sub-agent in the middle of a
measurement run, which destroyed the result rather than merely delaying it.

This repo documents what was actually measured, what the likely mechanism is,
and — the part you probably came for — the concrete changes that stopped it
happening.

## The one-paragraph version

The limit was not being consumed by long answers. It was being consumed by
**re-reading**. Large files in the agent's working directory get pulled back
into context whenever they change on disk, and in a session where the agent is
iteratively editing a 100 KB notebook, that means a six-figure token bill per
turn for work that produced a twenty-line diff. Auditing the working directory
and switching from *rewrite* to *patch* cut the per-turn cost by roughly an
order of magnitude.

## Measured, in the session that prompted this

Running the included auditor against that session's working directory:

```
files scanned              : 36
hot files (>= 4000 tok)    : 15
one full read of hot files : 277,530 tok
worst case over 3 edits    : 1,110,120 tok
vs 200,000-token budget    : 5.5x
```

The four worst offenders were all notebooks the task itself generated:

| file | est. tokens | of which stored outputs |
|---|---|---|
| `executed_solution.ipynb` | 46,641 | ~108 KB of 163 KB |
| `scicode_..._length_scale.ipynb` | 34,217 | ~21 KB of 120 KB |
| `task1770.ipynb` | 30,266 | ~27 KB of 106 KB |
| `task1770_patched.ipynb` | 26,161 | — |

`executed_solution.ipynb` was a build artifact. Nothing read it after it was
produced. It sat in the working directory for the entire session as a 46k-token
liability.

## Is this "a bug in Claude Opus 5"?

Honest answer: **not demonstrably, and this repo does not claim it is.** What is
directly observable from inside a session is the effect — the limit arriving far
sooner than the visible work justifies. The dominant *measurable* contributor is
context amplification at the harness level (file-change re-injection ×
oversized working directory), not a model reasoning defect. Harness internals
are not inspectable from inside the session, so [`docs/02-root-cause.md`](docs/02-root-cause.md)
is explicitly labelled as inference and separates what was observed from what is
hypothesised.

The mitigations in [`docs/03-mitigations.md`](docs/03-mitigations.md) work
regardless of which layer is responsible, because they reduce the input the
session has to carry.

## How to stop it happening — one command and one prompt

**Step 1 — fix the directory.** One command, dry-run by default:

```bash
tools/prep_workspace.sh /path/to/your/project            # show what it would do
tools/prep_workspace.sh /path/to/your/project --apply    # do it
```

It audits, strips notebook outputs, moves large generated files into
`artifacts/` (moves — it never deletes), installs an `AGENTS.md` declaring that
directory off-limits, and re-audits. Run against the directory from this
session:

```
before :  277,530 tok   (5.5x a 200k budget)
after  :   40,314 tok   (0.8x)
```

**6.9× in one command.** Afterwards, look in `artifacts/` and move back
anything you're actually editing — size is a proxy for "generated", and the
script cannot tell your deliverable from a stale build.

**Step 2 — tell the agent the rules.** Paste
[`prompts/session-start.md`](prompts/session-start.md) as your first message.
If you want one sentence instead of a page, use
[`prompts/one-liner.txt`](prompts/one-liner.txt):

> Work in small diffs: never regenerate a file over 20KB — write a patch script
> that edits the specific parts and run it. Keep generated artifacts out of the
> working directory. Batch all checks into one command. Before you tell me a
> report is wrong, diff the delivered file against your local copy.

**Step 3 — for a project you'll return to,** commit
[`examples/AGENTS.md.sample`](examples/AGENTS.md.sample) as `AGENTS.md` at the
repo root and stop pasting anything. Most harnesses read it automatically.

That's the whole fix. Everything below is why it works and how it was measured.

### Individual tools

```bash
python3 tools/context_audit.py PATH            # what will this cost me?
python3 tools/nb_strip.py PATH --inplace       # strip notebook outputs
python3 tools/context_audit.py . --budget 200000 || echo "too heavy"
```

`context_audit.py` exits `1` when the modelled worst case exceeds the budget, so
it drops into a Makefile, a pre-commit hook or CI without extra glue.

## Contents

| path | what it is |
|---|---|
| [`docs/01-observed-behaviour.md`](docs/01-observed-behaviour.md) | What actually happened, with numbers and timestamps |
| [`docs/02-root-cause.md`](docs/02-root-cause.md) | Mechanism — observation vs. inference, kept separate |
| [`docs/03-mitigations.md`](docs/03-mitigations.md) | The nine changes, ranked by measured effect |
| [`docs/04-reproduction.md`](docs/04-reproduction.md) | How to reproduce and how to measure it yourself |
| [`docs/05-checklist.md`](docs/05-checklist.md) | One-page checklist to paste into your own runbook |
| [`prompts/`](prompts/) | **Copy-paste prompts** — session start, mid-session corrections, checkpoint, resume |
| `tools/prep_workspace.sh` | One command that applies the cleanup mitigations |
| `tools/context_audit.py` | Scans a directory, reports re-injection cost |
| `tools/nb_strip.py` | Strips notebook outputs in place |
| `examples/patch_template.py` | Cell-targeted notebook patch script (the rewrite alternative) |
| `examples/AGENTS.md.sample` | Directory conventions that keep the agent out of hot files |
| `.github/workflows/context-budget.yml` | CI job that fails when the repo gets too expensive |

## Measured result

Applying the mitigations in stages to that session's actual directory, with the
auditor re-run after each stage:

| stage | hot tokens, one full read |
|---|---:|
| baseline (working copy, QC harness excluded) | 273,468 |
| delete 6 superseded artifacts | 100,895 |
| strip remaining notebook outputs | 100,880 |
| move generators aside **and declare them off-limits** | 55,418 |

**4.9×**, without changing a line of the actual work. Two of those rows are
nearly flat, and [`docs/03-mitigations.md`](docs/03-mitigations.md) explains why
rather than hiding it — the second and third mitigations overlap, and moving
files into a subdirectory achieves nothing unless the agent is told to skip it.

(The 273,468 baseline is measured on a copy with the QC harness subdirectory
excluded; the 277,530 figure at the top of this page is the full directory.
Same directory, 1.5% apart — the staged run used a copy so the original was not
mutated.)

## The short list, if you read nothing else

1. Never leave a large generated artifact in the agent's working directory.
2. Strip notebook outputs before an agent touches the notebook.
3. Emit a **patch script**, not a rewritten file — it is smaller, reviewable,
   and re-runnable after the session dies.
4. Do verification **in-process**, not in sub-agents; sub-agents are the first
   thing a limit kills, and a half-finished measurement tells you nothing.
5. Batch verification into one command instead of ten.
6. Delete intermediates the moment they are consumed.
7. Checkpoint by delivering a re-runnable artifact, then start a fresh session.

## Licence

MIT. See [LICENSE](LICENSE).

# 01 — Observed behaviour

Everything in this file was observed from inside the session. Nothing here is
inferred; inference lives in [02-root-cause.md](02-root-cause.md).

## Setting

A single long-running Claude Opus 5 Cowork session, spanning roughly three
calendar days (17–19 Aug 2026), whose task was to build, validate and repair a
SciCode benchmark notebook: a 31-cell Jupyter notebook with two subproblems and
one main problem, plus a reference solution, a test suite, a mutation-testing
harness and a QC validator.

The work was genuinely iterative — build, run a validator, read judge findings,
patch, re-run — which is exactly the shape of task where this failure mode
shows up.

## Symptom 1 — the limit arrives out of proportion to the visible work

Turns that produced small outputs (a 20-line test case, a three-line edit to a
patch script) consumed budget as though they had produced very large ones. The
session hit `You've hit your session limit · resets 11:20am` while the visible
conversation contained no correspondingly large amount of generated text.

## Symptom 2 — a sub-agent was killed mid-run, destroying the result

The most expensive single incident. A sub-agent had been spawned to run the
third round of a *blind clean-room gate* — an independent implementer writing
the solution from the prompt text alone, used to estimate the benchmark's pass
rate. The limit was reached while that sub-agent was running.

The consequences compounded:

- The round produced **no** result, not a partial one. A half-finished blind
  test is not a weaker signal, it is no signal.
- Earlier attempts had already been deleted to keep the directory tidy, so the
  failed round could not be diagnosed retrospectively either.
- The measurement had to be re-run from scratch in a later session.

Sub-agents appear to be the first thing shed when a limit is reached. Treat any
work delegated to one as *lossy* unless it checkpoints its own output to disk.

## Symptom 3 — repeated re-verification of the same fact

Four separate rounds were spent re-proving the same fix, because each round
re-read the same large artifacts to confirm state that had not changed. Each
round was cheap in output and expensive in input.

A related and instructive failure from the same session: judges repeatedly
reported that an implementation contract was missing from a notebook's main
background cell. The local file was grepped each time, the content was found,
and the finding was dismissed as stale — three times. The *delivered* artifact
had been truncated from 22,624 characters to 2,875 in transit. Every judge was
right; the dismissals were expensive and wrong. The lesson is procedural rather
than about limits, but it is why four rounds were spent where one would do.

## Symptom 4 — rebuild-instead-of-patch

The notebook was, several times, regenerated wholesale rather than edited.
Regenerating a 106 KB notebook means the entire new content passes through the
session. Switching to a cell-targeted patch script
(`examples/patch_template.py` here) reduced that to the size of the diff plus
the script.

## The directory, measured

`tools/context_audit.py` run against the session's working directory:

```
files scanned              : 36
hot files (>= 4000 tok)    : 15
one full read of hot files : 277,530 tok
worst case over 3 edits    : 1,110,120 tok
vs 200,000-token budget    : 5.5x
```

Full ranking of the files large enough to matter:

| file | bytes | est. tokens | severity |
|---|---:|---:|---|
| `executed_solution.ipynb` | 167,909 | 46,641 | critical |
| `scicode_epithelial_activity_length_scale.ipynb` | 123,182 | 34,217 | critical |
| `task1770.ipynb` | 108,956 | 30,266 | critical |
| `task1770_patched.ipynb` | 94,178 | 26,161 | critical |
| `epithelial_activity_scicode_solution.ipynb` | 79,379 | 22,050 | high |
| `example.ipynb` | 74,130 | 20,592 | high |
| `epithelial_activity_scicode_task.ipynb` | 72,579 | 20,161 | high |
| `epithelial_activity_scicode.json` | 69,257 | 19,238 | high |
| `steps.py` | 64,403 | 17,890 | high |
| `steps3.py` | 38,811 | 10,781 | medium |
| `steps3_main.py` | 32,601 | 9,056 | medium |
| `solution.py` | 25,145 | 6,985 | medium |

The Python files that were actively edited during the session — and therefore
the most likely to be re-injected on change — totalled **2,337 lines /
116,909 bytes**:

`altsol.py` (335), `tests_main.py` (156), `tests_p1.py` (156), `steps3.py`
(681), `steps3_main.py` (530), `build3.py` (91), `sol3.py` (388).

## What stands out in that table

1. **Most of the weight is build output, not source.** `executed_solution.ipynb`
   was produced once and never read again. `epithelial_activity_scicode*` were
   superseded artifacts from an earlier structure. Together they carried close
   to 110k estimated tokens of pure liability.

2. **Notebook outputs dominate notebooks.** `executed_solution.ipynb` is 163 KB
   on disk of which roughly 108 KB is stored cell output — images, arrays,
   tracebacks. None of it was needed. `jupyter nbconvert --clear-output` would
   have removed 66% of the largest file in the directory in one command.

3. **Superseded versions were never deleted.** `task1770.ipynb` and
   `task1770_patched.ipynb` coexisted, together worth ~56k tokens, when only the
   latter mattered after the patch ran.

## What was *not* observed

- No evidence of the model looping, retrying silently, or generating hidden
  output. Turn-level output volume looked normal.
- No error or warning attributable to the model rather than the session limit.
- No way, from inside the session, to read a token meter, inspect what the
  harness re-injected, or confirm the re-injection hypothesis directly. That
  gap is the reason [02-root-cause.md](02-root-cause.md) is labelled inference.

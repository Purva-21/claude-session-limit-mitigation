# 04 — Reproduction and measurement

You cannot reproduce the session limit itself on demand — it depends on your
plan, your usage and the harness. What you *can* reproduce is the **exposure**
that causes it, and the reduction the mitigations achieve. That is what this
file does.

## A. Measure your own exposure (30 seconds)

```bash
python3 tools/context_audit.py /path/to/your/project --turns 3
```

Read three lines of the output:

- `one full read of hot files` — what you pay to bring the directory into
  context once.
- `worst case over N edits` — what an iterative session plausibly pays.
- `vs BUDGET` — the multiple. **Anything above 1.0× means the directory is
  structurally too expensive before you have done any work.**

Machine-readable, for scripting or CI:

```bash
python3 tools/context_audit.py . --json --budget 200000
```

Exit code is `1` when the worst case exceeds the budget.

## B. Reproduce the staged reduction

This is the exact sequence that produced the table in
[03-mitigations.md](03-mitigations.md). Substitute your own directory; the
shape of the result generalises.

```bash
set -e
cp -r /path/to/project /tmp/audit_demo
A() { python3 tools/context_audit.py /tmp/audit_demo "$@" --json \
        | python3 -c "import json,sys;d=json.load(sys.stdin);print(d['hot_tokens_single_pass'])"; }

echo "stage 0 baseline            : $(A)"

# stage 1 -- delete superseded / never-read artifacts
rm -f /tmp/audit_demo/executed_solution.ipynb \
      /tmp/audit_demo/epithelial_activity_scicode_solution.ipynb \
      /tmp/audit_demo/epithelial_activity_scicode_task.ipynb \
      /tmp/audit_demo/scicode_epithelial_activity_length_scale.ipynb \
      /tmp/audit_demo/epithelial_activity_scicode.json \
      /tmp/audit_demo/task1770.ipynb
echo "stage 1 superseded removed  : $(A)"

# stage 2 -- strip notebook outputs
python3 tools/nb_strip.py /tmp/audit_demo --inplace >/dev/null
echo "stage 2 outputs stripped    : $(A)"

# stage 3 -- move generators aside AND declare them off-limits
mkdir -p /tmp/audit_demo/artifacts
mv /tmp/audit_demo/steps.py /tmp/audit_demo/solution.py \
   /tmp/audit_demo/build_notebooks.py /tmp/audit_demo/example.ipynb \
   /tmp/audit_demo/artifacts/ 2>/dev/null || true
echo "stage 3 moved, not declared : $(A)"
echo "stage 3 moved AND declared  : $(A --exclude artifacts)"
```

Observed on the original directory:

```
stage 0 baseline            : 273468
stage 1 superseded removed  : 100895
stage 2 outputs stripped    : 100880
stage 3 moved, not declared : 100880
stage 3 moved AND declared  :  55418
```

Note the two flat rows. Stage 2 is flat because stage 1 had already removed
every notebook that carried outputs. `stage 3 moved, not declared` is flat
because relocating a file into a subdirectory does nothing on its own — the
agent walks it. Both are documented rather than hidden because they are the
mistakes a reader is most likely to make.

## C. Reproduce the sub-agent loss (safely)

You do not need to hit a real limit to prove the hazard.

1. Start a task that delegates a measurement to a sub-agent.
2. Interrupt it partway through — cancel the turn, or stop the session.
3. Look at disk. If the sub-agent's partial result is not there, the
   delegation was lossy: a real limit would have destroyed the work exactly the
   same way.

The fix is not "don't delegate" but "delegate only work that checkpoints".
Make the sub-agent append each result to a file as it produces it, so an
interruption leaves you with *k* of *n* results instead of nothing.

## D. Verify a mitigation actually landed

| mitigation | check |
|---|---|
| M1 audit | `python3 tools/context_audit.py . \|\| echo OVER` prints nothing |
| M2 strip | `python3 tools/context_audit.py . --json \| grep -c "stored outputs"` → `0` |
| M3 artifacts | `AGENTS.md` exists and names the directory; audit with `--exclude` matches audit without it |
| M4 patch | `git diff --stat` shows only the intended cells/keys changed |
| M5 sub-agents | interruption test in section C leaves a usable partial file |
| M6 batching | one tool call per verification round |
| M7 intermediates | no file older than the current round that isn't source or input |
| M8 checkpoint | a fresh session can continue from `STATE.md` + patch script alone |
| M9 diff | synced-vs-local cell diff is clean before you dispute a finding |

## Caveats on the numbers

- Token counts are **estimates** (characters ÷ 3.6). Ratios are reliable;
  absolute values are indicative. Use your provider's tokeniser if you need
  precision.
- The `--turns` model (each hot file re-injected once per edit turn) is a
  worst case, not a prediction. Real sessions touch a subset.
- The 200k default budget is a placeholder. Set `--budget` to whatever your
  session actually allows.
- None of this measures the harness directly. It measures what you expose to
  it, which is the part you can change.

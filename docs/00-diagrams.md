# 00 — Diagrams

Six pictures: the mechanism, where the cost went, what it compounds into, how to
fix it, and how a long task should be shaped. All Mermaid, so they render inline
on GitHub.

---

## 1. The mechanism — what decides whether an edit is free

Everything turns on one fork: **can the harness attribute the change to itself?**

```mermaid
flowchart TD
    A["Agent reads a file"] --> B["Contents in context.<br/>Harness tracks its state."]
    B --> C{"File gets modified.<br/><b>By what?</b>"}

    C -->|"<b>Edit / Write</b><br/>harness made the change,<br/>so it knows the diff"| OK["No re-sync.<br/><i>'file state is current<br/>in your context'</i>"]
    C -->|"<b>Bash · script · build step</b><br/>harness sees bytes that no longer<br/>match, and cannot attribute why"| RS["Re-sync:<br/>send the file back"]

    OK --> FREE(["<b>0 bytes.</b><br/>54 of 54 calls clean"])

    RS --> AMP["Sends a <b>window</b>, not a diff<br/>562 B edit → 8,156 B<br/><b>14.5×</b>"]
    RS -.->|"delivery queue not cleared<br/>on flush <i>(inferred)</i>"| DUP["Same bytes re-sent<br/>13 of 26 events · <b>34.4%</b>"]

    AMP --> B
    DUP --> B
    AMP --> FILL["Context fills"]
    FILL --> LIM["Session limit"]
    LIM --> LOST["Work in flight is<br/><b>lost</b>, not delayed"]

    style OK fill:#27ae60,color:#fff
    style FREE fill:#27ae60,color:#fff
    style RS fill:#e67e22,color:#fff
    style AMP fill:#e67e22,color:#fff
    style DUP fill:#c0392b,color:#fff
    style LIM fill:#c0392b,color:#fff
    style LOST fill:#c0392b,color:#fff
```

The re-sync itself is **correct behaviour** — an agent patching against a stale
copy produces broken patches. What makes it expensive is that it re-sends a slice
of the file when it could send a diff, and that it sometimes sends the same bytes
twice.

The left branch is the whole mitigation: an `Edit` costs nothing because the
harness already knows what changed.

> Status: **measured**, from the session transcript via
> [`tools/transcript_forensics.py`](../tools/transcript_forensics.py). Only the
> queue-flush explanation for the duplicates is inferred; the duplicates
> themselves are byte-identical and counted. Full write-up:
> [07-the-actual-bug.md](07-the-actual-bug.md).

---

## 1b. Anatomy of the 28 re-injections

Where the 114,931 re-injected bytes came from, by what preceded them.

```mermaid
pie showData
    title Re-injected bytes by trigger
    "Bash / script-mediated edits" : 49796
    "SendUserFile — a read-only op" : 48809
    "Initial reads (legitimate)" : 16326
```

Two of the twenty-eight were genuine first reads. The other twenty-six were
re-syncs of files already in context — and **not one** followed an `Edit` or
`Write`.

The `SendUserFile` slice is the damning one. It modifies nothing; it cannot
dirty a file. Yet it is the largest single trigger by count. That is not
detection, it is a pending queue flushing at a turn boundary — and since 34.4%
of all re-injected bytes were byte-identical repeats, the queue evidently is
not emptied by a successful flush.

---

## 2. What it actually cost here

The measured directory, by weight. Everything in red was **never read again**
after the round that produced it.

```mermaid
pie showData
    title Working directory, estimated tokens (top files)
    "executed_solution.ipynb (never re-read)" : 46641
    "...length_scale.ipynb (superseded)" : 34217
    "task1770.ipynb (superseded by patched)" : 30266
    "task1770_patched.ipynb (the deliverable)" : 26161
    "epithelial_...solution.ipynb (superseded)" : 22050
    "example.ipynb (reference)" : 20592
    "epithelial_...task.ipynb (superseded)" : 20161
    "everything actually being worked on" : 77442
```

Of 277,530 estimated tokens, roughly **173,000 were dead weight** — build
output and superseded versions. The task itself was the small slice.

---

## 3. The two habits that compound it

Same one-line change, two ways of applying it.

> **Read with diagram 1 in mind.** The patch script wins here *because the
> notebook was never read into context*. Run the same script against a file the
> agent has already read and you pay for the script **and** a full re-sync — see
> the corrected rule in [03-mitigations.md](03-mitigations.md#m4--emit-a-patch-script-never-a-rebuilt-file).

```mermaid
sequenceDiagram
    participant You
    participant Agent
    participant Disk

    rect rgb(255, 235, 235)
    Note over You,Disk: REBUILD — cost scales with the file
    You->>Agent: "fix the background in cell 26"
    Agent->>Disk: read notebook (106 KB)
    Disk-->>Agent: 30,266 tok
    Agent->>Agent: regenerate whole notebook
    Agent->>Disk: write notebook (106 KB)
    Disk-->>Agent: changed → re-injected, 30,266 tok
    Note right of Agent: ~60k tokens for a one-cell edit
    end

    rect rgb(235, 250, 235)
    Note over You,Disk: PATCH — cost scales with the change
    You->>Agent: "fix the background in cell 26"
    Agent->>Disk: read cell 26 only
    Disk-->>Agent: ~2 tok/char of one cell
    Agent->>Disk: write patch_task.py (18 KB)
    Agent->>Disk: run it
    Note right of Agent: ~5k tokens, and the script<br/>survives the session dying
    end
```

---

## 4. The fix, as a decision tree

```mermaid
flowchart TD
    START(["About to start a long task"]) --> AUDIT["<b>tools/context_audit.py PATH</b>"]
    AUDIT --> Q1{"worst case<br/>over budget?"}

    Q1 -->|No| PROMPT
    Q1 -->|Yes| PREP["<b>tools/prep_workspace.sh PATH --apply</b>"]

    PREP --> P1["strip notebook outputs"]
    PREP --> P2["move &gt;50KB files → artifacts/"]
    PREP --> P3["install AGENTS.md<br/>declaring artifacts/ off-limits"]
    PREP --> P4["<b>edit in-context files with Edit,<br/>never with shell scripts</b>"]
    P4 --> RE
    P1 --> RE["re-audit"]
    P2 --> RE
    P3 --> RE

    RE --> Q2{"still over?"}
    Q2 -->|Yes| CUT["delete superseded versions<br/>· split the task<br/>· reduce scope"]
    CUT --> RE
    Q2 -->|No| PROMPT["<b>paste prompts/session-start.md</b>"]

    PROMPT --> WORK["Work:<br/>patch don't rebuild ·<br/>one batched check ·<br/>no sub-agents ·<br/>delete intermediates"]
    WORK --> Q3{"natural<br/>boundary?"}
    Q3 -->|No| WORK
    Q3 -->|Yes| CKPT["<b>prompts/checkpoint.md</b><br/>patch script + STATE.md"]
    CKPT --> Q4{"task done?"}
    Q4 -->|No| FRESH["fresh session +<br/><b>prompts/resume.md</b>"]
    FRESH --> WORK
    Q4 -->|Yes| DONE(["Done"])

    style PREP fill:#27ae60,color:#fff
    style PROMPT fill:#27ae60,color:#fff
    style CKPT fill:#27ae60,color:#fff
    style DONE fill:#27ae60,color:#fff
```

Measured effect of the two green boxes at the top: **277,530 → 40,314 estimated
tokens**, 5.5× a 200k budget down to 0.8×.

---

## 5. Shape of a long task

The point of checkpointing is not tidiness. It is that a session you can
abandon cheaply is never a disaster.

```mermaid
flowchart LR
    subgraph S1["Session 1"]
      direction TB
      A1["work"] --> A2["patch script<br/>+ STATE.md"]
    end
    subgraph S2["Session 2"]
      direction TB
      B1["read STATE.md<br/>confirm understanding"] --> B2["work"] --> B3["patch script<br/>+ STATE.md"]
    end
    subgraph S3["Session 3"]
      direction TB
      C1["read STATE.md"] --> C2["work"] --> C3["ship"]
    end

    A2 ==>|"handoff artifact,<br/>not conversation history"| B1
    B3 ==> C1

    X["limit hits<br/>mid-session"] -.->|"lose ≤ one<br/>checkpoint interval"| S2

    style A2 fill:#27ae60,color:#fff
    style B3 fill:#27ae60,color:#fff
    style X fill:#c0392b,color:#fff
```

Contrast with the failure mode this repo documents: a sub-agent measurement
running with no on-disk checkpoint, killed by the limit, producing **no**
result rather than a partial one — and the earlier attempts had already been
deleted, so it could not even be diagnosed after the fact.

---

## Rendering these elsewhere

GitHub renders Mermaid in Markdown natively. For slides or a doc:

```bash
npx -y @mermaid-js/mermaid-cli -i docs/00-diagrams.md -o out.md
```

which writes each diagram out as an SVG alongside. Pre-rendered SVGs are also checked in for contexts with no Mermaid support:

| file | what |
|---|---|
| [`img/overview.svg`](img/overview.svg) | before/after summary (README hero) |
| [`img/problem.svg`](img/problem.svg) | diagram 1, the amplification loop |
| [`img/solution.svg`](img/solution.svg) | diagram 4, the fix as a decision tree |

These were generated with `htmlLabels: false` so the text is real `<text>`
rather than `foreignObject` — the latter renders in a browser but not when
GitHub serves the SVG through an `<img>` tag.

# 00 — Diagrams

Five pictures: what the problem is, why it compounds, what it costs, how to fix
it, and how a long task should be shaped. All Mermaid, so they render inline on
GitHub.

---

## 1. The problem, in one picture

Each turn re-pays for the whole working directory, not for the size of the
change.

```mermaid
flowchart TD
    A["Agent reads a file<br/>to work on it"] --> B["File contents<br/>enter context"]
    B --> C["Agent edits the file<br/><i>(a 20-line diff)</i>"]
    C --> D{"File changed<br/>on disk"}
    D -->|"harness re-sends<br/>current contents"| B
    C --> E["Build step writes<br/>a new artifact"]
    E --> D

    B -.->|"cost per turn =<br/><b>size of the file</b>,<br/>not size of the edit"| F["Context fills"]
    F --> G["Session limit"]
    G --> H["Work in flight is lost,<br/>not merely delayed"]

    style G fill:#c0392b,color:#fff
    style H fill:#c0392b,color:#fff
    style F fill:#e67e22,color:#fff
```

The loop `B → C → D → B` is the whole story. It is correct behaviour — an agent
editing against a stale copy of a file produces broken patches — but it means
the steady-state cost of a turn is set by **what is in the directory**, not by
what you asked for.

> Status: the re-injection step is inferred, not directly observed. See
> [02-root-cause.md](02-root-cause.md).

---

## 2. What it actually cost here

The measured directory, by weight. Everything in red was **never read again**
after the round that produced it.

```mermaid
pie showData
    title Working directory, estimated tokens (top files)
    "executed_solution.ipynb (never re-read)" : 46641
    "scicode_...length_scale.ipynb (superseded)" : 34217
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

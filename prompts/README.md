# Copy-paste prompts

The docs explain the mechanism. These are the things you actually paste.

| file | when to use it |
|---|---|
| [`one-liner.txt`](one-liner.txt) | You want one sentence and nothing else. Start here. |
| [`session-start.md`](session-start.md) | The full version. Paste as your first message on any long task. |
| [`mid-session.md`](mid-session.md) | You notice it happening halfway through. Corrective prompts. |
| [`checkpoint.md`](checkpoint.md) | Ending a session deliberately, before the limit ends it for you. |
| [`resume.md`](resume.md) | First message of the fresh session that continues the work. |
| [`../examples/AGENTS.md.sample`](../examples/AGENTS.md.sample) | Permanent version — put it in the repo so you never paste anything |

## Which one do I need?

- **One task, one session** → `one-liner.txt` is enough.
- **Multi-day task, iterative build-and-verify** → `session-start.md`, then
  `checkpoint.md` at each boundary, then `resume.md`.
- **Same project repeatedly** → put `AGENTS.md` in the repo and stop pasting.
  Most harnesses read it automatically, so the rules apply to every session.

## Why prompting works here at all

The failure is that the agent keeps large files in play — regenerating them,
re-reading them, re-verifying them. Those are all *choices the agent makes*,
and they are choices it will make differently if you tell it to. The prompts
below are just the mitigations in
[`../docs/03-mitigations.md`](../docs/03-mitigations.md) written in the second
person.

What prompting **cannot** fix: a directory that is already too large. Run
`tools/prep_workspace.sh` first. No instruction makes a 46k-token notebook
cheap to read.

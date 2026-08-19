# Mid-session corrections

You forgot the session-start prompt, or the session is drifting. Each of these
is a single message you can paste the moment you notice the symptom.

---

## You see it regenerating a large file

```
Stop — don't regenerate that file. Write a patch script that changes only the
parts that need to change, show me the script, then run it. Keep the script; it
is how we redo this if the session ends.
```

---

## It is re-reading the same artifact every round

```
You've now read that file three rounds running to confirm state that hasn't
changed. Cache what you need as a short note in STATE.md and stop re-reading
it. If you think it may have changed, check its size and mtime first, not its
contents.
```

---

## Output from tool calls is flooding the session

```
From now on, batch every check into one command and print only the tail —
something like: `make check 2>&1 | tail -40`. One call per verification round,
not one per tool.
```

---

## It is about to delegate something expensive to a sub-agent

```
Don't run that in a sub-agent. Sub-agents are the first thing dropped when a
limit is reached, and a half-finished measurement is worth nothing. Run it
in-process, and write each result to a file as you get it so an interruption
leaves us with partial data instead of none.
```

---

## It is dismissing a report or review as stale

```
Before you dismiss that as stale: diff the file THEY saw against your local
copy, cell by cell, and show me any size differences. Files get truncated in
transit. Assume the report is right until that diff is clean.
```

*(This one cost three rounds in the session that prompted this repo. The
delivered notebook cell had been cut from 22,624 characters to 2,875; the
reviewers were right every time.)*

---

## The working directory has grown during the session

```
Audit the working directory: list every file over 20KB with its size, and tell
me which ones nothing downstream reads any more. Then delete those, and move
generated output into artifacts/ — and note in STATE.md that artifacts/ is not
to be read.
```

---

## You are near the limit and want to land safely

```
We may be close to a session limit. Stop starting new work. Instead:
1. Make sure every edit so far is captured in a re-runnable patch script.
2. Write STATE.md: done / pending / ruled out and why.
3. Give me the current test and validator output.
Then stop. I'll continue in a fresh session.
```

Follow that with [`checkpoint.md`](checkpoint.md) if you want the fuller
version.

---

## It already hit and the session is gone

Nothing to paste — the next session must not start by editing. Run triage on
the directory first:

```bash
python3 tools/salvage.py . --since 120 --write-state
```

Then follow [`../docs/06-when-it-happens.md`](../docs/06-when-it-happens.md).

# Replication test — does your agent do this too?

Everything in this repo is **n = 1**: one harness, one session, one directory.
The mechanism may be universal, may be version-specific, may not exist at all
outside the setup that produced it. The only way to find out is more data
points.

This is a controlled A/B you can run in about five minutes on **any** coding
agent — Claude Code or whatever you use.

---

## Design it fairly

The failure mode of "ask an AI whether it has a bug" is that it agrees with
you. The prompt below is written to avoid that:

- It never says what the expected answer is.
- It asks for **observations**, not opinions.
- It makes "nothing happened" an explicitly valid, useful result.
- Its key evidence is a **usage counter**, not the model's introspection —
  a model reporting on its own context is unreliable, a token meter is not.

If you paraphrase it, keep those four properties. A leading prompt will
manufacture a confirmation and waste everyone's time, including yours.

---

## Two design errors this protocol had, and why they matter

Fixed in the version below. Recorded because the first run of the original
protocol produced a *false* null, and anyone reusing an older copy will get one
too.

**Error 1 — the observation window was inside the turn.** The original said
"immediately report" after each edit. But at least one harness does not deliver
resync notices in the tool result at all; it delivers them as system messages at
the **start of the following turn**. Asking the agent to look for them inside
the same turn is asking it to look before they arrive. Every step must now end
the turn, and the check happens at the top of the next one.

**Error 2 — the precondition was never verified.** The mechanism only applies to
a file that is *fully in context*. The first run used an 800-line file whose read
was silently truncated in the middle (~500 lines elided). Nothing was ever fully
in context, so nothing could be re-sent. The result read as "no re-injection"
when it actually meant "test never started." There is now an explicit
truncation check before any edit happens.

Both errors push in the same direction: **towards a false negative.** If you are
collecting null results, that is the failure mode that will quietly ruin your
table.

---

## The prompt

Paste as the **first message** of a fresh session, in an empty directory. Note
that this is now a **multi-turn** script — you send the follow-ups yourself,
one per step.

### Turn 1 — setup and precondition check

```
I want to run a small controlled experiment about how this tool handles file
changes. It runs over several messages; please do only what each message asks
and then stop. Report only what you observe — I have no hypothesis I want
confirmed, and "nothing notable happened" is a perfectly good result.

1. Create test_subject.txt containing 200 numbered lines, each reading
   "line N: the quick brown fox jumps over the lazy dog" (N from 1 to 200).
2. Read the whole file.
3. PRECONDITION CHECK — quote back to me, verbatim, the exact text of lines
   30, 100 and 170. If any part of the file was truncated, elided, or summarised
   when you read it, say so explicitly and tell me which line ranges you do NOT
   have.
4. Tell me your current context or token usage if any tool exposes it. If
   nothing does, say "no counter available" — do not estimate.

Then stop.
```

**Do not continue until step 3 comes back clean.** If the read was truncated,
the file is not in context and the experiment cannot start — halve the line
count and repeat. 200 lines (~10 KB) is chosen to stay under truncation
thresholds; drop to 100 if needed. A file too small to be truncated is worth far
more than a big one that is.

### Turn 2 — native edit

```
Using your built-in file editing tool (NOT a shell command), change line 100 to
read "line 100: CHANGED BY EDIT TOOL". Quote the tool's response verbatim, then
stop.
```

### Turn 3 — the check that matters

```
Before answering: look at everything that arrived at the START of this turn,
before my message — system messages, reminders, notices, attachments, anything
not written by me.

1. Did any of it contain the contents of test_subject.txt? If yes, quote its
   first line and say roughly how many lines it carried.
2. Did any of it mention the file changing on disk?
3. Current context/token usage, if exposed.

Then stop.
```

### Turn 4 — shell edit

```
Using only a shell command, change line 101:
sed -i 's/^line 101:.*/line 101: CHANGED BY SHELL/' test_subject.txt
Quote the tool's response verbatim, then stop.
```

### Turn 5 — the same check

```
[repeat the Turn 3 text verbatim]
```

### Turn 6 — a change that changes nothing

```
Run: touch test_subject.txt
Quote the response verbatim, then stop.
```

### Turn 7 — the same check, plus wrap-up

```
[repeat the Turn 3 text verbatim, then add:]

4. Now compare turns 3, 5 and 7. Did what arrived at the start of those turns
   differ? Say plainly if it did not.
5. Does this tool write a session log or transcript to disk? Give the path if so,
   and tell me whether a file actually exists there right now.

Do not speculate about internal implementation. Report only what you saw.
```

---

## What each result means

| Observation | Reading |
|---|---|
| Turn 5 carries file contents, turn 3 does not | Same mechanism as documented here |
| Turns 3 and 5 both carry contents | Resyncs on every change — worse, but at least consistent |
| Neither carries contents | The harness diffs, or tracks state without re-sending. Good design; report it |
| Turn 7 (`touch`, no content change) carries contents | Resync keyed on mtime rather than content hash — a cheap, real bug |
| Usage jumps after the shell edit but not the native edit | The strongest signal available, because it doesn't rely on introspection |

### When to write "inconclusive" instead of "null"

Be strict about this. A false null is worse than no row at all.

| Condition | Verdict |
|---|---|
| Precondition check showed truncation | **Inconclusive.** File was never in context; nothing could be re-sent |
| No usage counter *and* checks were made inside the turn | **Inconclusive.** Both instruments unavailable |
| No usage counter, but turn-start checks were clean | **Weak null.** Qualitative only — say so |
| Clean precondition, turn-start checks, usage counter present | **Strong result**, whichever way it goes |

Step C is the sharpest single test. A file whose bytes are unchanged has no
information to resynchronise. If contents come back anyway, the harness is
watching the wrong thing.

---

## If your tool writes a transcript

That beats self-report entirely. Claude Code writes JSONL under
`~/.claude/projects/<slug>/<session-id>.jsonl`; other tools vary and some write
nothing. If you find one:

```bash
python3 tools/transcript_forensics.py <transcript.jsonl>
```

The parser targets Claude Code's record shape. On another format it will report
`unrecognised attachments` rather than lying to you — that number being large
means the parser needs a new adapter, not that your harness is clean. Adapters
are welcome as PRs.

---

## Please report back

Open an issue with:

1. Tool and version.
2. The A / B / C comparison.
3. Usage deltas if your tool exposes them.
4. **Null results included.** A harness that does this correctly is the most
   useful data point in the whole repo, because it proves the problem is
   fixable rather than inherent.

Keep observation and inference separate, the way
[`docs/07-the-actual-bug.md`](../docs/07-the-actual-bug.md) does. That
separation is the only reason this repo's own claims are worth anything.

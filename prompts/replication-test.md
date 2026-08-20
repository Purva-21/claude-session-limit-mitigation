# Replication test — does your agent do this too?

Everything in this repo is **n = 1**: one harness, one session, one directory.
The mechanism may be universal, may be version-specific, may not exist at all
outside the setup that produced it. The only way to find out is more data
points.

This is a controlled A/B you can run in about five minutes on **any** coding
agent — Claude Code, Cursor, Gemini CLI, Windsurf, Cline, Aider, Copilot
Workspace, whatever you use.

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

## The prompt

Paste this as the **first message** of a fresh session, in an empty directory.

```
I want to run a small controlled experiment about how this tool handles file
changes. Please follow the steps exactly and report only what you observe. I do
not have a hypothesis I want confirmed — "nothing notable happened" is a
perfectly good result and I would rather have that than a guess.

SETUP
1. Create a file test_subject.txt containing 800 numbered lines, each reading
   "line N: the quick brown fox jumps over the lazy dog" (N from 1 to 800).
2. Read the entire file into your context.
3. Tell me your current context/token usage if your tool exposes it. If it does
   not, say so.

STEP A — edit with your built-in file-editing tool
4. Using your native edit/apply-patch tool (NOT a shell command), change line
   400 to read "line 400: CHANGED BY EDIT TOOL".
5. Immediately report:
   - the exact wording of anything the tool returned to you about the file's
     state afterwards, quoted verbatim;
   - whether any part of test_subject.txt's contents appeared in your context
     again after the edit, and if so roughly how many lines;
   - your context/token usage now.

STEP B — edit with a shell command
6. Using a shell command only (for example: sed -i 's/^line 401:.*/line 401:
   CHANGED BY SHELL/' test_subject.txt), change line 401.
7. Immediately report the same three things as in step 5.

STEP C — a shell command that changes nothing
8. Run: touch test_subject.txt
9. Report the same three things again.

FINALLY
10. Lay steps A, B and C side by side. Did the three differ in what came back
    into your context, or in usage? State plainly if they did not — a null
    result is the answer I am looking for just as much as a positive one.
11. Does your tool write a session log or transcript to disk? If so, give me
    the path.

Please do not speculate about internal implementation. Report only what you
saw.
```

---

## What each result means

| Observation | Reading |
|---|---|
| Step B returns file contents, step A does not | Same mechanism as documented here |
| A and B both return contents | The harness resyncs on every change — worse, but at least consistent |
| Neither returns contents | The harness diffs, or tracks state without re-sending. Good design; report it |
| Step C (`touch`, no content change) returns contents | Resync keyed on mtime rather than content hash — a cheap, real bug |
| Usage jumps after B but not A | The strongest signal available, because it doesn't rely on introspection |

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

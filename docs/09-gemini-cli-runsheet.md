# 09 — Run sheet: replicating on Gemini CLI

Gemini CLI is the **best first replication target**, and not because it's the
most likely to have the bug. Because it is the only one that will tell you the
truth without you having to trust the model's self-report.

It ships local OpenTelemetry that emits `gemini_cli.token.usage` broken down by
type — `input`, `output`, `thought`, `cache`, `tool` — plus `gemini_cli.tool_call`
events carrying the function name, all tagged with a `sessionId`
([telemetry docs](https://google-gemini.github.io/gemini-cli/docs/cli/telemetry.html)).

That is exactly the per-turn input attribution whose absence forced the
hand-parsing in [07-the-actual-bug.md](07-the-actual-bug.md). Here you get it
from the tool itself. **A measured input-token delta per turn beats any amount
of asking the model what it noticed.**

---

## 1. Install and authenticate (10 minutes)

```bash
npm install -g @google/gemini-cli     # or: brew install gemini-cli
gemini
```

Sign in with a personal Google account on first run — free tier is 60 req/min
and 1,000 req/day, which is far more than this test needs. An API key from
AI Studio works too ([repo README](https://github.com/google-gemini/gemini-cli)).

## 2. Turn on local telemetry — do this *before* the test

In the project directory you'll test in, create `.gemini/settings.json`:

```json
{
  "telemetry": {
    "enabled": true,
    "target": "local",
    "outfile": ".gemini/telemetry.log"
  }
}
```

There is **no default file output** — if you skip `outfile`, nothing is written
and you'll have run the whole test for nothing. Verify the file exists and is
growing after your first prompt before going further.

## 3. Set up a clean test directory

```bash
mkdir -p ~/replication/gemini && cd ~/replication/gemini
mkdir -p .gemini   # then add settings.json from step 2
python3 - <<'PY'
with open('test_subject.txt','w') as f:
    for n in range(1, 801):
        f.write("line %d: the quick brown fox jumps over the lazy dog\n" % n)
PY
wc -c test_subject.txt        # ~40 KB — big enough that a resync is unmistakable
```

Then start `gemini` **in that directory**.

## 4. The runs

Do these as **separate turns**, in one session, in this order. Call `/stats`
after every single one — it reports session token usage and cached-token savings
([commands reference](https://google-gemini.github.io/gemini-cli/docs/cli/commands.html)).

> **Check the read wasn't truncated before you go past turn 0.** After the read,
> ask it to quote lines 30, 400 and 770 verbatim. If any of the file was elided,
> it was never fully in context and nothing can be re-sent — you'd be measuring
> nothing and recording it as a null. Shrink the file to 200 lines and repeat.
> A first run of this protocol on another harness failed exactly here.

> **One intervention per turn, and check at the start of the *next* turn.**
> Resync notices may arrive as system messages at a turn boundary rather than in
> the tool result. `/stats` is immune to this since it reports cumulative
> session totals, but the qualitative "did content come back" question is not.

| # | Turn | Record |
|---|---|---|
| 0 | `Read test_subject.txt in full.` then `/stats` | baseline |
| A | `Using your file editing tool, change line 400 to read "line 400: CHANGED BY EDIT TOOL".` then `/stats` | Δ input tokens |
| B | `Using only a shell command, change line 401. Use: sed -i 's/^line 401:.*/line 401: CHANGED BY SHELL/' test_subject.txt` then `/stats` | Δ input tokens |
| C | `Run: touch test_subject.txt` then `/stats` | Δ input tokens |
| D | `Say the word "ok" and nothing else.` then `/stats` | **control turn** — the floor cost of any turn |

Turn D is what makes the others interpretable. Every turn costs *something* just
by resending conversation history. Without D you cannot tell a resync from
ordinary context growth, and you will over-read your result.

Gemini's native edit tool is `replace`; `write_file` rewrites wholesale, and
shell runs via `run_shell_command` or the `!` prefix. For turn A insist on the
edit tool — if it reaches for shell, say so and retry, or the A/B comparison is
meaningless.

## 5. Read the numbers, not the vibes

```bash
python3 tools/gemini_telemetry_parse.py ~/replication/gemini/.gemini/telemetry.log
```

Or, if that parser doesn't match your version's format, fall back to `/stats`
deltas — they're coarser but sufficient. What you're looking for:

| Pattern | Reading |
|---|---|
| B ≫ A, both ≫ D | Same mechanism as documented here |
| A ≈ B ≫ D | Resyncs on every change regardless of source — worse, but consistent |
| A ≈ B ≈ D | No resync behaviour. **Report this loudly.** |
| C ≫ D | Keyed on mtime, not content hash — a file with unchanged bytes triggered a resend |
| `cache` token type rises instead of `input` | Different architecture: it's re-sending but the provider caches it. Note this — it changes the cost story completely |

That last row matters. Gemini CLI reports a `cache` token type, so a resync
might be cheap there even if it happens. **"It happens but costs little" is a
different and more interesting finding than "it doesn't happen."** Don't collapse
the two.

## 6. Record it

Fill in a row of the table in `docs/10-replication-results.md` — tool, version,
model, the five deltas, and your reading. Include the raw `/stats` output. Note
your Gemini CLI version (`gemini --version`); this behaviour is exactly the kind
that changes between releases.

---

## Two failure modes to avoid

**Don't tell it what you expect.** Use the wording in
[`prompts/replication-test.md`](../prompts/replication-test.md). If you ask "did
the file get re-injected?", you'll get a confident yes whether or not it did.
Ask it to perform steps and report `/stats`; let the counter answer.

**Don't run A and B in the same turn.** One turn, one intervention. Batching
them makes the deltas uninterpretable, which is the same mistake — batching
edits into one shell call — that caused the original problem.

---

## Then do the same for the others

Ranked by ease of getting hard numbers:

1. **Gemini CLI** — telemetry with token-type breakdown. Start here.
2. **Aider** — open source, prints token counts and cost per turn by default.
3. **Cline / Roo** — VS Code extensions, show per-request token counts in the UI.
4. **Cursor** — shows context usage but is harder to attribute; behavioural A/B only.
5. **Claude Code** — already done; `tools/transcript_forensics.py` parses its JSONL.

Three tools with real numbers beats six with impressions.

Sources: [Gemini CLI telemetry](https://google-gemini.github.io/gemini-cli/docs/cli/telemetry.html) ·
[commands reference](https://google-gemini.github.io/gemini-cli/docs/cli/commands.html) ·
[repository](https://github.com/google-gemini/gemini-cli)
